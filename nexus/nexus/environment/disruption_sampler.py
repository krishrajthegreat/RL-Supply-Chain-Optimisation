"""
Disruption sampling engine for the NEXUS supply chain simulation.

Manages the full disruption lifecycle — injection, tracking, effect
application, and resolution — with support for both stochastic sampling
from historical distributions and scripted demo scenarios.

Disruption distribution (from empirical supply chain data):
  40 % weather · 25 % congestion · 20 % labor · 10 % geopolitical · 5 % financial
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from nexus.environment.network_graph import (
    CircuitState,
    SupplyChainNetwork,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Disruption Types & Parameters
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class DisruptionType(str, Enum):
    WEATHER = "weather"
    CONGESTION = "congestion"
    LABOR = "labor"
    GEOPOLITICAL = "geopolitical"
    FINANCIAL = "financial"
    CARRIER = "carrier"


# Historical probability of each disruption type
DISRUPTION_DISTRIBUTION: dict[DisruptionType, float] = {
    DisruptionType.WEATHER: 0.40,
    DisruptionType.CONGESTION: 0.25,
    DisruptionType.LABOR: 0.20,
    DisruptionType.GEOPOLITICAL: 0.10,
    DisruptionType.FINANCIAL: 0.05,
}

# Severity distributions (mean, std) on 0-10 scale
SEVERITY_PARAMS: dict[DisruptionType, tuple[float, float]] = {
    DisruptionType.WEATHER: (5.5, 2.0),
    DisruptionType.CONGESTION: (4.0, 1.5),
    DisruptionType.LABOR: (6.0, 1.8),
    DisruptionType.GEOPOLITICAL: (7.0, 2.0),
    DisruptionType.FINANCIAL: (8.0, 1.5),
    DisruptionType.CARRIER: (4.5, 1.5),
}

# Duration distributions (mean_hours, std_hours)
DURATION_PARAMS: dict[DisruptionType, tuple[int, int]] = {
    DisruptionType.WEATHER: (48, 24),
    DisruptionType.CONGESTION: (72, 36),
    DisruptionType.LABOR: (120, 72),
    DisruptionType.GEOPOLITICAL: (240, 120),
    DisruptionType.FINANCIAL: (720, 360),
    DisruptionType.CARRIER: (96, 48),
}

# Nodes statistically vulnerable to each disruption type
VULNERABILITY_MAP: dict[DisruptionType, list[str]] = {
    DisruptionType.WEATHER: [
        "hamburg_port", "rotterdam_port", "la_port",
        "mumbai_hub", "shanghai_port", "tokyo_hub", "sydney_dc",
    ],
    DisruptionType.CONGESTION: [
        "shanghai_port", "la_port", "hamburg_port",
        "singapore_port", "mumbai_hub", "dubai_hub",
    ],
    DisruptionType.LABOR: [
        "la_port", "hamburg_port", "rotterdam_port",
        "london_dc", "mumbai_hub",
    ],
    DisruptionType.GEOPOLITICAL: [
        "dubai_hub", "mumbai_hub", "shanghai_port", "seoul_hub",
    ],
    DisruptionType.FINANCIAL: [
        "mumbai_hub", "shanghai_port", "dubai_hub",
    ],
}

# Human-readable description templates
_DESCRIPTION_TEMPLATES: dict[DisruptionType, str] = {
    DisruptionType.WEATHER: (
        "Severe weather event at {node_name}. Severity {severity:.1f}/10. "
        "Crane operations restricted, throughput degraded. "
        "Estimated duration: {duration}h."
    ),
    DisruptionType.CONGESTION: (
        "Severe congestion at {node_name}. Queue depth {queue_mult:.1f}× normal. "
        "Dwell times significantly increased. "
        "Estimated duration: {duration}h."
    ),
    DisruptionType.LABOR: (
        "Labor disruption at {node_name}. Severity {severity:.1f}/10. "
        "Work stoppages reported, throughput reduced. "
        "Estimated duration: {duration}h."
    ),
    DisruptionType.GEOPOLITICAL: (
        "Geopolitical risk increase on {edge_label} corridor. "
        "Risk premium up {risk_pct:.0f}%. Sanctions/conflict exposure elevated. "
        "Estimated duration: {duration}h."
    ),
    DisruptionType.FINANCIAL: (
        "Supplier {supplier_id} showing financial distress. "
        "Connected node {node_name} at risk of supply interruption. "
        "Credit insurance under review. Estimated duration: {duration}h."
    ),
    DisruptionType.CARRIER: (
        "Carrier {carrier_id} experiencing operational issues. "
        "OTP dropped by {otp_drop_pct:.0f}%. Multiple service delays reported. "
        "Estimated duration: {duration}h."
    ),
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Disruption Event
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class DisruptionEvent:
    """A single disruption with type, target, severity, and lifecycle state."""
    event_id: str
    disruption_type: DisruptionType
    target_node: Optional[str]
    target_edge: Optional[tuple[str, str]]
    target_carrier: Optional[str]
    severity: float               # 0-10
    duration_hours: int
    start_hour: int               # sim-hour when injected
    description: str
    resolved: bool = False
    hours_active: int = 0

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "type": self.disruption_type.value,
            "target_node": self.target_node,
            "target_edge": (
                list(self.target_edge) if self.target_edge else None
            ),
            "target_carrier": self.target_carrier,
            "severity": round(self.severity, 2),
            "duration_hours": self.duration_hours,
            "start_hour": self.start_hour,
            "hours_active": self.hours_active,
            "resolved": self.resolved,
            "description": self.description,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Disruption Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class DisruptionEngine:
    """
    Manages disruption lifecycle: injection → tracking → resolution.

    Supports both:
      • Scripted injections (for the live demo)
      • Stochastic sampling from historical distributions (for RL training)
    """

    def __init__(
        self,
        network: SupplyChainNetwork,
        seed: Optional[int] = None,
    ):
        self.network = network
        self.rng = np.random.default_rng(seed)
        self.active_disruptions: list[DisruptionEvent] = []
        self.resolved_disruptions: list[DisruptionEvent] = []
        self._event_counter = 0

    def _next_event_id(self) -> str:
        self._event_counter += 1
        return f"DISR-{self._event_counter:04d}"

    # ── Specific Injection Methods ─────────────────────────────────

    def inject_weather(
        self,
        node_id: str,
        severity: float,
        duration_hours: int = 72,
        current_hour: int = 0,
    ) -> DisruptionEvent:
        """Inject weather disruption — degrades throughput 40-80 %."""
        severity = max(1.0, min(10.0, severity))
        node = self.network.nodes.get(node_id)
        node_name = node.name if node else node_id

        event = DisruptionEvent(
            event_id=self._next_event_id(),
            disruption_type=DisruptionType.WEATHER,
            target_node=node_id,
            target_edge=None,
            target_carrier=None,
            severity=severity,
            duration_hours=duration_hours,
            start_hour=current_hour,
            description=_DESCRIPTION_TEMPLATES[DisruptionType.WEATHER].format(
                node_name=node_name,
                severity=severity,
                duration=duration_hours,
            ),
        )
        self.network.apply_weather_disruption(node_id, severity)
        self.active_disruptions.append(event)
        return event

    def inject_congestion(
        self,
        node_id: str,
        queue_multiplier: float = 3.0,
        duration_hours: int = 96,
        current_hour: int = 0,
    ) -> DisruptionEvent:
        """Inject congestion — queue depth spike and dwell increase."""
        node = self.network.nodes.get(node_id)
        node_name = node.name if node else node_id

        event = DisruptionEvent(
            event_id=self._next_event_id(),
            disruption_type=DisruptionType.CONGESTION,
            target_node=node_id,
            target_edge=None,
            target_carrier=None,
            severity=min(10.0, queue_multiplier * 2.5),
            duration_hours=duration_hours,
            start_hour=current_hour,
            description=_DESCRIPTION_TEMPLATES[DisruptionType.CONGESTION].format(
                node_name=node_name,
                queue_mult=queue_multiplier,
                duration=duration_hours,
            ),
        )
        self.network.apply_congestion(node_id, queue_multiplier)
        self.active_disruptions.append(event)
        return event

    def inject_labor(
        self,
        node_id: str,
        severity: float = 6.0,
        duration_hours: int = 120,
        current_hour: int = 0,
    ) -> DisruptionEvent:
        """Inject labor disruption — modelled as combined weather + congestion."""
        severity = max(1.0, min(10.0, severity))
        node = self.network.nodes.get(node_id)
        node_name = node.name if node else node_id

        event = DisruptionEvent(
            event_id=self._next_event_id(),
            disruption_type=DisruptionType.LABOR,
            target_node=node_id,
            target_edge=None,
            target_carrier=None,
            severity=severity,
            duration_hours=duration_hours,
            start_hour=current_hour,
            description=_DESCRIPTION_TEMPLATES[DisruptionType.LABOR].format(
                node_name=node_name,
                severity=severity,
                duration=duration_hours,
            ),
        )
        # Labor disruptions reduce throughput and increase congestion
        self.network.apply_weather_disruption(node_id, severity * 0.6)
        self.network.apply_congestion(node_id, 1.0 + severity * 0.15)
        self.active_disruptions.append(event)
        return event

    def inject_carrier_disruption(
        self,
        carrier_id: str,
        otp_drop: float = 0.20,
        duration_hours: int = 168,
        current_hour: int = 0,
    ) -> DisruptionEvent:
        """Inject carrier performance degradation."""
        event = DisruptionEvent(
            event_id=self._next_event_id(),
            disruption_type=DisruptionType.CARRIER,
            target_node=None,
            target_edge=None,
            target_carrier=carrier_id,
            severity=min(10.0, otp_drop * 30),
            duration_hours=duration_hours,
            start_hour=current_hour,
            description=_DESCRIPTION_TEMPLATES[DisruptionType.CARRIER].format(
                carrier_id=carrier_id,
                otp_drop_pct=otp_drop * 100,
                duration=duration_hours,
            ),
        )
        self.active_disruptions.append(event)
        return event

    def inject_geopolitical(
        self,
        from_node: str,
        to_node: str,
        risk_increase: float = 0.4,
        duration_hours: int = 336,
        current_hour: int = 0,
    ) -> DisruptionEvent:
        """Inject geopolitical risk on a specific lane."""
        event = DisruptionEvent(
            event_id=self._next_event_id(),
            disruption_type=DisruptionType.GEOPOLITICAL,
            target_node=None,
            target_edge=(from_node, to_node),
            target_carrier=None,
            severity=min(10.0, risk_increase * 15),
            duration_hours=duration_hours,
            start_hour=current_hour,
            description=_DESCRIPTION_TEMPLATES[DisruptionType.GEOPOLITICAL].format(
                edge_label=f"{from_node} → {to_node}",
                risk_pct=risk_increase * 100,
                duration=duration_hours,
            ),
        )
        self.network.apply_geopolitical_risk(from_node, to_node, risk_increase)
        self.active_disruptions.append(event)
        return event

    def inject_supplier_stress(
        self,
        supplier_id: str,
        connected_node: str,
        severity: float = 7.0,
        duration_hours: int = 720,
        current_hour: int = 0,
    ) -> DisruptionEvent:
        """Inject supplier financial distress (affects connected node)."""
        node = self.network.nodes.get(connected_node)
        node_name = node.name if node else connected_node

        event = DisruptionEvent(
            event_id=self._next_event_id(),
            disruption_type=DisruptionType.FINANCIAL,
            target_node=connected_node,
            target_edge=None,
            target_carrier=None,
            severity=min(10.0, severity),
            duration_hours=duration_hours,
            start_hour=current_hour,
            description=_DESCRIPTION_TEMPLATES[DisruptionType.FINANCIAL].format(
                supplier_id=supplier_id,
                node_name=node_name,
                duration=duration_hours,
            ),
        )
        self.active_disruptions.append(event)
        return event

    # ── Stochastic Sampling ───────────────────────────────────────

    def sample_disruption(self, current_hour: int = 0) -> DisruptionEvent:
        """
        Sample a random disruption from historical distributions.

        Distribution: 40 % weather · 25 % congestion · 20 % labor
                      · 10 % geopolitical · 5 % financial
        Severity and duration drawn from type-specific Gaussians.
        """
        dtypes = list(DISRUPTION_DISTRIBUTION.keys())
        weights = np.array(list(DISRUPTION_DISTRIBUTION.values()))
        weights = weights / weights.sum()
        dtype_idx = self.rng.choice(len(dtypes), p=weights)
        dtype = dtypes[dtype_idx]

        mean_s, std_s = SEVERITY_PARAMS[dtype]
        severity = max(1.0, min(10.0, float(self.rng.normal(mean_s, std_s))))

        mean_d, std_d = DURATION_PARAMS[dtype]
        duration = max(6, int(self.rng.normal(mean_d, std_d)))

        # Choose a vulnerable target node
        if dtype in VULNERABILITY_MAP:
            vuln_nodes = VULNERABILITY_MAP[dtype]
            target_node = vuln_nodes[self.rng.integers(0, len(vuln_nodes))]
        else:
            node_keys = list(self.network.nodes.keys())
            target_node = node_keys[self.rng.integers(0, len(node_keys))]

        # Dispatch to the appropriate injection method
        if dtype == DisruptionType.WEATHER:
            return self.inject_weather(
                target_node, severity, duration, current_hour
            )
        elif dtype == DisruptionType.CONGESTION:
            return self.inject_congestion(
                target_node, max(1.5, severity / 3), duration, current_hour
            )
        elif dtype == DisruptionType.LABOR:
            return self.inject_labor(
                target_node, severity, duration, current_hour
            )
        elif dtype == DisruptionType.GEOPOLITICAL:
            edges = self.network.get_edges_from(target_node)
            if edges:
                edge = edges[self.rng.integers(0, len(edges))]
                return self.inject_geopolitical(
                    edge.from_node, edge.to_node,
                    max(0.1, severity / 15), duration, current_hour,
                )
            # Fallback if no outbound edges
            return self.inject_congestion(
                target_node, max(1.5, severity / 3), duration, current_hour
            )
        elif dtype == DisruptionType.FINANCIAL:
            return self.inject_supplier_stress(
                f"SUP-GEN-{self._event_counter:03d}",
                target_node, severity, duration, current_hour,
            )

        # Final fallback
        return self.inject_congestion(
            target_node, max(1.5, severity / 3), duration, current_hour
        )

    # ── Lifecycle ─────────────────────────────────────────────────

    def tick(self, current_hour: int) -> list[DisruptionEvent]:
        """
        Advance all disruptions by one hour. Resolve and rollback expired ones.

        Returns list of disruptions that resolved this tick.
        """
        newly_resolved: list[DisruptionEvent] = []

        for event in self.active_disruptions:
            event.hours_active += 1
            if event.hours_active >= event.duration_hours:
                event.resolved = True
                newly_resolved.append(event)

        for event in newly_resolved:
            self.active_disruptions.remove(event)
            self.resolved_disruptions.append(event)

            # Rollback network effects
            if event.target_node:
                self.network.reset_node(event.target_node)
            if event.target_edge:
                self.network.reset_edge(*event.target_edge)

        return newly_resolved

    # ── Queries ────────────────────────────────────────────────────

    def get_active_events(self) -> list[dict]:
        return [e.to_dict() for e in self.active_disruptions]

    def get_active_for_node(self, node_id: str) -> list[DisruptionEvent]:
        return [
            e for e in self.active_disruptions
            if e.target_node == node_id
        ]

    def get_history(self) -> list[dict]:
        return [e.to_dict() for e in self.resolved_disruptions]

    def is_node_disrupted(self, node_id: str) -> bool:
        return any(e.target_node == node_id for e in self.active_disruptions)

    def max_severity_at_node(self, node_id: str) -> float:
        events = self.get_active_for_node(node_id)
        return max((e.severity for e in events), default=0.0)

    # ── Demo Scenarios ────────────────────────────────────────────

    def inject_hamburg_scenario(
        self, current_hour: int = 0
    ) -> list[DisruptionEvent]:
        """
        Injects the primary demo scenario from context.md:
          1. Hamburg storm surge (weather + congestion)
          2. Gujarat Chemical supplier distress
          3. ONE carrier performance drop

        This scenario demonstrates the full NEXUS response chain:
        SENTINEL detects → GUARDIAN isolates → NAVIGATOR reroutes
        → STOCKPILE pre-positions → HERALD communicates
        """
        events = [
            self.inject_weather("hamburg_port", 8.5, 72, current_hour),
            self.inject_congestion("hamburg_port", 3.5, 96, current_hour),
            self.inject_supplier_stress(
                "SUP-003", "mumbai_hub", 7.5, 720, current_hour
            ),
            self.inject_carrier_disruption("one", 0.18, 168, current_hour),
        ]
        return events

    def inject_red_sea_scenario(
        self, current_hour: int = 0
    ) -> list[DisruptionEvent]:
        """
        Simulates a Red Sea crisis: geopolitical risk spike on
        Asia→Europe lanes transiting the Suez corridor.
        """
        events = [
            self.inject_geopolitical(
                "singapore_port", "rotterdam_port", 0.55, 480, current_hour
            ),
            self.inject_geopolitical(
                "singapore_port", "dubai_hub", 0.40, 480, current_hour
            ),
            self.inject_geopolitical(
                "dubai_hub", "rotterdam_port", 0.60, 480, current_hour
            ),
        ]
        return events

    def inject_shanghai_lockdown_scenario(
        self, current_hour: int = 0
    ) -> list[DisruptionEvent]:
        """
        Simulates COVID-era Shanghai lockdown: severe weather-like
        throughput reduction plus massive congestion.
        """
        events = [
            self.inject_weather("shanghai_port", 9.0, 168, current_hour),
            self.inject_congestion("shanghai_port", 5.0, 240, current_hour),
            self.inject_supplier_stress(
                "SUP-001", "shanghai_port", 6.0, 336, current_hour
            ),
            self.inject_supplier_stress(
                "SUP-006", "shanghai_port", 8.0, 336, current_hour
            ),
        ]
        return events

    # ── Reset ─────────────────────────────────────────────────────

    def reset(self):
        """Clear all disruptions and restore network to seed state."""
        self.active_disruptions.clear()
        self.resolved_disruptions.clear()
        self._event_counter = 0
        self.network.reset_all()
