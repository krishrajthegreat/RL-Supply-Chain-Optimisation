"""
Experience rollout buffer with Generalised Advantage Estimation (GAE).

Stores per-agent trajectories from parallel environment rollouts
and computes advantages using GAE-λ for stable policy updates.

Design
------
Each agent has its own storage arrays (different obs/act dims),
but they share step indices and done flags since all agents act
simultaneously in the PettingZoo ParallelEnv.
"""

from __future__ import annotations

from typing import Dict, Generator, NamedTuple

import numpy as np
import torch


class RolloutBatch(NamedTuple):
    """A minibatch of experience for a single agent."""
    observations: torch.Tensor   # (B, obs_dim)
    actions: torch.Tensor        # (B, act_dim)
    log_probs: torch.Tensor      # (B,)
    advantages: torch.Tensor     # (B,)
    returns: torch.Tensor        # (B,)
    global_obs: torch.Tensor     # (B, global_obs_dim)


class AgentBuffer:
    """Fixed-size ring buffer for one agent's rollout data."""

    def __init__(self, capacity: int, obs_dim: int, act_dim: int):
        self.capacity = capacity
        self.obs = np.zeros((capacity, obs_dim), dtype=np.float32)
        self.actions = np.zeros((capacity, act_dim), dtype=np.float32)
        self.log_probs = np.zeros(capacity, dtype=np.float32)
        self.rewards = np.zeros(capacity, dtype=np.float32)
        self.values = np.zeros(capacity, dtype=np.float32)
        self.dones = np.zeros(capacity, dtype=np.float32)
        self.ptr = 0

    def store(
        self,
        obs: np.ndarray,
        action: np.ndarray,
        log_prob: float,
        reward: float,
        value: float,
        done: bool,
    ) -> None:
        idx = self.ptr
        self.obs[idx] = obs
        self.actions[idx] = action
        self.log_probs[idx] = log_prob
        self.rewards[idx] = reward
        self.values[idx] = value
        self.dones[idx] = float(done)
        self.ptr += 1

    @property
    def size(self) -> int:
        return self.ptr


class RolloutBuffer:
    """
    Multi-agent rollout buffer with GAE computation.

    Stores transitions for all 6 agents simultaneously across
    multiple vectorised environment steps.

    Parameters
    ----------
    capacity : int
        Maximum number of steps per rollout (across all envs).
    agent_dims : dict
        Mapping agent_name → (obs_dim, act_dim).
    global_obs_dim : int
        Dimension of the concatenated global observation.
    gamma : float
        Discount factor (default 0.99).
    gae_lambda : float
        GAE λ parameter (default 0.95).
    """

    def __init__(
        self,
        capacity: int,
        agent_dims: Dict[str, tuple[int, int]],
        global_obs_dim: int,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
    ):
        self.capacity = capacity
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.global_obs_dim = global_obs_dim

        # Per-agent buffers
        self.agent_buffers: Dict[str, AgentBuffer] = {}
        for name, (obs_dim, act_dim) in agent_dims.items():
            self.agent_buffers[name] = AgentBuffer(capacity, obs_dim, act_dim)

        # Global observation storage (for critic)
        self.global_obs = np.zeros(
            (capacity, global_obs_dim), dtype=np.float32
        )

        # Advantages and returns (computed post-rollout)
        self._advantages: Dict[str, np.ndarray] = {}
        self._returns: Dict[str, np.ndarray] = {}

    @property
    def size(self) -> int:
        """Number of stored steps (same for all agents)."""
        first = next(iter(self.agent_buffers.values()))
        return first.size

    def store(
        self,
        agent_obs: Dict[str, np.ndarray],
        agent_actions: Dict[str, np.ndarray],
        agent_log_probs: Dict[str, float],
        agent_rewards: Dict[str, float],
        agent_values: Dict[str, float],
        dones: Dict[str, bool],
        global_obs: np.ndarray,
    ) -> None:
        """Store one timestep of experience for all agents."""
        idx = self.size
        if idx >= self.capacity:
            return  # buffer full

        for name, buf in self.agent_buffers.items():
            done = dones.get(name, False)
            buf.store(
                obs=agent_obs[name],
                action=agent_actions[name],
                log_prob=agent_log_probs[name],
                reward=agent_rewards[name],
                value=agent_values[name],
                done=done,
            )

        self.global_obs[idx] = global_obs

    def compute_gae(
        self, last_values: Dict[str, float], last_dones: Dict[str, bool]
    ) -> None:
        """
        Compute GAE advantages and discounted returns for all agents.

        Must be called after the rollout is complete, before sampling
        minibatches.

        Args:
            last_values: V(s_T) for each agent at the final step.
            last_dones: Whether the episode ended at the final step.
        """
        n = self.size
        for name, buf in self.agent_buffers.items():
            advantages = np.zeros(n, dtype=np.float32)
            last_gae = 0.0
            last_val = last_values[name]
            last_done = float(last_dones.get(name, False))

            for t in reversed(range(n)):
                if t == n - 1:
                    next_non_terminal = 1.0 - last_done
                    next_value = last_val
                else:
                    next_non_terminal = 1.0 - buf.dones[t + 1]
                    next_value = buf.values[t + 1]

                delta = (
                    buf.rewards[t]
                    + self.gamma * next_value * next_non_terminal
                    - buf.values[t]
                )
                last_gae = (
                    delta
                    + self.gamma * self.gae_lambda * next_non_terminal * last_gae
                )
                advantages[t] = last_gae

            returns = advantages + buf.values[:n]
            self._advantages[name] = advantages
            self._returns[name] = returns

    def get_batches(
        self, agent_name: str, batch_size: int, device: str = "cpu"
    ) -> Generator[RolloutBatch, None, None]:
        """
        Yield shuffled minibatches of experience for one agent.

        Args:
            agent_name: Which agent's data to sample.
            batch_size: Minibatch size.
            device: "cpu" or "cuda".

        Yields:
            RolloutBatch named tuples.
        """
        buf = self.agent_buffers[agent_name]
        n = self.size
        adv = self._advantages[agent_name]
        ret = self._returns[agent_name]

        # Normalise advantages
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)

        # Shuffle indices
        indices = np.random.permutation(n)

        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            idx = indices[start:end]

            yield RolloutBatch(
                observations=torch.from_numpy(buf.obs[idx]).to(device),
                actions=torch.from_numpy(buf.actions[idx]).to(device),
                log_probs=torch.from_numpy(buf.log_probs[idx]).to(device),
                advantages=torch.from_numpy(adv[idx]).to(device),
                returns=torch.from_numpy(ret[idx]).to(device),
                global_obs=torch.from_numpy(self.global_obs[idx]).to(device),
            )

    def reset(self) -> None:
        """Clear all stored data for the next rollout."""
        for buf in self.agent_buffers.values():
            buf.ptr = 0
        self._advantages.clear()
        self._returns.clear()
