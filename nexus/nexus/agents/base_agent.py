"""
Base agent interface for all NEXUS MARL agents.

Every agent must produce *explainable* decisions — each action
includes a ``reasoning`` field in plain English so that judges
(and operators) can understand what the agent did and why.

Design Principles
-----------------
1. **Observe → Decide → Explain**: every cycle produces both an
   action and a human-readable justification.
2. **Stateful**: agents maintain internal state across timesteps
   (sliding windows, baselines, history) to detect trends.
3. **Environment-Agnostic Actions**: agents output numpy arrays
   conforming to their Gymnasium action space, but also provide
   a structured ``AgentDecision`` for the API/UI layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Decision Structures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class AgentDecision:
    """
    A single structured decision produced by an agent.

    Attributes
    ----------
    agent_name : str
        Which agent produced this decision (e.g. "SENTINEL").
    action_type : str
        Category of action (e.g. "risk_flag", "circuit_open", "reroute").
    target : str
        What the action affects (node ID, shipment ID, carrier ID, etc.).
    details : dict
        Structured payload specific to the action type.
    reasoning : str
        Plain-English explanation of *why* this action was taken.
        This is the most important field for demo explainability.
    confidence : float
        Agent's self-assessed confidence in this decision (0-1).
    priority : float
        Urgency/importance score (0-1).
    timestamp_step : int
        Simulation step at which the decision was made.
    """
    agent_name: str
    action_type: str
    target: str
    details: dict = field(default_factory=dict)
    reasoning: str = ""
    confidence: float = 0.5
    priority: float = 0.5
    timestamp_step: int = 0

    def to_dict(self) -> dict:
        return {
            "agent": self.agent_name,
            "action_type": self.action_type,
            "target": self.target,
            "details": self.details,
            "reasoning": self.reasoning,
            "confidence": round(self.confidence, 4),
            "priority": round(self.priority, 4),
            "step": self.timestamp_step,
        }


@dataclass
class AgentOutput:
    """
    Complete output from a single agent step.

    Contains both the raw action (numpy arrays for the env)
    and the structured decisions (for the API/UI layer).
    """
    action: dict[str, np.ndarray]       # Gymnasium action-space dict
    decisions: list[AgentDecision]       # Structured decisions with reasoning
    summary: str = ""                    # One-line summary of this step

    @property
    def has_actions(self) -> bool:
        return len(self.decisions) > 0

    def to_dict(self) -> dict:
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "summary": self.summary,
            "num_actions": len(self.decisions),
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Base Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class BaseAgent(ABC):
    """
    Abstract base class for all NEXUS MARL agents.

    Subclasses must implement:
      • ``observe(obs)``  — ingest a new observation from the env
      • ``act()``         — produce an ``AgentOutput``
      • ``reset()``       — reset internal state for a new episode

    The base class provides:
      • Decision history tracking
      • Step counter
      • Convenience methods for building decisions
    """

    def __init__(self, name: str):
        self.name = name.upper()
        self.step_count: int = 0
        self.decision_history: list[AgentDecision] = []
        self._last_observation: Optional[dict[str, np.ndarray]] = None

    # ── Abstract Interface ────────────────────────────────────────

    @abstractmethod
    def observe(self, obs: dict[str, np.ndarray]) -> None:
        """
        Ingest a new observation from the environment.

        Args:
            obs: Dict of numpy arrays conforming to this agent's
                 observation space.
        """
        ...

    @abstractmethod
    def act(self) -> AgentOutput:
        """
        Produce an action + structured decisions based on the
        most recent observation.

        Returns:
            AgentOutput containing both raw action arrays and
            explainable decisions.
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset all internal state for a new episode."""
        ...

    # ── Convenience Methods ───────────────────────────────────────

    def step(self, obs: dict[str, np.ndarray]) -> AgentOutput:
        """
        Full observe → act cycle.  Tracks step count and history.

        Args:
            obs: Environment observation for this agent.

        Returns:
            AgentOutput with action arrays and decisions.
        """
        self.step_count += 1
        self._last_observation = obs
        self.observe(obs)
        output = self.act()

        # Stamp step number on all decisions
        for d in output.decisions:
            d.timestamp_step = self.step_count

        # Append to history (keep last 500 decisions)
        self.decision_history.extend(output.decisions)
        if len(self.decision_history) > 500:
            self.decision_history = self.decision_history[-500:]

        return output

    def make_decision(
        self,
        action_type: str,
        target: str,
        details: dict,
        reasoning: str,
        confidence: float = 0.5,
        priority: float = 0.5,
    ) -> AgentDecision:
        """Helper to build a decision with this agent's name pre-filled."""
        return AgentDecision(
            agent_name=self.name,
            action_type=action_type,
            target=target,
            details=details,
            reasoning=reasoning,
            confidence=confidence,
            priority=priority,
            timestamp_step=self.step_count,
        )

    def get_recent_decisions(self, n: int = 10) -> list[AgentDecision]:
        """Return the last *n* decisions."""
        return self.decision_history[-n:]

    def get_decisions_for_target(self, target: str) -> list[AgentDecision]:
        """Return all historical decisions targeting a specific entity."""
        return [d for d in self.decision_history if d.target == target]
