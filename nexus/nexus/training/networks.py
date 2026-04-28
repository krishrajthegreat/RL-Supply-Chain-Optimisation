"""
Neural network definitions for NEXUS HAPPO agents.

Each of the 6 supply-chain agents has its own Actor MLP that maps
from its observation space to its action space.  A single shared
Global Critic maps the concatenated global state to a scalar value
estimate (Centralized Training, Decentralized Execution — CTDE).

All networks use:
  • Xavier uniform initialization
  • LayerNorm after each hidden layer
  • Tanh activations (stable gradients for continuous control)
  • Sigmoid output squashing on actors (actions bounded [0, 1])
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from gymnasium import spaces

logger = logging.getLogger(__name__)

# ── Observation normalization bounds ─────────────────────────────
# Keys whose observation-space upper bound exceeds 1.0.
# Values are the max of the Box space (used to scale into [0, 1]).
_OBS_SCALE: dict[str, float] = {
    "weather_severity": 10.0,
    "throughput_ratio": 2.0,
    "dwell_time_ratio": 5.0,
    "circuit_states": 2.0,
    "queue_depth_velocity": 1.0,   # range [-1, 1] → will be shifted below
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _flatten_space_dim(space: spaces.Dict) -> int:
    """Total flat dimension of a Gymnasium Dict space."""
    total = 0
    for key, box in space.spaces.items():
        total += int(np.prod(box.shape))
    return total


def _flatten_obs(obs: dict[str, np.ndarray]) -> torch.Tensor:
    """Flatten a Dict observation into a single 1-D tensor.

    All observation values are normalised to approximately [0, 1]
    (or [-1, 1] for signed quantities) using the known observation-
    space bounds.  This prevents features with large native ranges
    (e.g. weather_severity ∈ [0, 10]) from dominating the gradient.
    """
    parts = []
    for key in sorted(obs.keys()):
        v = obs[key]
        if isinstance(v, np.ndarray):
            t = torch.from_numpy(v).float().flatten()
        else:
            t = torch.as_tensor(v).float().flatten()

        # Normalise to [0, 1] using known bounds
        if key in _OBS_SCALE and _OBS_SCALE[key] > 1.0:
            t = t / _OBS_SCALE[key]
        # Signed quantities: shift [-1, 1] → [0, 1]
        if key == "queue_depth_velocity":
            t = (t + 1.0) * 0.5

        # Safety clamp — observations should already be bounded,
        # but disruption stacking can occasionally exceed space limits
        t = torch.clamp(t, -1.0, 1.0)

        parts.append(t)
    return torch.cat(parts)


def _flatten_obs_batch(
    obs_list: list[dict[str, np.ndarray]],
) -> torch.Tensor:
    """Flatten a list of Dict observations into a (B, D) tensor."""
    return torch.stack([_flatten_obs(o) for o in obs_list])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Actor Network
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AgentActor(nn.Module):
    """
    Per-agent policy network (Actor).

    Maps a flattened observation to a mean action vector.
    Actions are squashed through Sigmoid to lie in [0, 1].
    A learned log-std parameter controls exploration noise.

    Parameters
    ----------
    obs_dim : int
        Flattened observation dimension.
    act_dim : int
        Flattened action dimension.
    hidden : int
        Hidden layer width (default 256).
    """

    def __init__(self, obs_dim: int, act_dim: int, hidden: int = 256):
        super().__init__()
        self.obs_dim = obs_dim
        self.act_dim = act_dim

        self.net = nn.Sequential(
            nn.Linear(obs_dim, hidden),
            nn.LayerNorm(hidden),
            nn.Tanh(),
            nn.Linear(hidden, hidden),
            nn.LayerNorm(hidden),
            nn.Tanh(),
        )
        self.mean_head = nn.Linear(hidden, act_dim)

        # Learnable log standard deviation (per action dimension)
        self.log_std = nn.Parameter(torch.zeros(act_dim) - 0.5)

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight, gain=1.0)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(
        self, obs: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            obs: (B, obs_dim) flattened observations.

        Returns:
            mean: (B, act_dim) action means in [0, 1].
            std: (B, act_dim) action standard deviations.
        """
        h = self.net(obs)
        mean = torch.sigmoid(self.mean_head(h))
        # Clamp log_std to prevent degenerate distributions:
        #   min=-5  → std ≈ 0.0067 (tight but non-zero)
        #   max=0.5 → std ≈ 1.649  (sufficient exploration)
        log_std_clamped = torch.clamp(self.log_std, min=-5.0, max=0.5)
        std = torch.exp(log_std_clamped).expand_as(mean)
        return mean, std

    def get_action(
        self, obs: torch.Tensor, deterministic: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Sample an action and compute its log-probability.

        Args:
            obs: (B, obs_dim) or (obs_dim,) observation tensor.
            deterministic: If True, return the mean (no noise).

        Returns:
            action: (B, act_dim) sampled action clamped to [0, 1].
            log_prob: (B,) log-probability of the action.
        """
        if obs.dim() == 1:
            obs = obs.unsqueeze(0)

        mean, std = self.forward(obs)

        if deterministic:
            action = mean
            # Log-prob of the mean under the Gaussian
            dist = torch.distributions.Normal(mean, std)
            log_prob = dist.log_prob(action).sum(dim=-1)
        else:
            dist = torch.distributions.Normal(mean, std)
            raw = dist.rsample()  # reparameterised sample
            action = torch.clamp(raw, 0.0, 1.0)
            log_prob = dist.log_prob(raw).sum(dim=-1)

        return action.squeeze(0), log_prob.squeeze(0)

    def evaluate_actions(
        self, obs: torch.Tensor, actions: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Evaluate log-probs and entropy for given obs-action pairs.

        Used during the policy update phase.

        Args:
            obs: (B, obs_dim)
            actions: (B, act_dim)

        Returns:
            log_probs: (B,)
            entropy: (B,)
        """
        mean, std = self.forward(obs)

        # ── NaN guard ────────────────────────────────────────
        # If network weights have diverged, mean/std may contain
        # NaN.  Replace with safe defaults so training can skip
        # this batch gracefully instead of crashing.
        if torch.isnan(mean).any() or torch.isnan(std).any():
            logger.warning("NaN detected in actor forward pass — "
                           "returning zero log-probs")
            batch = obs.shape[0]
            return (
                torch.zeros(batch, device=obs.device),
                torch.zeros(batch, device=obs.device),
            )

        dist = torch.distributions.Normal(mean, std)
        log_probs = dist.log_prob(actions).sum(dim=-1)
        entropy = dist.entropy().sum(dim=-1)
        return log_probs, entropy


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Critic Network
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class GlobalCritic(nn.Module):
    """
    Centralized value function for CTDE.

    Takes the concatenated observations of ALL agents as input
    and produces a single scalar value estimate V(s).

    This network is used only during training.  At deployment,
    only the Actor networks are needed.

    Parameters
    ----------
    global_obs_dim : int
        Sum of all agents' flattened observation dimensions.
    hidden : int
        Hidden layer width (default 512).
    """

    def __init__(self, global_obs_dim: int, hidden: int = 512):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(global_obs_dim, hidden),
            nn.LayerNorm(hidden),
            nn.Tanh(),
            nn.Linear(hidden, hidden // 2),
            nn.LayerNorm(hidden // 2),
            nn.Tanh(),
            nn.Linear(hidden // 2, 1),
        )
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight, gain=1.0)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, global_obs: torch.Tensor) -> torch.Tensor:
        """
        Args:
            global_obs: (B, global_obs_dim)

        Returns:
            value: (B, 1)
        """
        return self.net(global_obs)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Factory
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_networks(
    env,
    hidden_actor: int = 256,
    hidden_critic: int = 512,
    device: str = "cpu",
) -> Tuple[Dict[str, AgentActor], GlobalCritic, int]:
    """
    Build all Actor networks and the GlobalCritic from a SupplyChainEnv.

    Args:
        env: A SupplyChainEnv instance (must have been reset once).
        hidden_actor: Hidden width for actor networks.
        hidden_critic: Hidden width for the critic.
        device: "cpu" or "cuda".

    Returns:
        actors: Dict mapping agent_name → AgentActor on device.
        critic: GlobalCritic on device.
        global_obs_dim: Total flattened dimension across all agents.
    """
    actors: Dict[str, AgentActor] = {}
    global_obs_dim = 0

    for agent_name in env.possible_agents:
        obs_space = env.observation_space(agent_name)
        act_space = env.action_space(agent_name)
        obs_dim = _flatten_space_dim(obs_space)
        act_dim = _flatten_space_dim(act_space)
        global_obs_dim += obs_dim

        actor = AgentActor(obs_dim, act_dim, hidden=hidden_actor).to(device)
        actors[agent_name] = actor

    critic = GlobalCritic(global_obs_dim, hidden=hidden_critic).to(device)

    return actors, critic, global_obs_dim
