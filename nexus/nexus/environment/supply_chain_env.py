"""
PettingZoo ParallelEnv for the NEXUS multi-agent supply chain simulation.

Six specialised agents cooperate to manage a 15-node global logistics
network under stochastic disruptions.  Each timestep = 1 simulated hour.

Agents
------
sentinel   — Risk scoring and early-warning intelligence
navigator  — Dynamic multi-objective routing
guardian   — Circuit-breaker management (node isolation)
stockpile  — Proactive inventory pre-positioning
broker     — Carrier health monitoring and selection
herald     — Stakeholder communication and alert triage

API
---
Implements ``pettingzoo.ParallelEnv`` — all agents act simultaneously.
Compatible with PettingZoo ≥ 1.24 and Gymnasium ≥ 0.29.
"""

from __future__ import annotations

import functools
from copy import deepcopy
from typing import Any, Optional

import numpy as np
from gymnasium import spaces
from pettingzoo import ParallelEnv

from nexus.data import load_json
from nexus.environment.disruption_sampler import DisruptionEngine
from nexus.environment.network_graph import (
    CircuitState,
    SupplyChainNetwork,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Constants
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NUM_NODES = 15
NUM_CARRIERS = 8
NUM_SUPPLIERS = 8
MAX_SHIPMENTS = 30
DEFAULT_EPISODE_LENGTH = 168        # 1 week in simulated hours

# Canonical ordering — every observation vector uses this index mapping
NODE_IDS: list[str] = [
    "shanghai_port", "rotterdam_port", "hamburg_port", "singapore_port",
    "la_port", "frankfurt_dc", "london_dc", "paris_dc", "newyork_dc",
    "chicago_dc", "dubai_hub", "mumbai_hub", "tokyo_hub", "seoul_hub",
    "sydney_dc",
]
NODE_TO_IDX: dict[str, int] = {nid: i for i, nid in enumerate(NODE_IDS)}

CARRIER_IDS: list[str] = [
    "maersk", "msc", "cma_cgm", "hapag_lloyd",
    "one", "fedex", "dhl", "ups",
]
CARRIER_TO_IDX: dict[str, int] = {cid: i for i, cid in enumerate(CARRIER_IDS)}

# Historical per-node disruption frequency (Bayesian prior, empirical)
_HIST_DISRUPTION_FREQ = np.array([
    0.15, 0.10, 0.18, 0.08, 0.20,      # ports
    0.05, 0.07, 0.06, 0.12, 0.09,      # DCs
    0.11, 0.22, 0.07, 0.06, 0.04,      # hubs
], dtype=np.float32)

# Circuit-state encoding  closed=0  open=1  half_open=2
_CIRCUIT_MAP = {"closed": 0.0, "open": 1.0, "half_open": 2.0}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Environment
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SupplyChainEnv(ParallelEnv):
    """
    NEXUS multi-agent supply-chain environment.

    Parameters
    ----------
    render_mode : str | None
        ``"human"`` — textual dashboard to stdout.
        ``"json"``  — returns full state dict.
    max_steps : int
        Episode length in simulated hours (default 168 = 1 week).
    disruption_probability : float
        Per-step probability of a random disruption injection (training
        diversity).  Set to 0 for deterministic demo mode.
    seed : int | None
        RNG seed for reproducibility.
    """

    metadata = {
        "render_modes": ["human", "json"],
        "name": "nexus_supply_chain_v0",
        "is_parallelizable": True,
    }

    def __init__(
        self,
        render_mode: Optional[str] = None,
        max_steps: int = DEFAULT_EPISODE_LENGTH,
        disruption_probability: float = 0.02,
        seed: Optional[int] = None,
    ):
        super().__init__()

        self.render_mode = render_mode
        self.max_steps = max_steps
        self.disruption_probability = disruption_probability
        self._seed = seed
        self._rng = np.random.default_rng(seed)

        self.possible_agents: list[str] = [
            "sentinel", "navigator", "guardian",
            "stockpile", "broker", "herald",
        ]

        # ── state (populated on reset) ─────────────────────────
        self.agents: list[str] = []
        self.network: Optional[SupplyChainNetwork] = None
        self.disruption_engine: Optional[DisruptionEngine] = None
        self.shipments: list[dict] = []
        self.carriers: list[dict] = []
        self.suppliers: list[dict] = []
        self.current_step: int = 0

        # Shared agent-generated state
        self.risk_scores = np.zeros(NUM_NODES, dtype=np.float32)
        self.alert_queue: list[dict] = []
        self._prev_queue_depths = np.zeros(NUM_NODES, dtype=np.float32)
        self._inventory_levels = np.zeros(NUM_NODES, dtype=np.float32)
        self._demand_forecast = np.zeros(NUM_NODES, dtype=np.float32)
        self._episode_metrics: dict[str, Any] = {}

        # ── spaces ─────────────────────────────────────────────
        self._obs_spaces: dict[str, spaces.Dict] = {}
        self._act_spaces: dict[str, spaces.Dict] = {}
        self._build_spaces()

    # ═══════════════════════════════════════════════════════════════
    #  Observation & Action Spaces
    # ═══════════════════════════════════════════════════════════════

    def _build_spaces(self):
        """Define Gymnasium Dict spaces for every agent."""
        f32 = np.float32

        # ── SENTINEL ──────────────────────────────────────────────
        self._obs_spaces["sentinel"] = spaces.Dict({
            "weather_severity":
                spaces.Box(0, 10, (NUM_NODES,), f32),
            "congestion_scores":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "carrier_health":
                spaces.Box(0, 1, (NUM_CARRIERS,), f32),
            "osint_signal_volume":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "supplier_health":
                spaces.Box(0, 1, (NUM_SUPPLIERS,), f32),
            "node_health":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "disruption_active":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "historical_disruption_freq":
                spaces.Box(0, 1, (NUM_NODES,), f32),
        })
        self._act_spaces["sentinel"] = spaces.Dict({
            "risk_scores":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "confidence":
                spaces.Box(0, 1, (NUM_NODES,), f32),
        })

        # ── NAVIGATOR ─────────────────────────────────────────────
        self._obs_spaces["navigator"] = spaces.Dict({
            "node_health":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "risk_overlay":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "circuit_states":
                spaces.Box(0, 2, (NUM_NODES,), f32),
            "shipment_urgency":
                spaces.Box(0, 1, (MAX_SHIPMENTS,), f32),
            "shipment_at_risk":
                spaces.Box(0, 1, (MAX_SHIPMENTS,), f32),
        })
        self._act_spaces["navigator"] = spaces.Dict({
            "reroute_flags":
                spaces.Box(0, 1, (MAX_SHIPMENTS,), f32),
            "urgency_level":
                spaces.Box(0, 1, (MAX_SHIPMENTS,), f32),
        })

        # ── GUARDIAN ──────────────────────────────────────────────
        self._obs_spaces["guardian"] = spaces.Dict({
            "throughput_ratio":
                spaces.Box(0, 2, (NUM_NODES,), f32),
            "dwell_time_ratio":
                spaces.Box(0, 5, (NUM_NODES,), f32),
            "queue_depth_velocity":
                spaces.Box(-1, 1, (NUM_NODES,), f32),
            "error_rate":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "node_health":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "circuit_states":
                spaces.Box(0, 2, (NUM_NODES,), f32),
            "downstream_impact":
                spaces.Box(0, 1, (NUM_NODES,), f32),
        })
        self._act_spaces["guardian"] = spaces.Dict({
            # 0..0.33 ⇒ no change  |  0.33..0.66 ⇒ OPEN  |  0.66..1 ⇒ HALF_OPEN probe
            "circuit_actions":
                spaces.Box(0, 1, (NUM_NODES,), f32),
        })

        # ── STOCKPILE ─────────────────────────────────────────────
        self._obs_spaces["stockpile"] = spaces.Dict({
            "inventory_levels":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "risk_scores":
                spaces.Box(0, 1, (NUM_NODES,), f32),
            "demand_forecast":
                spaces.Box(0, 1, (NUM_NODES,), f32),
        })
        self._act_spaces["stockpile"] = spaces.Dict({
            "transfer_triggers":
                spaces.Box(0, 1, (NUM_NODES,), f32),
        })

        # ── BROKER ────────────────────────────────────────────────
        self._obs_spaces["broker"] = spaces.Dict({
            "carrier_otp":
                spaces.Box(0, 1, (NUM_CARRIERS,), f32),
            "carrier_health":
                spaces.Box(0, 1, (NUM_CARRIERS,), f32),
            "carrier_capacity":
                spaces.Box(0, 1, (NUM_CARRIERS,), f32),
        })
        self._act_spaces["broker"] = spaces.Dict({
            # >0.7 recommend  |  0.3–0.7 neutral  |  <0.3 soft blackout
            "carrier_flags":
                spaces.Box(0, 1, (NUM_CARRIERS,), f32),
        })

        # ── HERALD ────────────────────────────────────────────────
        self._obs_spaces["herald"] = spaces.Dict({
            "active_alerts":
                spaces.Box(0, 1, (MAX_SHIPMENTS,), f32),
            "sla_breach_probability":
                spaces.Box(0, 1, (MAX_SHIPMENTS,), f32),
            "risk_scores":
                spaces.Box(0, 1, (NUM_NODES,), f32),
        })
        self._act_spaces["herald"] = spaces.Dict({
            "alert_priorities":
                spaces.Box(0, 1, (MAX_SHIPMENTS,), f32),
        })

    @functools.lru_cache(maxsize=None)
    def observation_space(self, agent: str) -> spaces.Dict:
        return self._obs_spaces[agent]

    @functools.lru_cache(maxsize=None)
    def action_space(self, agent: str) -> spaces.Dict:
        return self._act_spaces[agent]

    # ═══════════════════════════════════════════════════════════════
    #  Reset
    # ═══════════════════════════════════════════════════════════════

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ) -> tuple[dict[str, dict], dict[str, dict]]:
        """
        Reset environment to initial state.

        Returns (observations, infos) per PettingZoo API.
        """
        if seed is not None:
            self._seed = seed
            self._rng = np.random.default_rng(seed)

        self.agents = list(self.possible_agents)
        self.current_step = 0

        # ── Network ────────────────────────────────────────────
        self.network = SupplyChainNetwork()
        self.disruption_engine = DisruptionEngine(
            self.network, seed=self._seed
        )

        # ── Shipments ──────────────────────────────────────────
        raw = load_json("shipments.json")["shipments"]
        self.shipments = []
        for i, s in enumerate(deepcopy(raw)):
            # Find current position in route
            try:
                route_pos = s["route_planned"].index(s["current_node"])
            except ValueError:
                route_pos = 0
            s.update({
                "idx":                  i,
                "route_position":       route_pos,
                "hours_on_edge":        0,
                "total_delay_hours":    0,
                "rerouted":             False,
                "sla_breached":         False,
                "delivered":            False,
                "elapsed_hours":        s.get("departure_time_hours_ago", 0),
            })
            self.shipments.append(s)

        # ── Carriers ───────────────────────────────────────────
        self.carriers = deepcopy(load_json("carriers.json")["carriers"])

        # ── Suppliers ──────────────────────────────────────────
        self.suppliers = deepcopy(load_json("suppliers.json")["suppliers"])

        # ── Internal state ─────────────────────────────────────
        self.risk_scores = np.zeros(NUM_NODES, dtype=np.float32)
        self.alert_queue = []
        self._prev_queue_depths = np.array(
            [self.network.nodes[nid].current_queue_depth for nid in NODE_IDS],
            dtype=np.float32,
        )
        self._inventory_levels = {
            nid: float(np.clip(0.1 + self._rng.random() * 0.2, 0, 1))
            for nid in NODE_IDS
        }
        self._demand_forecast = {
            nid: float(np.clip(0.25 + self._rng.random() * 0.45, 0, 1))
            for nid in NODE_IDS
        }
        self._episode_metrics = {
            "total_disruptions":      0,
            "sla_breaches":           0,
            "shipments_delivered":    0,
            "total_delay_hours":      0.0,
            "circuit_opens":          0,
            "reroutes":               0,
            "alerts_sent":            0,
            "sentinel_true_pos":      0,
            "sentinel_false_pos":     0,
            "sentinel_predictions":   {},   # keyed by step for O(1) lookup
            "realized_disruptions":   [],
        }

        observations = self._build_observations()
        infos = {agent: {} for agent in self.agents}
        return observations, infos

    # ═══════════════════════════════════════════════════════════════
    #  Step
    # ═══════════════════════════════════════════════════════════════

    def step(
        self,
        actions: dict[str, dict[str, np.ndarray]],
    ) -> tuple[
        dict[str, dict],
        dict[str, float],
        dict[str, bool],
        dict[str, bool],
        dict[str, dict],
    ]:
        """
        Advance the simulation by 1 hour.

        Processing order:
          1. SENTINEL → update risk scores
          2. GUARDIAN → circuit breaker decisions
          3. NAVIGATOR → routing decisions
          4. STOCKPILE → inventory pre-positioning
          5. BROKER → carrier flags
          6. HERALD → alert triage
          7. Advance shipments along routes
          8. Stochastic disruption injection
          9. Disruption lifecycle tick
          10. Recompute node health
          11. Build observations and rewards
        """
        if not self.agents:
            return {}, {}, {}, {}, {}

        self.current_step += 1

        # 1–6: process each agent's actions
        self._process_sentinel(actions.get("sentinel"))
        self._process_guardian(actions.get("guardian"))
        self._process_navigator(actions.get("navigator"))
        self._process_stockpile(actions.get("stockpile"))
        self._process_broker(actions.get("broker"))
        self._process_herald(actions.get("herald"))

        # 7: advance shipment positions
        self._advance_shipments()

        # 8: stochastic disruption (training diversity)
        if self._rng.random() < self.disruption_probability:
            event = self.disruption_engine.sample_disruption(self.current_step)
            self._episode_metrics["total_disruptions"] += 1
            if event.target_node and event.target_node in NODE_TO_IDX:
                self._episode_metrics["realized_disruptions"].append({
                    "step": self.current_step,
                    "node_idx": NODE_TO_IDX[event.target_node],
                    "severity": event.severity,
                })

        # 9: resolve expired disruptions
        self.disruption_engine.tick(self.current_step)

        # 10: recompute health for every node
        for node in self.network.nodes.values():
            node.compute_health()

        # Deplete inventory each step (demand consumption)
        for nid in NODE_IDS:
            self._inventory_levels[nid] = max(0.0, self._inventory_levels[nid] - 0.02)

        # Store queue depths for velocity computation next step
        self._prev_queue_depths = np.array(
            [self.network.nodes[nid].current_queue_depth for nid in NODE_IDS],
            dtype=np.float32,
        )

        # 11: returns
        observations = self._build_observations()
        rewards = self._compute_rewards()

        truncated = self.current_step >= self.max_steps
        terminations = {a: False for a in self.agents}
        truncations = {a: truncated for a in self.agents}

        infos: dict[str, dict] = {}
        for a in self.agents:
            info: dict[str, Any] = {"step": self.current_step}
            if truncated:
                info["episode_metrics"] = self._episode_metrics
            infos[a] = info

        if truncated:
            self.agents = []

        return observations, rewards, terminations, truncations, infos

    # ═══════════════════════════════════════════════════════════════
    #  Observation Builder
    # ═══════════════════════════════════════════════════════════════

    def _build_observations(self) -> dict[str, dict[str, np.ndarray]]:
        """Construct agent-specific observations from the current world state."""
        net = self.network

        # ── shared vectors ────────────────────────────────────
        node_health = np.array(
            [net.nodes[nid].health_score for nid in NODE_IDS], dtype=np.float32
        )
        weather = np.array(
            [net.nodes[nid].weather_severity for nid in NODE_IDS], dtype=np.float32
        )
        congestion = np.array(
            [net.nodes[nid].congestion_score for nid in NODE_IDS], dtype=np.float32
        )
        carrier_health = np.array(
            [c["health_score"] for c in self.carriers], dtype=np.float32
        )
        supplier_health = np.array(
            [s["composite_health_score"] for s in self.suppliers], dtype=np.float32
        )
        circuit_vals = np.array(
            [_CIRCUIT_MAP.get(net.nodes[nid].circuit_state.value, 0.0)
             for nid in NODE_IDS],
            dtype=np.float32,
        )

        # disruption intensity per node (normalised 0-1)
        disruption_flags = np.zeros(NUM_NODES, dtype=np.float32)
        for event in self.disruption_engine.active_disruptions:
            if event.target_node and event.target_node in NODE_TO_IDX:
                idx = NODE_TO_IDX[event.target_node]
                disruption_flags[idx] = max(
                    disruption_flags[idx],
                    min(1.0, event.severity / 10.0),
                )

        # OSINT signal volume (correlated with disruptions + noise)
        osint_noise = self._rng.random(NUM_NODES).astype(np.float32) * 0.08
        osint_volume = np.clip(disruption_flags * 0.85 + osint_noise, 0, 1)

        # ── shipment vectors ──────────────────────────────────
        shipment_urgency = np.zeros(MAX_SHIPMENTS, dtype=np.float32)
        shipment_at_risk = np.zeros(MAX_SHIPMENTS, dtype=np.float32)
        sla_breach_prob = np.zeros(MAX_SHIPMENTS, dtype=np.float32)
        active_alerts = np.zeros(MAX_SHIPMENTS, dtype=np.float32)

        for s in self.shipments:
            i = s["idx"]
            if i >= MAX_SHIPMENTS or s["delivered"]:
                continue

            remaining_sla = max(
                1.0,
                s["sla_deadline_hours"] - s["elapsed_hours"] - self.current_step,
            )

            # urgency increases as SLA deadline approaches
            shipment_urgency[i] = float(np.clip(80.0 / remaining_sla, 0, 1))

            # at-risk if route passes through disrupted / open-circuit node
            for nid in s["route_planned"][s["route_position"]:]:
                if nid in NODE_TO_IDX:
                    nidx = NODE_TO_IDX[nid]
                    if disruption_flags[nidx] > 0.3 or circuit_vals[nidx] == 1.0:
                        shipment_at_risk[i] = 1.0
                        break

            # breach probability from accumulated delay
            sla_breach_prob[i] = float(np.clip(
                s["total_delay_hours"] / max(remaining_sla, 1) * 1.5, 0, 1
            ))

            if shipment_at_risk[i] > 0.5 or sla_breach_prob[i] > 0.4:
                active_alerts[i] = max(shipment_at_risk[i], sla_breach_prob[i])

        # ── GUARDIAN vectors ──────────────────────────────────
        throughput_ratios = np.clip(np.array(
            [net.nodes[nid].throughput_ratio for nid in NODE_IDS],
            dtype=np.float32,
        ), 0.0, 2.0)
        dwell_ratios = np.clip(np.array(
            [net.nodes[nid].dwell_ratio for nid in NODE_IDS],
            dtype=np.float32,
        ), 0.0, 5.0)
        current_qs = np.array(
            [net.nodes[nid].current_queue_depth for nid in NODE_IDS],
            dtype=np.float32,
        )
        capacities = np.array(
            [max(net.nodes[nid]._original_throughput, 1) for nid in NODE_IDS],
            dtype=np.float32,
        )
        queue_velocity = np.clip(
            (current_qs - self._prev_queue_depths) / capacities, -1, 1
        ).astype(np.float32)

        error_rate = np.clip(1.0 - node_health, 0, 1).astype(np.float32)

        # downstream impact: fraction of active shipments routing through node
        downstream_impact = np.zeros(NUM_NODES, dtype=np.float32)
        total_active = sum(1 for s in self.shipments if not s["delivered"])
        if total_active > 0:
            for s in self.shipments:
                if s["delivered"]:
                    continue
                for nid in s["route_planned"]:
                    if nid in NODE_TO_IDX:
                        downstream_impact[NODE_TO_IDX[nid]] += 1.0
            downstream_impact = np.clip(
                downstream_impact / total_active, 0, 1
            ).astype(np.float32)

        # ── Inventory / Demand ────────────────────────────────
        inv = np.array(
            [self._inventory_levels[nid] for nid in NODE_IDS], dtype=np.float32
        )
        demand = np.array(
            [self._demand_forecast[nid] for nid in NODE_IDS], dtype=np.float32
        )

        # ── Carrier vectors ───────────────────────────────────
        carrier_otp = np.array(
            [c["otp_score"] for c in self.carriers], dtype=np.float32
        )
        carrier_cap = np.array(
            [c["capacity_reliability"] for c in self.carriers], dtype=np.float32
        )

        # ── assemble ──────────────────────────────────────────
        return {
            "sentinel": {
                "weather_severity": weather,
                "congestion_scores": congestion,
                "carrier_health": carrier_health,
                "osint_signal_volume": osint_volume,
                "supplier_health": supplier_health,
                "node_health": node_health,
                "disruption_active": disruption_flags,
                "historical_disruption_freq": _HIST_DISRUPTION_FREQ.copy(),
            },
            "navigator": {
                "node_health": node_health,
                "risk_overlay": self.risk_scores.copy(),
                "circuit_states": circuit_vals,
                "shipment_urgency": shipment_urgency,
                "shipment_at_risk": shipment_at_risk,
            },
            "guardian": {
                "throughput_ratio": throughput_ratios,
                "dwell_time_ratio": dwell_ratios,
                "queue_depth_velocity": queue_velocity,
                "error_rate": error_rate,
                "node_health": node_health,
                "circuit_states": circuit_vals,
                "downstream_impact": downstream_impact,
            },
            "stockpile": {
                "inventory_levels": inv,
                "risk_scores": self.risk_scores.copy(),
                "demand_forecast": demand,
            },
            "broker": {
                "carrier_otp": carrier_otp,
                "carrier_health": carrier_health,
                "carrier_capacity": carrier_cap,
            },
            "herald": {
                "active_alerts": active_alerts,
                "sla_breach_probability": sla_breach_prob,
                "risk_scores": self.risk_scores.copy(),
            },
        }

    # ═══════════════════════════════════════════════════════════════
    #  Action Processing
    # ═══════════════════════════════════════════════════════════════

    def _process_sentinel(self, action: Optional[dict]) -> None:
        """Update global risk scores from SENTINEL's assessment."""
        if action is None:
            return
        scores = action.get("risk_scores")
        confidence = action.get("confidence")
        if scores is None:
            return
        if confidence is None:
            confidence = np.ones(NUM_NODES, dtype=np.float32) * 0.5

        # Exponential moving average blend
        alpha = 0.7
        self.risk_scores = np.clip(
            alpha * scores + (1 - alpha) * self.risk_scores, 0, 1,
        ).astype(np.float32)

        # Record predictions for reward scoring (keyed by step)
        step_preds = []
        for i in range(NUM_NODES):
            if scores[i] > 0.65:
                step_preds.append({
                    "node_idx":       i,
                    "predicted_risk": float(scores[i]),
                    "confidence":     float(confidence[i]),
                })
        if step_preds:
            self._episode_metrics["sentinel_predictions"][self.current_step] = step_preds

    def _process_guardian(self, action: Optional[dict]) -> None:
        """Process circuit-breaker state transitions."""
        if action is None:
            return
        acts = action.get("circuit_actions")
        if acts is None:
            return

        for i, val in enumerate(acts):
            nid = NODE_IDS[i]
            node = self.network.nodes[nid]

            if val > 0.66:
                # HALF-OPEN probe: only valid if currently OPEN
                if node.circuit_state == CircuitState.OPEN:
                    if node.health_score > 0.35:
                        self.network.set_circuit_state(nid, CircuitState.HALF_OPEN)

            elif val > 0.33:
                # OPEN circuit: only if currently CLOSED and health is bad
                if node.circuit_state == CircuitState.CLOSED:
                    if node.health_score < 0.35:
                        self.network.set_circuit_state(nid, CircuitState.OPEN)
                        self._episode_metrics["circuit_opens"] += 1
                # Auto-close HALF_OPEN if health has recovered
                elif node.circuit_state == CircuitState.HALF_OPEN:
                    if node.health_score > 0.70:
                        self.network.set_circuit_state(nid, CircuitState.CLOSED)

    def _process_navigator(self, action: Optional[dict]) -> None:
        """Re-route flagged shipments around disrupted nodes."""
        if action is None:
            return
        flags = action.get("reroute_flags")
        if flags is None:
            return

        for i, flag in enumerate(flags):
            if i >= len(self.shipments):
                break
            s = self.shipments[i]
            if flag <= 0.5 or s["delivered"]:
                continue

            origin = s["current_node"]
            dest = s["destination"]
            new_route, cost = self.network.dijkstra(
                origin, dest, "transit_hours", avoid_open_circuits=True,
            )
            if new_route and len(new_route) > 1 and new_route != s["route_planned"][s["route_position"]:]:
                s["route_planned"] = new_route
                s["route_position"] = 0
                s["hours_on_edge"] = 0
                s["rerouted"] = True
                self._episode_metrics["reroutes"] += 1

    def _process_stockpile(self, action: Optional[dict]) -> None:
        """Pre-position inventory at nodes flagged for risk."""
        if action is None:
            return
        triggers = action.get("transfer_triggers")
        if triggers is None:
            return

        for i, trigger in enumerate(triggers):
            if trigger > 0.5:
                nid = NODE_IDS[i]
                self._inventory_levels[nid] = min(
                    1.0, self._inventory_levels[nid] + 0.08,
                )

    def _process_broker(self, action: Optional[dict]) -> None:
        """Set carrier blackout flags based on health assessment."""
        if action is None:
            return
        flags = action.get("carrier_flags")
        if flags is None:
            return

        for i, flag in enumerate(flags):
            if i >= len(self.carriers):
                break
            self.carriers[i]["blackout_flag"] = bool(flag < 0.3)

    def _process_herald(self, action: Optional[dict]) -> None:
        """Triage alerts and enqueue high-priority notifications."""
        if action is None:
            return
        priorities = action.get("alert_priorities")
        if priorities is None:
            return

        # Trim queue to only current-step entries (prevents O(n²) growth)
        self.alert_queue = [
            a for a in self.alert_queue if a["step"] == self.current_step - 1
        ] if self.alert_queue else []

        for i, p in enumerate(priorities):
            if p > 0.5 and i < len(self.shipments):
                self.alert_queue.append({
                    "step":        self.current_step,
                    "shipment_id": self.shipments[i]["shipment_id"],
                    "priority":    float(p),
                })
                self._episode_metrics["alerts_sent"] += 1

    # ═══════════════════════════════════════════════════════════════
    #  Shipment Simulation
    # ═══════════════════════════════════════════════════════════════

    def _advance_shipments(self) -> None:
        """Move every active shipment 1 hour along its planned route."""
        for s in self.shipments:
            if s["delivered"]:
                continue

            route = s["route_planned"]
            pos = s["route_position"]

            # Already at final node
            if pos >= len(route) - 1:
                s["delivered"] = True
                s["status"] = "delivered"
                self._episode_metrics["shipments_delivered"] += 1
                continue

            from_nid = route[pos]
            to_nid = route[pos + 1]

            # Blocked at an open-circuit node?
            from_node = self.network.nodes.get(from_nid)
            if from_node and from_node.circuit_state == CircuitState.OPEN:
                s["total_delay_hours"] += 1
                s["status"] = "blocked"
                self._episode_metrics["total_delay_hours"] += 1
                # SLA check
                self._check_sla(s)
                continue

            # Get edge (check both for missing edges)
            edge = self.network.get_edge(from_nid, to_nid)
            if edge is None:
                # Route broken — shipment stalled
                s["total_delay_hours"] += 1
                s["status"] = "route_error"
                self._episode_metrics["total_delay_hours"] += 1
                self._check_sla(s)
                continue

            s["hours_on_edge"] += 1
            s["status"] = "in_transit"

            # Has the shipment completed this edge?
            if s["hours_on_edge"] >= edge.transit_hours:
                s["route_position"] += 1
                s["hours_on_edge"] = 0
                s["current_node"] = to_nid

                if s["route_position"] >= len(route) - 1:
                    s["delivered"] = True
                    s["status"] = "delivered"
                    self._episode_metrics["shipments_delivered"] += 1
                else:
                    s["status"] = "at_node"

            self._check_sla(s)

    def _check_sla(self, s: dict) -> None:
        """Mark SLA breach if elapsed time exceeds deadline."""
        if s["sla_breached"] or s["delivered"]:
            return
        total_elapsed = s.get("elapsed_hours", 0) + self.current_step
        if total_elapsed > s["sla_deadline_hours"]:
            s["sla_breached"] = True
            self._episode_metrics["sla_breaches"] += 1

    # ═══════════════════════════════════════════════════════════════
    #  Reward Computation
    # ═══════════════════════════════════════════════════════════════

    def _compute_rewards(self) -> dict[str, float]:
        """
        Dense per-step reward with team component for HAPPO training.

        Structure: reward = Individual(70%) + Team(30%)

        Team reward (shared by all agents):
          + avg node health (keep network healthy)
          - new SLA breaches this step
          + shipments progressing (not blocked)

        Individual rewards:
          SENTINEL : risk accuracy + early warning − false alarms
          NAVIGATOR: −delay + delivery + reroute bonus
          GUARDIAN : justified opens − false opens + cascade containment
          STOCKPILE: pre-positioning accuracy
          BROKER   : correct blackout decisions
          HERALD   : alert accuracy − alarm fatigue
        """

        # ── TEAM REWARD (shared, dense per-step) ──────────────
        avg_health = float(np.mean([
            self.network.nodes[nid].health_score for nid in NODE_IDS
        ]))
        # Count shipments progressing (not blocked, not delivered)
        progressing = sum(
            1 for s in self.shipments
            if not s["delivered"] and s["status"] == "in_transit"
        )
        total_active = max(1, sum(
            1 for s in self.shipments if not s["delivered"]
        ))
        progress_ratio = progressing / total_active

        # Count new SLA breaches THIS step only
        new_breaches = sum(
            1 for s in self.shipments
            if s["sla_breached"] and not s["delivered"]
            and (s.get("elapsed_hours", 0) + self.current_step)
                <= s["sla_deadline_hours"] + 1
        )

        team_reward = (
            + 0.02 * avg_health          # keep network healthy
            + 0.01 * progress_ratio      # reward forward movement
            - 0.10 * new_breaches        # penalise breaches immediately
        )

        # ── INDIVIDUAL REWARDS ────────────────────────────────
        individual: dict[str, float] = {}

        # ── SENTINEL ──────────────────────────────────────────
        r_sentinel = 0.0
        step_preds = self._episode_metrics["sentinel_predictions"].get(
            self.current_step, []
        )
        for pred in step_preds:
            nidx = pred["node_idx"]
            actually_disrupted = any(
                e.target_node == NODE_IDS[nidx]
                for e in self.disruption_engine.active_disruptions
            )
            if actually_disrupted:
                r_sentinel += 0.15 * pred["confidence"]
                self._episode_metrics["sentinel_true_pos"] += 1
            else:
                r_sentinel -= 0.05
                self._episode_metrics["sentinel_false_pos"] += 1

        # Early-warning bonus (dense)
        for event in self.disruption_engine.active_disruptions:
            if event.target_node and event.target_node in NODE_TO_IDX:
                idx = NODE_TO_IDX[event.target_node]
                if self.risk_scores[idx] > 0.65:
                    r_sentinel += 0.02
        individual["sentinel"] = r_sentinel

        # ── NAVIGATOR ─────────────────────────────────────────
        r_nav = 0.0
        for s in self.shipments:
            if s["delivered"] and not s["sla_breached"]:
                r_nav += 0.05           # per-delivery bonus (dense)
            elif s["delivered"] and s["sla_breached"]:
                r_nav -= 0.03
            elif not s["delivered"]:
                r_nav -= s["total_delay_hours"] * 0.0005
            if s["rerouted"] and s["delivered"] and not s["sla_breached"]:
                r_nav += 0.04           # successful reroute
        individual["navigator"] = r_nav

        # ── GUARDIAN ──────────────────────────────────────────
        r_guard = 0.0
        for node in self.network.nodes.values():
            if node.circuit_state == CircuitState.OPEN:
                if node.health_score < 0.35:
                    r_guard += 0.05     # justified isolation
                else:
                    r_guard -= 0.10     # false alarm (costly)
                for dn_id in self.network.get_downstream_nodes(node.id):
                    dn = self.network.nodes.get(dn_id)
                    if dn and dn.health_score > 0.7:
                        r_guard += 0.01
        individual["guardian"] = r_guard

        # ── STOCKPILE ─────────────────────────────────────────
        r_stock = 0.0
        for i, nid in enumerate(NODE_IDS):
            at_risk = self.risk_scores[i] > 0.5
            well_stocked = self._inventory_levels[nid] > 0.5
            if at_risk and well_stocked:
                r_stock += 0.02
            elif at_risk and not well_stocked:
                r_stock -= 0.04
            elif not at_risk and well_stocked:
                r_stock -= 0.002
        individual["stockpile"] = r_stock

        # ── BROKER ────────────────────────────────────────────
        r_broker = 0.0
        for c in self.carriers:
            if c.get("blackout_flag"):
                if c["health_score"] < 0.5:
                    r_broker += 0.04
                elif c["health_score"] > 0.8:
                    r_broker -= 0.06
            else:
                if c["health_score"] >= 0.5:
                    r_broker += 0.01
        individual["broker"] = r_broker

        # ── HERALD ────────────────────────────────────────────
        r_herald = 0.0
        alerted_ids = {
            a["shipment_id"]
            for a in self.alert_queue
            if a["step"] == self.current_step
        }
        for s in self.shipments:
            sid = s["shipment_id"]
            if s["sla_breached"] and sid in alerted_ids:
                r_herald += 0.04
            elif s["sla_breached"] and sid not in alerted_ids:
                r_herald -= 0.06
            elif not s["sla_breached"] and sid in alerted_ids:
                r_herald -= 0.005
        individual["herald"] = r_herald

        # ── BLEND: 70% individual + 30% team ──────────────────
        rewards: dict[str, float] = {}
        for agent_name in self.possible_agents:
            ind = individual.get(agent_name, 0.0)
            rewards[agent_name] = float(
                np.clip(0.70 * ind + 0.30 * team_reward, -1.0, 1.0)
            )

        return rewards

    # ═══════════════════════════════════════════════════════════════
    #  Render / Serialise
    # ═══════════════════════════════════════════════════════════════

    def render(self) -> Optional[dict]:
        """Render the environment according to ``render_mode``."""
        if self.render_mode == "json":
            return self.get_state()
        elif self.render_mode == "human":
            self._render_human()
        return None

    def _render_human(self) -> None:
        """Pretty-print a textual dashboard to stdout."""
        de = self.disruption_engine
        net = self.network
        m = self._episode_metrics

        open_circuits = sum(
            1 for n in net.nodes.values()
            if n.circuit_state == CircuitState.OPEN
        )
        half_open = sum(
            1 for n in net.nodes.values()
            if n.circuit_state == CircuitState.HALF_OPEN
        )

        print(f"\n{'━' * 64}")
        print(f"  NEXUS Supply Chain  │  Step {self.current_step:>4}/{self.max_steps}")
        print(f"{'━' * 64}")
        print(
            f"  Disruptions: {len(de.active_disruptions)} active  │  "
            f"Circuits: {open_circuits} open, {half_open} half-open"
        )
        print(
            f"  Delivered: {m['shipments_delivered']}/{len(self.shipments)}  │  "
            f"SLA Breaches: {m['sla_breaches']}  │  "
            f"Reroutes: {m['reroutes']}"
        )
        print(f"  Total Delay: {m['total_delay_hours']:.0f}h  │  "
              f"Alerts: {m['alerts_sent']}")
        print(f"{'─' * 64}")

        for nid in NODE_IDS:
            node = net.nodes[nid]
            h = node.health_score
            led = "🟢" if h > 0.7 else ("🟡" if h > 0.4 else "🔴")
            cs = {"closed": "⬛", "open": "🔴", "half_open": "🟡"
                  }[node.circuit_state.value]
            risk = self.risk_scores[NODE_TO_IDX[nid]]
            risk_str = f"risk={risk:.2f}" if risk > 0.1 else ""
            print(
                f"  {led}{cs} {node.name:40s} "
                f"hp={h:.2f}  {risk_str}"
            )

        if de.active_disruptions:
            print(f"{'─' * 64}")
            print("  Active Disruptions:")
            for ev in de.active_disruptions:
                print(f"    [{ev.event_id}] {ev.disruption_type.value:12s} "
                      f"sev={ev.severity:.1f}  +{ev.hours_active}h")
        print(f"{'━' * 64}\n")

    def get_state(self) -> dict:
        """Full world state as a JSON-serialisable dict (for API layer)."""
        return {
            "step": self.current_step,
            "max_steps": self.max_steps,
            "network": self.network.to_dict(),
            "shipments": [self._shipment_dict(s) for s in self.shipments],
            "carriers": self.carriers,
            "suppliers": self.suppliers,
            "risk_scores": {
                NODE_IDS[i]: float(self.risk_scores[i])
                for i in range(NUM_NODES)
            },
            "active_disruptions": self.disruption_engine.get_active_events(),
            "alert_queue": self.alert_queue[-50:],
            "inventory_levels": dict(self._inventory_levels),
            "metrics": self._episode_metrics,
        }

    @staticmethod
    def _shipment_dict(s: dict) -> dict:
        """Clean shipment dict for serialisation (drop internal fields)."""
        return {
            "shipment_id":       s["shipment_id"],
            "origin":            s["origin"],
            "destination":       s["destination"],
            "cargo_type":        s["cargo_type"],
            "value_usd":         s["value_usd"],
            "weight_tonnes":     s["weight_tonnes"],
            "sla_deadline_hours": s["sla_deadline_hours"],
            "current_node":      s["current_node"],
            "current_carrier":   s["current_carrier"],
            "route_planned":     s["route_planned"],
            "status":            s["status"],
            "priority_tier":     s["priority_tier"],
            "customer_tier":     s["customer_tier"],
            "total_delay_hours": s["total_delay_hours"],
            "rerouted":          s["rerouted"],
            "sla_breached":      s["sla_breached"],
            "delivered":         s["delivered"],
        }

    def close(self) -> None:
        """No-op clean-up (no GPU / file handles to release)."""
        pass
