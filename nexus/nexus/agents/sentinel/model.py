"""
SENTINEL — Risk Assessment Agent for NEXUS MARL system.

The first line of defence: fuses five signal categories into
per-node risk scores with confidence intervals, then produces
the ``risk_scores`` and ``confidence`` action arrays consumed
by all other agents.

Signal Fusion Weights
---------------------
  25 % Weather/environmental
  25 % OSINT Dark Signal Intelligence
  20 % Supplier financial health
  15 % Congestion / operational
  15 % Geopolitical / carrier

Risk Thresholds
---------------
  Amber : risk > 0.55  (elevated monitoring)
  Red   : risk > 0.75  (immediate action required)

Integration
-----------
SENTINEL observes → produces ``risk_scores`` →
  • NAVIGATOR reads risk overlay to reroute shipments
  • GUARDIAN reads risk to decide circuit-breaker opens
  • STOCKPILE reads risk to pre-position inventory
  • HERALD reads risk to prioritise alerts
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from nexus.agents.base_agent import AgentOutput, BaseAgent
from nexus.agents.sentinel.financial import SupplierHealthRadar
from nexus.agents.sentinel.osint import DarkSignalIntelligence
from nexus.environment.supply_chain_env import (
    CARRIER_IDS,
    NODE_IDS,
    NODE_TO_IDX,
    NUM_CARRIERS,
    NUM_NODES,
    NUM_SUPPLIERS,
)

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Hyperparameters
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Signal category weights (sum to 1.0)
SIGNAL_WEIGHTS = {
    "weather":       0.25,
    "osint":         0.25,
    "supplier":      0.20,
    "congestion":    0.15,
    "geopolitical":  0.15,
}

# Risk thresholds
AMBER_THRESHOLD = 0.55
RED_THRESHOLD = 0.75

# Exponential moving average decay for risk score smoothing
EMA_ALPHA = 0.6

# Minimum confidence for a risk flag to be emitted as a decision
MIN_FLAG_CONFIDENCE = 0.40

# How many steps of historical risk to keep per node
RISK_HISTORY_LENGTH = 48


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SENTINEL Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SentinelAgent(BaseAgent):
    """
    NEXUS SENTINEL — risk scoring and early-warning agent.

    Each timestep:
      1. Ingests env observation (weather, congestion, carrier health, etc.)
      2. Runs OSINT analysis and supplier radar (lazy-loaded asynchronously)
      3. Fuses all signals into per-node ``risk_scores`` with ``confidence``
      4. Emits structured ``AgentDecision`` objects with full reasoning

    Parameters
    ----------
    use_gemini : bool
        Whether to enable Gemini API for OSINT post classification.
    scan_interval : int
        Run expensive OSINT / supplier scans every N steps (default 6 = 6h).
    """

    def __init__(
        self,
        use_gemini: bool = False,
        scan_interval: int = 6,
    ):
        super().__init__("SENTINEL")

        # Sub-modules
        self.osint = DarkSignalIntelligence(use_gemini=use_gemini)
        self.financial_radar = SupplierHealthRadar()

        # Configuration
        self.scan_interval = scan_interval

        # ── Per-node state ──
        self._weather_risk = np.zeros(NUM_NODES, dtype=np.float32)
        self._osint_risk = np.zeros(NUM_NODES, dtype=np.float32)
        self._supplier_risk = np.zeros(NUM_NODES, dtype=np.float32)
        self._congestion_risk = np.zeros(NUM_NODES, dtype=np.float32)
        self._geopolitical_risk = np.zeros(NUM_NODES, dtype=np.float32)

        # Composite outputs (EMA-smoothed)
        self._risk_scores = np.zeros(NUM_NODES, dtype=np.float32)
        self._confidence = np.ones(NUM_NODES, dtype=np.float32) * 0.5

        # History for trend detection
        self._risk_history: dict[int, list[float]] = {
            i: [] for i in range(NUM_NODES)
        }

        # Latest observation
        self._obs: Optional[dict[str, np.ndarray]] = None

        # OSINT / supplier scan cache
        self._last_osint_report = None
        self._last_financial_report = None

    # ── BaseAgent Interface ───────────────────────────────────────

    def observe(self, obs: dict[str, np.ndarray]) -> None:
        """Ingest a new observation from the SENTINEL observation space."""
        self._obs = obs

    def act(self) -> AgentOutput:
        """
        Fuse all signal sources and produce risk scores.

        Returns AgentOutput with:
          - action["risk_scores"]: shape (15,) per-node risk 0-1
          - action["confidence"]: shape (15,) per-node confidence 0-1
          - decisions: list of AgentDecision for flagged nodes
        """
        if self._obs is None:
            return AgentOutput(
                action={
                    "risk_scores": np.zeros(NUM_NODES, dtype=np.float32),
                    "confidence": np.ones(NUM_NODES, dtype=np.float32) * 0.5,
                },
                decisions=[],
                summary="SENTINEL: no observation received, returning baseline.",
            )

        # ── Step 1: Extract raw signals from observation ──────
        self._extract_weather_risk()
        self._extract_congestion_risk()
        self._extract_geopolitical_risk()

        # ── Step 2: Run expensive scans periodically ──────────
        if self.step_count % self.scan_interval == 1 or self.step_count <= 1:
            self._run_osint_scan()
            self._run_financial_scan()

        # ── Step 3: Fuse into composite risk ──────────────────
        raw_composite = (
            SIGNAL_WEIGHTS["weather"] * self._weather_risk
            + SIGNAL_WEIGHTS["osint"] * self._osint_risk
            + SIGNAL_WEIGHTS["supplier"] * self._supplier_risk
            + SIGNAL_WEIGHTS["congestion"] * self._congestion_risk
            + SIGNAL_WEIGHTS["geopolitical"] * self._geopolitical_risk
        )
        raw_composite = np.clip(raw_composite, 0, 1).astype(np.float32)

        # ── Step 4: EMA smoothing ─────────────────────────────
        self._risk_scores = (
            EMA_ALPHA * raw_composite
            + (1 - EMA_ALPHA) * self._risk_scores
        ).astype(np.float32)

        # ── Step 5: Compute confidence ────────────────────────
        self._compute_confidence(raw_composite)

        # ── Step 6: Update history ────────────────────────────
        for i in range(NUM_NODES):
            self._risk_history[i].append(float(self._risk_scores[i]))
            if len(self._risk_history[i]) > RISK_HISTORY_LENGTH:
                self._risk_history[i] = (
                    self._risk_history[i][-RISK_HISTORY_LENGTH:]
                )

        # ── Step 7: Generate decisions for flagged nodes ──────
        decisions = self._generate_decisions()

        # Action for the environment
        action = {
            "risk_scores": self._risk_scores.copy(),
            "confidence": self._confidence.copy(),
        }

        # Summary
        n_amber = int(np.sum(self._risk_scores > AMBER_THRESHOLD))
        n_red = int(np.sum(self._risk_scores > RED_THRESHOLD))
        summary = (
            f"SENTINEL step {self.step_count}: "
            f"{n_red} red, {n_amber} amber risk flags. "
            f"Max risk: {NODE_IDS[int(np.argmax(self._risk_scores))]} "
            f"({float(np.max(self._risk_scores)):.2f})"
        )

        return AgentOutput(
            action=action,
            decisions=decisions,
            summary=summary,
        )

    def reset(self) -> None:
        """Reset all internal state for a new episode."""
        self._weather_risk = np.zeros(NUM_NODES, dtype=np.float32)
        self._osint_risk = np.zeros(NUM_NODES, dtype=np.float32)
        self._supplier_risk = np.zeros(NUM_NODES, dtype=np.float32)
        self._congestion_risk = np.zeros(NUM_NODES, dtype=np.float32)
        self._geopolitical_risk = np.zeros(NUM_NODES, dtype=np.float32)
        self._risk_scores = np.zeros(NUM_NODES, dtype=np.float32)
        self._confidence = np.ones(NUM_NODES, dtype=np.float32) * 0.5
        self._risk_history = {i: [] for i in range(NUM_NODES)}
        self._obs = None
        self._last_osint_report = None
        self._last_financial_report = None
        self.step_count = 0
        self.decision_history.clear()
        self.osint.clear_cache()

    # ── Signal Extraction ─────────────────────────────────────────

    def _extract_weather_risk(self) -> None:
        """
        Convert weather severity (0-10) to normalised risk (0-1).
        Non-linear: severity 5 → risk 0.35, severity 8 → risk 0.75.
        """
        weather = self._obs["weather_severity"]  # shape (15,)
        # Sigmoid-like transformation: risk = 1 / (1 + exp(-0.6*(sev - 5)))
        self._weather_risk = (
            1.0 / (1.0 + np.exp(-0.6 * (weather - 5.0)))
        ).astype(np.float32)

    def _extract_congestion_risk(self) -> None:
        """
        Fuse congestion score (0-1) with reported node health.
        """
        congestion = self._obs["congestion_scores"]    # (15,)
        node_health = self._obs["node_health"]          # (15,)
        disruptions = self._obs["disruption_active"]    # (15,)

        # Congestion risk = blend of direct congestion + inverse health
        self._congestion_risk = np.clip(
            0.5 * congestion
            + 0.3 * (1.0 - node_health)
            + 0.2 * disruptions,
            0, 1,
        ).astype(np.float32)

    def _extract_geopolitical_risk(self) -> None:
        """
        Carrier health acts as proxy for geopolitical/operational risk.
        Low carrier health suggests lane disruptions.
        """
        carrier_health = self._obs["carrier_health"]    # (8,)

        # Average inverse carrier health → global geo risk
        avg_carrier_risk = 1.0 - float(np.mean(carrier_health))

        # Distribute to all nodes, weighted by historical frequency
        hist_freq = self._obs["historical_disruption_freq"]  # (15,)
        self._geopolitical_risk = np.clip(
            avg_carrier_risk * hist_freq * 3.0,
            0, 1,
        ).astype(np.float32)

    # ── OSINT Scan ────────────────────────────────────────────────

    def _run_osint_scan(self) -> None:
        """Run the Dark Signal Intelligence pipeline."""
        try:
            report = self.osint.analyse()
            self._last_osint_report = report

            # Convert triggered clusters to per-node risk
            osint_risk = np.zeros(NUM_NODES, dtype=np.float32)
            for cluster in report.clusters:
                if cluster.node_id in NODE_TO_IDX:
                    idx = NODE_TO_IDX[cluster.node_id]
                    # Risk proportional to sigma score, capped at 1.0
                    if cluster.is_triggered:
                        osint_risk[idx] = min(
                            1.0,
                            cluster.sigma_score / (2.5 * 2)
                            + cluster.avg_confidence * 0.3,
                        )
                    else:
                        osint_risk[idx] = min(
                            0.4,
                            cluster.total_severity_weight * 0.1,
                        )

            self._osint_risk = osint_risk

        except Exception as exc:
            logger.warning("OSINT scan failed: %s", exc)

    # ── Financial Scan ────────────────────────────────────────────

    def _run_financial_scan(self) -> None:
        """Run the Supplier Financial Health Radar."""
        try:
            report = self.financial_radar.scan()
            self._last_financial_report = report

            # Convert supplier health to per-node risk
            node_risk_map = self.financial_radar.get_node_risk_contribution()
            supplier_risk = np.zeros(NUM_NODES, dtype=np.float32)
            for node_id, risk in node_risk_map.items():
                if node_id in NODE_TO_IDX:
                    supplier_risk[NODE_TO_IDX[node_id]] = risk

            self._supplier_risk = supplier_risk

        except Exception as exc:
            logger.warning("Financial scan failed: %s", exc)

    # ── Confidence Computation ────────────────────────────────────

    def _compute_confidence(self, raw_composite: np.ndarray) -> None:
        """
        Compute per-node confidence as a function of:
          - Signal agreement (how many sources agree)
          - History length (more history → more confident)
          - OSINT cluster confidence (if available)
        """
        for i in range(NUM_NODES):
            # Count how many signal sources agree on elevated risk
            signals = [
                self._weather_risk[i],
                self._osint_risk[i],
                self._supplier_risk[i],
                self._congestion_risk[i],
                self._geopolitical_risk[i],
            ]
            elevated = sum(1 for s in signals if s > 0.3)
            signal_agreement = elevated / len(signals)

            # History-based confidence (more data → higher confidence)
            history_len = len(self._risk_history[i])
            history_factor = min(1.0, history_len / RISK_HISTORY_LENGTH)

            # If the risk is near 0 or near 1, we're more confident
            risk_certainty = abs(raw_composite[i] - 0.5) * 2.0

            # OSINT cluster confidence boost
            osint_boost = 0.0
            if self._last_osint_report:
                for cluster in self._last_osint_report.triggered_clusters:
                    if (cluster.node_id == NODE_IDS[i]
                            and cluster.is_triggered):
                        osint_boost = cluster.avg_confidence * 0.2

            self._confidence[i] = float(np.clip(
                0.3
                + 0.25 * signal_agreement
                + 0.15 * history_factor
                + 0.15 * risk_certainty
                + osint_boost,
                0.1, 0.99,
            ))

    # ── Decision Generation ───────────────────────────────────────

    def _generate_decisions(self) -> list:
        """
        Generate structured AgentDecision objects for nodes that
        exceed risk thresholds.
        """
        decisions = []

        for i in range(NUM_NODES):
            risk = float(self._risk_scores[i])
            conf = float(self._confidence[i])
            node_id = NODE_IDS[i]

            if risk <= AMBER_THRESHOLD or conf < MIN_FLAG_CONFIDENCE:
                continue

            # Determine status
            if risk > RED_THRESHOLD:
                status = "RED"
                action_type = "risk_flag_red"
                priority = min(1.0, risk)
            else:
                status = "AMBER"
                action_type = "risk_flag_amber"
                priority = risk * 0.8

            # Build reasoning
            reasoning = self._build_reasoning(i, risk, conf, status)

            decisions.append(self.make_decision(
                action_type=action_type,
                target=node_id,
                details={
                    "risk_score": round(risk, 4),
                    "confidence": round(conf, 4),
                    "status": status,
                    "signal_breakdown": {
                        "weather": round(float(self._weather_risk[i]), 4),
                        "osint": round(float(self._osint_risk[i]), 4),
                        "supplier": round(float(self._supplier_risk[i]), 4),
                        "congestion": round(float(self._congestion_risk[i]), 4),
                        "geopolitical": round(float(self._geopolitical_risk[i]), 4),
                    },
                    "trend": self._get_trend(i),
                },
                reasoning=reasoning,
                confidence=conf,
                priority=priority,
            ))

        # Sort by priority descending
        decisions.sort(key=lambda d: d.priority, reverse=True)
        return decisions

    def _build_reasoning(
        self,
        node_idx: int,
        risk: float,
        confidence: float,
        status: str,
    ) -> str:
        """
        Build human-readable risk reasoning for a specific node.

        Explains *which* signals are elevated, *why* the risk is
        at the given level, and *what* the downstream impact could be.
        """
        node_id = NODE_IDS[node_idx]
        parts = [
            f"{status} ALERT for {node_id}: "
            f"composite risk {risk:.2f} (confidence {confidence:.2f})."
        ]

        # Identify top contributing signals
        signal_names = [
            ("weather", float(self._weather_risk[node_idx])),
            ("OSINT", float(self._osint_risk[node_idx])),
            ("supplier health", float(self._supplier_risk[node_idx])),
            ("congestion", float(self._congestion_risk[node_idx])),
            ("geopolitical", float(self._geopolitical_risk[node_idx])),
        ]
        signal_names.sort(key=lambda x: x[1], reverse=True)
        top = [s for s in signal_names if s[1] > 0.2]

        if top:
            top_str = ", ".join(
                f"{name} ({val:.2f})" for name, val in top[:3]
            )
            parts.append(f"Primary drivers: {top_str}.")

        # OSINT detail
        if (self._last_osint_report
                and self._osint_risk[node_idx] > 0.3):
            for c in self._last_osint_report.triggered_clusters:
                if c.node_id == node_id:
                    parts.append(
                        f"OSINT: {c.signal_count} social signals "
                        f"({c.sigma_score:.1f} sigma above baseline). "
                        f"Dominant type: {c.dominant_type}."
                    )
                    break

        # Supplier detail
        if (self._last_financial_report
                and self._supplier_risk[node_idx] > 0.3):
            for a in self._last_financial_report.critical_alerts:
                if node_id in a.connected_nodes:
                    parts.append(
                        f"Supplier alert: {a.name} ({a.status.upper()}, "
                        f"score {a.composite_score:.2f}). "
                        f"Flags: {', '.join(a.alert_flags[:3])}."
                    )
                    break

        # Trend
        trend = self._get_trend(node_idx)
        if trend == "rising":
            parts.append("Risk trend is RISING — situation worsening.")
        elif trend == "falling":
            parts.append("Risk trend is FALLING — possible recovery.")

        return " ".join(parts)

    def _get_trend(self, node_idx: int) -> str:
        """Detect risk trend for a node over recent history."""
        history = self._risk_history[node_idx]
        if len(history) < 4:
            return "stable"

        recent = np.mean(history[-3:])
        older = np.mean(history[-6:-3]) if len(history) >= 6 else np.mean(history[:-3])

        if recent > older + 0.08:
            return "rising"
        elif recent < older - 0.08:
            return "falling"
        return "stable"

    # ── Convenience Accessors ─────────────────────────────────────

    @property
    def risk_scores(self) -> np.ndarray:
        """Current per-node risk scores."""
        return self._risk_scores.copy()

    @property
    def confidence_scores(self) -> np.ndarray:
        """Current per-node confidence."""
        return self._confidence.copy()

    @property
    def latest_osint_report(self):
        """Most recent OSINT analysis report."""
        return self._last_osint_report

    @property
    def latest_financial_report(self):
        """Most recent supplier financial report."""
        return self._last_financial_report

    def get_risk_for_node(self, node_id: str) -> dict:
        """Get detailed risk info for a specific node."""
        if node_id not in NODE_TO_IDX:
            return {"error": f"Unknown node {node_id}"}
        i = NODE_TO_IDX[node_id]
        return {
            "node_id": node_id,
            "risk_score": round(float(self._risk_scores[i]), 4),
            "confidence": round(float(self._confidence[i]), 4),
            "signal_breakdown": {
                "weather": round(float(self._weather_risk[i]), 4),
                "osint": round(float(self._osint_risk[i]), 4),
                "supplier": round(float(self._supplier_risk[i]), 4),
                "congestion": round(float(self._congestion_risk[i]), 4),
                "geopolitical": round(float(self._geopolitical_risk[i]), 4),
            },
            "trend": self._get_trend(i),
            "history_length": len(self._risk_history[i]),
        }

    def get_full_risk_report(self) -> dict:
        """Full risk report across all nodes."""
        nodes = []
        for i, nid in enumerate(NODE_IDS):
            risk = float(self._risk_scores[i])
            if risk > AMBER_THRESHOLD:
                status = "RED" if risk > RED_THRESHOLD else "AMBER"
            else:
                status = "GREEN"
            nodes.append({
                "node_id": nid,
                "risk_score": round(risk, 4),
                "confidence": round(float(self._confidence[i]), 4),
                "status": status,
                "trend": self._get_trend(i),
            })
        nodes.sort(key=lambda n: n["risk_score"], reverse=True)

        return {
            "step": self.step_count,
            "agent": self.name,
            "nodes": nodes,
            "red_count": sum(1 for n in nodes if n["status"] == "RED"),
            "amber_count": sum(1 for n in nodes if n["status"] == "AMBER"),
            "osint_summary": (
                self._last_osint_report.scan_summary
                if self._last_osint_report else "No scan yet"
            ),
            "supplier_summary": (
                self._last_financial_report.summary
                if self._last_financial_report else "No scan yet"
            ),
        }
