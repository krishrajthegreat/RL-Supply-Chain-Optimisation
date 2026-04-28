"""
HAPPO — Heterogeneous-Agent Proximal Policy Optimisation.

Core training algorithm for the NEXUS MARL supply-chain system.

Key differences from standard PPO / MAPPO:
  1. **Sequential agent updates**: agents are updated one at a time,
     conditioned on the policies already updated in this iteration.
  2. **No parameter sharing**: each agent has its own Actor network
     with architecture sized to its unique obs/act space.
  3. **Importance-weight decomposition**: the multi-agent advantage
     is decomposed per-agent via importance ratios, ensuring
     monotonic improvement across the team.

Reference
---------
Kuba et al., "Trust Region Policy Optimisation in Multi-Agent
Reinforcement Learning", ICLR 2022.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import torch
import torch.nn as nn

from nexus.training.networks import (
    AgentActor,
    GlobalCritic,
    _flatten_obs,
    _flatten_space_dim,
    build_networks,
)
from nexus.training.rollout_buffer import RolloutBuffer

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HAPPO Trainer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class HAPPOTrainer:
    """
    HAPPO training loop for NEXUS multi-agent supply-chain env.

    Parameters
    ----------
    env : SupplyChainEnv
        A single (non-vectorised) environment instance.
    lr_actor : float
        Learning rate for actor networks (default 3e-4).
    lr_critic : float
        Learning rate for the centralized critic (default 1e-3).
    gamma : float
        Discount factor (default 0.99).
    gae_lambda : float
        GAE λ (default 0.95).
    clip_eps : float
        PPO clip parameter ε (default 0.2).
    entropy_coef : float
        Entropy bonus coefficient (default 0.01).
    value_loss_coef : float
        Value loss weight (default 0.5).
    max_grad_norm : float
        Gradient clipping norm (default 0.5).
    update_epochs : int
        Number of passes over the buffer per iteration (default 4).
    batch_size : int
        Minibatch size for SGD (default 256).
    rollout_steps : int
        Steps to collect per rollout before update (default 2048).
    device : str
        "cpu" or "cuda".
    checkpoint_dir : str | Path
        Where to save model checkpoints.
    """

    def __init__(
        self,
        env,
        lr_actor: float = 3e-4,
        lr_critic: float = 1e-3,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_eps: float = 0.2,
        entropy_coef: float = 0.01,
        value_loss_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        update_epochs: int = 4,
        batch_size: int = 256,
        rollout_steps: int = 2048,
        device: str = "cpu",
        checkpoint_dir: str | Path = "checkpoints",
    ):
        self.env = env
        self.device = device
        self.clip_eps = clip_eps
        self.entropy_coef = entropy_coef
        self.value_loss_coef = value_loss_coef
        self.max_grad_norm = max_grad_norm
        self.update_epochs = update_epochs
        self.batch_size = batch_size
        self.rollout_steps = rollout_steps
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # ── Build networks ─────────────────────────────────────
        self.actors, self.critic, self.global_obs_dim = build_networks(
            env, device=device
        )

        # ── Optimizers ─────────────────────────────────────────
        self.actor_optimizers: Dict[str, torch.optim.Adam] = {}
        for name, actor in self.actors.items():
            self.actor_optimizers[name] = torch.optim.Adam(
                actor.parameters(), lr=lr_actor, eps=1e-5
            )
        self.critic_optimizer = torch.optim.Adam(
            self.critic.parameters(), lr=lr_critic, eps=1e-5
        )

        # ── Rollout buffer ─────────────────────────────────────
        agent_dims = {}
        for name in env.possible_agents:
            obs_dim = _flatten_space_dim(env.observation_space(name))
            act_dim = _flatten_space_dim(env.action_space(name))
            agent_dims[name] = (obs_dim, act_dim)

        self.buffer = RolloutBuffer(
            capacity=rollout_steps,
            agent_dims=agent_dims,
            global_obs_dim=self.global_obs_dim,
            gamma=gamma,
            gae_lambda=gae_lambda,
        )

        # ── Metrics ────────────────────────────────────────────
        self.iteration = 0
        self.total_steps = 0
        self._episode_rewards: list[float] = []
        self._episode_lengths: list[int] = []
        self._current_ep_reward = 0.0
        self._current_ep_length = 0

        # ── Agent update order (fixed for HAPPO sequential) ───
        self.update_order = list(env.possible_agents)

        # ── Stored obs from last reset/step (avoids re-querying env) ─
        self._last_obs: dict = {}

    # ═══════════════════════════════════════════════════════════════
    #  Rollout Collection
    # ═══════════════════════════════════════════════════════════════

    def collect_rollout(self) -> Dict[str, float]:
        """
        Collect a rollout of experience by running the env.

        Uses self._last_obs which is set by reset() or carry-over from
        the previous rollout.  Handles episode boundaries cleanly by
        auto-resetting and continuing to fill the buffer.

        Returns dict of per-agent mean rewards for logging.
        """
        self.buffer.reset()

        # Always start from a fresh episode if we have no stored obs
        if not self._last_obs:
            obs, _ = self.env.reset()
            self._last_obs = obs
            self._current_ep_reward = 0.0
            self._current_ep_length = 0

        obs = self._last_obs
        agent_reward_totals = {a: 0.0 for a in self.env.possible_agents}
        steps_collected = 0

        for _ in range(self.rollout_steps):
            # ── Build global observation for critic ────────────
            global_obs = self._build_global_obs(obs)
            global_obs_t = torch.from_numpy(global_obs).float().to(self.device)

            # ── Get value estimate ─────────────────────────────
            with torch.no_grad():
                value = self.critic(global_obs_t.unsqueeze(0)).item()

            # ── Sample actions from each actor ─────────────────
            agent_actions: dict = {}
            agent_actions_np: dict = {}
            agent_log_probs: dict = {}
            flat_obs: dict = {}

            for agent_name in self.env.possible_agents:
                if agent_name not in obs:
                    # Agent already terminated — use zeros
                    act_dim = _flatten_space_dim(
                        self.env.action_space(agent_name)
                    )
                    obs_dim = _flatten_space_dim(
                        self.env.observation_space(agent_name)
                    )
                    agent_actions_np[agent_name] = np.zeros(act_dim, dtype=np.float32)
                    agent_log_probs[agent_name] = 0.0
                    flat_obs[agent_name] = np.zeros(obs_dim, dtype=np.float32)
                    continue

                obs_flat = _flatten_obs(obs[agent_name])
                flat_obs[agent_name] = obs_flat.numpy()
                obs_t = obs_flat.to(self.device)

                with torch.no_grad():
                    action, log_prob = self.actors[agent_name].get_action(obs_t)

                action_np = action.cpu().numpy()
                agent_actions_np[agent_name] = action_np
                agent_log_probs[agent_name] = log_prob.item()
                agent_actions[agent_name] = self._unflatten_action(
                    agent_name, action_np
                )

            # ── Environment step ───────────────────────────────
            # Only step with agents that are currently alive
            active_actions = {
                k: v for k, v in agent_actions.items()
                if k in self.env.agents
            }
            next_obs, rewards, terminations, truncations, infos = (
                self.env.step(active_actions)
            )

            # ── Compute done flags ─────────────────────────────
            dones = {
                a: terminations.get(a, False) or truncations.get(a, False)
                for a in self.env.possible_agents
            }

            # ── Store in buffer ────────────────────────────────
            agent_values = {a: value for a in self.env.possible_agents}
            self.buffer.store(
                agent_obs=flat_obs,
                agent_actions=agent_actions_np,
                agent_log_probs=agent_log_probs,
                agent_rewards=rewards if rewards else {
                    a: 0.0 for a in self.env.possible_agents
                },
                agent_values=agent_values,
                dones=dones,
                global_obs=global_obs,
            )

            steps_collected += 1
            self.total_steps += 1

            # ── Track episode metrics ──────────────────────────
            if rewards:
                team_r = sum(rewards.values()) / max(len(rewards), 1)
                self._current_ep_reward += team_r
                for a in self.env.possible_agents:
                    if a in rewards:
                        agent_reward_totals[a] += rewards[a]
            self._current_ep_length += 1

            # ── Handle episode boundaries ──────────────────────
            episode_done = not self.env.agents  # all agents done
            if episode_done:
                self._episode_rewards.append(self._current_ep_reward)
                self._episode_lengths.append(self._current_ep_length)
                self._current_ep_reward = 0.0
                self._current_ep_length = 0
                obs, _ = self.env.reset()
            else:
                obs = next_obs

        # ── Store obs for next rollout (carry-over) ────────────
        self._last_obs = obs

        # ── Compute GAE advantages ─────────────────────────────
        last_global = self._build_global_obs(obs)
        last_global_t = torch.from_numpy(last_global).float().to(self.device)
        with torch.no_grad():
            last_value = self.critic(last_global_t.unsqueeze(0)).item()

        last_values = {a: last_value for a in self.env.possible_agents}
        last_dones = {a: False for a in self.env.possible_agents}
        self.buffer.compute_gae(last_values, last_dones)

        # ── Return mean rewards per agent ──────────────────────
        return {
            a: agent_reward_totals[a] / max(steps_collected, 1)
            for a in self.env.possible_agents
        }

    # ═══════════════════════════════════════════════════════════════
    #  HAPPO Update
    # ═══════════════════════════════════════════════════════════════

    def update(self) -> Dict[str, float]:
        """
        Perform the HAPPO policy update.

        Updates agents **sequentially** (the key HAPPO innovation).
        Each agent's update is conditioned on the already-updated
        policies, ensuring monotonic team improvement.

        Returns dict of loss metrics for logging.
        """
        metrics = {}

        # ── Update Critic (shared, one pass) ───────────────────
        critic_loss_total = 0.0
        critic_updates = 0
        for epoch in range(self.update_epochs):
            # Use first agent's buffer for global obs (same indices)
            first_agent = self.update_order[0]
            for batch in self.buffer.get_batches(
                first_agent, self.batch_size, self.device
            ):
                values = self.critic(batch.global_obs).squeeze(-1)
                critic_loss = nn.functional.mse_loss(values, batch.returns)

                self.critic_optimizer.zero_grad()
                critic_loss.backward()
                nn.utils.clip_grad_norm_(
                    self.critic.parameters(), self.max_grad_norm
                )
                self.critic_optimizer.step()

                critic_loss_total += critic_loss.item()
                critic_updates += 1

        metrics["critic_loss"] = (
            critic_loss_total / max(critic_updates, 1)
        )

        # ── Sequential Actor Updates (HAPPO core) ──────────────
        # In HAPPO, importance weights from previously updated agents
        # are accumulated and applied to subsequent agents' updates.
        accumulated_ratios = None

        for agent_name in self.update_order:
            actor = self.actors[agent_name]
            optimizer = self.actor_optimizers[agent_name]

            agent_policy_loss = 0.0
            agent_entropy = 0.0
            agent_updates = 0

            for epoch in range(self.update_epochs):
                for batch in self.buffer.get_batches(
                    agent_name, self.batch_size, self.device
                ):
                    # Evaluate current policy
                    log_probs, entropy = actor.evaluate_actions(
                        batch.observations, batch.actions
                    )

                    # Importance ratio — tightly clamped because
                    # log_prob sums over all action dimensions (up to 60),
                    # so even small per-dim shifts compound to huge ratios
                    log_ratio = log_probs - batch.log_probs
                    log_ratio = torch.clamp(log_ratio, -2.0, 2.0)
                    ratio = torch.exp(log_ratio)

                    # HAPPO: apply accumulated importance weights
                    # from previously updated agents
                    advantages = batch.advantages
                    if accumulated_ratios is not None:
                        # Truncate accumulated ratios to match batch
                        acc_batch = accumulated_ratios[:len(advantages)]
                        if len(acc_batch) == len(advantages):
                            advantages = advantages * acc_batch.detach()

                    # PPO-clip objective
                    surr1 = ratio * advantages
                    surr2 = (
                        torch.clamp(ratio, 1.0 - self.clip_eps, 1.0 + self.clip_eps)
                        * advantages
                    )
                    policy_loss = -torch.min(surr1, surr2).mean()

                    # Entropy bonus
                    entropy_loss = -entropy.mean()

                    # Total loss
                    loss = (
                        policy_loss
                        + self.entropy_coef * entropy_loss
                    )

                    # ── NaN / Inf guard ─────────────────────────
                    if torch.isnan(loss) or torch.isinf(loss):
                        logger.warning(
                            "NaN/Inf loss detected for %s (epoch %d) "
                            "— skipping this batch",
                            agent_name, epoch,
                        )
                        optimizer.zero_grad()
                        continue

                    optimizer.zero_grad()
                    loss.backward()
                    grad_norm = nn.utils.clip_grad_norm_(
                        actor.parameters(), self.max_grad_norm
                    )
                    if grad_norm > 10.0:
                        logger.debug(
                            "%s grad_norm=%.2f (clipped to %.1f)",
                            agent_name, grad_norm, self.max_grad_norm,
                        )
                    optimizer.step()

                    agent_policy_loss += policy_loss.item()
                    agent_entropy += entropy.mean().item()
                    agent_updates += 1

            metrics[f"{agent_name}_policy_loss"] = (
                agent_policy_loss / max(agent_updates, 1)
            )
            metrics[f"{agent_name}_entropy"] = (
                agent_entropy / max(agent_updates, 1)
            )

            # ── Update accumulated importance ratios ───────────
            # Recompute ratios with the now-updated policy
            with torch.no_grad():
                all_obs = torch.from_numpy(
                    self.buffer.agent_buffers[agent_name].obs[:self.buffer.size]
                ).to(self.device)
                all_acts = torch.from_numpy(
                    self.buffer.agent_buffers[agent_name].actions[:self.buffer.size]
                ).to(self.device)
                old_lps = torch.from_numpy(
                    self.buffer.agent_buffers[agent_name].log_probs[:self.buffer.size]
                ).to(self.device)

                new_lps, _ = actor.evaluate_actions(all_obs, all_acts)
                log_r = torch.clamp(new_lps - old_lps, -2.0, 2.0)
                new_ratios = torch.exp(log_r)

                if accumulated_ratios is None:
                    accumulated_ratios = new_ratios
                else:
                    min_len = min(len(accumulated_ratios), len(new_ratios))
                    accumulated_ratios = (
                        accumulated_ratios[:min_len] * new_ratios[:min_len]
                    )

                # Clamp accumulated product to prevent multiplicative
                # explosion across the 6-agent sequential update
                accumulated_ratios = torch.clamp(
                    accumulated_ratios, 0.1, 10.0
                )

        self.iteration += 1
        return metrics

    # ═══════════════════════════════════════════════════════════════
    #  Training Loop
    # ═══════════════════════════════════════════════════════════════

    def train(
        self,
        num_iterations: int = 2000,
        log_interval: int = 10,
        save_interval: int = 100,
        eval_fn=None,
        wandb_run=None,
    ) -> list[dict]:
        """
        Main training loop.

        Args:
            num_iterations: Total training iterations.
            log_interval: Print metrics every N iterations.
            save_interval: Save checkpoint every N iterations.
            eval_fn: Optional evaluation callback.
            wandb_run: Optional wandb.Run for live dashboard logging.

        Returns:
            List of per-iteration metric dicts.
        """
        all_metrics = []
        logger.info(
            "Starting HAPPO training: %d iterations, "
            "rollout=%d steps, device=%s",
            num_iterations, self.rollout_steps, self.device,
        )

        for i in range(1, num_iterations + 1):
            t0 = time.time()

            # ── Collect experience ─────────────────────────────
            reward_means = self.collect_rollout()

            # ── Update policies ────────────────────────────────
            update_metrics = self.update()

            dt = time.time() - t0
            fps = self.rollout_steps / dt

            # ── Aggregate metrics ──────────────────────────────
            ep_rewards = self._episode_rewards[-20:]
            ep_lengths = self._episode_lengths[-20:]

            metrics = {
                "iteration": i,
                "total_steps": self.total_steps,
                "fps": fps,
                "time_s": dt,
                "mean_ep_reward": (
                    np.mean(ep_rewards) if ep_rewards else 0.0
                ),
                "mean_ep_length": (
                    np.mean(ep_lengths) if ep_lengths else 0.0
                ),
                **{f"reward_{k}": v for k, v in reward_means.items()},
                **update_metrics,
            }
            all_metrics.append(metrics)

            # ── Logging ────────────────────────────────────────
            if i % log_interval == 0:
                logger.info(
                    "Iter %4d/%d | Steps: %7d | FPS: %5.0f | "
                    "Ep Reward: %+7.2f | Ep Len: %5.0f | "
                    "Critic Loss: %.4f",
                    i, num_iterations, self.total_steps, fps,
                    metrics["mean_ep_reward"],
                    metrics["mean_ep_length"],
                    metrics.get("critic_loss", 0),
                )

            # ── W&B Logging ────────────────────────────────────
            if wandb_run:
                log_dict = {
                    "iteration": i,
                    "total_steps": self.total_steps,
                    "fps": fps,
                    "mean_ep_reward": metrics["mean_ep_reward"],
                    "mean_ep_length": metrics["mean_ep_length"],
                    "critic_loss": metrics.get("critic_loss", 0),
                }
                # Per-agent rewards
                for k, v in reward_means.items():
                    log_dict[f"reward/{k}"] = v
                # Per-agent policy loss & entropy
                for k, v in update_metrics.items():
                    if "policy_loss" in k:
                        log_dict[f"loss/{k}"] = v
                    elif "entropy" in k:
                        log_dict[f"entropy/{k}"] = v
                # GPU memory
                if self.device == "cuda":
                    import torch
                    log_dict["vram_mb"] = torch.cuda.memory_allocated() / 1e6
                wandb_run.log(log_dict, step=i)

            # ── Checkpointing ──────────────────────────────────
            if i % save_interval == 0:
                self.save_checkpoint(f"iter_{i:05d}")
                logger.info("Checkpoint saved: iter_%05d", i)

            # ── Evaluation callback ────────────────────────────
            if eval_fn and i % save_interval == 0:
                eval_fn(self, i)

        # Final save
        self.save_checkpoint("final")
        logger.info(
            "Training complete. %d iterations, %d total steps.",
            num_iterations, self.total_steps,
        )

        return all_metrics

    # ═══════════════════════════════════════════════════════════════
    #  Checkpointing
    # ═══════════════════════════════════════════════════════════════

    def save_checkpoint(self, tag: str) -> Path:
        """Save all network weights and optimizer states."""
        path = self.checkpoint_dir / f"nexus_happo_{tag}.pt"
        state = {
            "iteration": self.iteration,
            "total_steps": self.total_steps,
            "critic": self.critic.state_dict(),
            "critic_optimizer": self.critic_optimizer.state_dict(),
        }
        for name, actor in self.actors.items():
            state[f"actor_{name}"] = actor.state_dict()
            state[f"actor_opt_{name}"] = (
                self.actor_optimizers[name].state_dict()
            )
        torch.save(state, path)
        return path

    def load_checkpoint(self, path: str | Path) -> None:
        """Load network weights and optimizer states."""
        state = torch.load(path, map_location=self.device, weights_only=False)
        self.iteration = state["iteration"]
        self.total_steps = state["total_steps"]
        self.critic.load_state_dict(state["critic"])
        self.critic_optimizer.load_state_dict(state["critic_optimizer"])
        for name in self.actors:
            self.actors[name].load_state_dict(state[f"actor_{name}"])
            self.actor_optimizers[name].load_state_dict(
                state[f"actor_opt_{name}"]
            )
        logger.info("Loaded checkpoint: %s (iter %d)", path, self.iteration)

    # ═══════════════════════════════════════════════════════════════
    #  Helpers
    # ═══════════════════════════════════════════════════════════════

    def _build_global_obs(self, obs: dict) -> np.ndarray:
        """Concatenate all agents' observations into one flat vector."""
        parts = []
        for agent_name in self.env.possible_agents:
            if agent_name in obs:
                flat = _flatten_obs(obs[agent_name]).numpy()
            else:
                dim = _flatten_space_dim(
                    self.env.observation_space(agent_name)
                )
                flat = np.zeros(dim, dtype=np.float32)
            parts.append(flat)
        return np.concatenate(parts)

    def _unflatten_action(
        self, agent_name: str, flat_action: np.ndarray
    ) -> dict[str, np.ndarray]:
        """Convert a flat action array back to a Dict action."""
        act_space = self.env.action_space(agent_name)
        result = {}
        offset = 0
        for key in sorted(act_space.spaces.keys()):
            box = act_space.spaces[key]
            size = int(np.prod(box.shape))
            result[key] = flat_action[offset:offset + size].reshape(box.shape)
            offset += size
        return result
