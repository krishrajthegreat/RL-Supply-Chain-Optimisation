"""
Synthetic disruption scenario generator for NEXUS training.

Produces diverse, realistic crisis configurations to train the
MARL agents against a wide distribution of supply-chain shocks.

Scenario Categories
-------------------
1. Weather cascades — typhoons, floods, ice storms with geographic
   correlation and seasonal patterns.
2. Geopolitical crises — strait closures, sanctions, port strikes
   with realistic duration distributions.
3. Financial shocks — supplier bankruptcies, credit crunches
   affecting specific supply nodes.
4. Compound "Black Swan" events — multiple simultaneous crises
   that stress-test the agents' coordination.
5. Seasonal demand spikes — Chinese New Year, holiday surges,
   monsoon disruptions.

All parameters are calibrated from real-world disruption statistics
to ensure training produces policies that generalize.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Constants (from the env module)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NODE_IDS = [
    "shanghai_port", "rotterdam_port", "hamburg_port", "singapore_port",
    "la_port", "frankfurt_dc", "london_dc", "paris_dc", "newyork_dc",
    "chicago_dc", "dubai_hub", "mumbai_hub", "tokyo_hub", "seoul_hub",
    "sydney_dc",
]

# Geographic clusters for correlated disruptions
GEO_CLUSTERS = {
    "europe": ["rotterdam_port", "hamburg_port", "frankfurt_dc",
               "london_dc", "paris_dc"],
    "asia_pacific": ["shanghai_port", "singapore_port", "tokyo_hub",
                     "seoul_hub", "sydney_dc"],
    "americas": ["la_port", "newyork_dc", "chicago_dc"],
    "middle_east_sa": ["dubai_hub", "mumbai_hub"],
}

# Seasonal disruption probabilities (month-indexed, 0=Jan)
SEASONAL_WEATHER = {
    "asia_pacific": [0.3, 0.2, 0.1, 0.1, 0.15, 0.2, 0.4, 0.5,
                     0.6, 0.4, 0.2, 0.15],  # typhoon season Jul-Oct
    "europe": [0.3, 0.25, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05,
               0.1, 0.15, 0.25, 0.35],  # winter storms
    "americas": [0.15, 0.1, 0.05, 0.05, 0.1, 0.2, 0.3, 0.4,
                 0.5, 0.3, 0.15, 0.1],  # hurricane season Jun-Nov
    "middle_east_sa": [0.05, 0.05, 0.1, 0.15, 0.2, 0.3, 0.35,
                       0.3, 0.2, 0.1, 0.05, 0.05],  # monsoon
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Scenario Definition
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class DisruptionEvent:
    """A single disruption to inject at a specific simulation step."""
    step: int
    disruption_type: str        # weather | congestion | geopolitical | carrier | supplier | financial
    target_node: Optional[str]  # node_id or None for global events
    severity: float             # 0-10
    duration_hours: int         # how long it lasts
    description: str = ""


@dataclass
class TrainingScenario:
    """A complete scenario configuration for one training episode."""
    name: str
    difficulty: str             # "easy" | "medium" | "hard" | "extreme"
    disruption_probability: float
    events: list[DisruptionEvent] = field(default_factory=list)
    season_month: int = 0       # 0-11
    demand_multiplier: float = 1.0
    max_steps: int = 168


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Scenario Generator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ScenarioGenerator:
    """
    Procedural generator for diverse training scenarios.

    Usage
    -----
    >>> gen = ScenarioGenerator(seed=42)
    >>> scenario = gen.generate(difficulty="medium")
    >>> print(scenario.name, len(scenario.events))

    Parameters
    ----------
    seed : int | None
        RNG seed for reproducibility.
    """

    def __init__(self, seed: Optional[int] = None):
        self._rng = np.random.default_rng(seed)

    def generate(
        self, difficulty: str = "medium"
    ) -> TrainingScenario:
        """
        Generate a random scenario at the given difficulty.

        Args:
            difficulty: "easy", "medium", "hard", or "extreme".

        Returns:
            TrainingScenario with pre-scripted disruption events.
        """
        config = {
            "easy":    {"p": 0.01, "n_events": (0, 2),  "sev": (2, 5)},
            "medium":  {"p": 0.02, "n_events": (1, 4),  "sev": (3, 7)},
            "hard":    {"p": 0.04, "n_events": (2, 6),  "sev": (5, 9)},
            "extreme": {"p": 0.06, "n_events": (3, 8),  "sev": (6, 10)},
        }[difficulty]

        month = int(self._rng.integers(0, 12))
        n_events = int(self._rng.integers(*config["n_events"]))

        events = []
        for _ in range(n_events):
            event = self._random_event(
                config["sev"], month, difficulty
            )
            events.append(event)

        # Sort events by step
        events.sort(key=lambda e: e.step)

        # Demand multiplier (seasonal)
        demand_mult = 1.0
        if month in [0, 1, 11]:   # holiday season
            demand_mult = 1.0 + self._rng.random() * 0.3
        elif month in [6, 7, 8]:  # summer
            demand_mult = 0.9 + self._rng.random() * 0.2

        scenario_names = {
            "easy": ["calm_waters", "smooth_sailing", "clear_skies"],
            "medium": ["rough_seas", "storm_warning", "trade_tensions"],
            "hard": ["port_crisis", "cascade_failure", "supply_shock"],
            "extreme": ["black_swan", "perfect_storm", "global_meltdown"],
        }
        name = self._rng.choice(scenario_names[difficulty])
        name = f"{name}_{self._rng.integers(1000, 9999)}"

        return TrainingScenario(
            name=name,
            difficulty=difficulty,
            disruption_probability=config["p"],
            events=events,
            season_month=month,
            demand_multiplier=demand_mult,
        )

    def _random_event(
        self,
        severity_range: tuple[float, float],
        month: int,
        difficulty: str,
    ) -> DisruptionEvent:
        """Generate one random disruption event."""
        dtype = self._rng.choice([
            "weather", "congestion", "geopolitical",
            "carrier", "supplier", "financial",
        ], p=[0.30, 0.25, 0.15, 0.10, 0.10, 0.10])

        step = int(self._rng.integers(1, 160))
        severity = float(self._rng.uniform(*severity_range))

        # Duration scales with severity
        base_dur = int(self._rng.integers(6, 48))
        duration = int(base_dur * (1 + severity / 10))

        # Target node selection
        if dtype == "weather":
            target, desc = self._weather_event(month, severity)
        elif dtype == "congestion":
            target, desc = self._congestion_event(severity)
        elif dtype == "geopolitical":
            target, desc = self._geopolitical_event(severity)
        elif dtype == "carrier":
            target, desc = self._carrier_event(severity)
        elif dtype == "supplier":
            target, desc = self._supplier_event(severity)
        else:
            target, desc = self._financial_event(severity)

        return DisruptionEvent(
            step=step,
            disruption_type=dtype,
            target_node=target,
            severity=severity,
            duration_hours=duration,
            description=desc,
        )

    # ── Event Type Generators ─────────────────────────────────────

    def _weather_event(
        self, month: int, severity: float
    ) -> tuple[str, str]:
        """Weather disruption biased by season and geography."""
        # Pick a region biased by seasonal probability
        regions = list(SEASONAL_WEATHER.keys())
        probs = np.array([
            SEASONAL_WEATHER[r][month] for r in regions
        ])
        probs = probs / probs.sum()
        region = self._rng.choice(regions, p=probs)

        node = self._rng.choice(GEO_CLUSTERS[region])

        weather_types = {
            "asia_pacific": ["Typhoon", "Monsoon flooding", "Tsunami warning"],
            "europe": ["Winter storm", "North Sea gale", "Flooding"],
            "americas": ["Hurricane", "Polar vortex", "Wildfire smoke"],
            "middle_east_sa": ["Monsoon", "Sandstorm", "Cyclone"],
        }
        wtype = self._rng.choice(weather_types[region])
        desc = f"{wtype} affecting {node} (severity {severity:.1f})"
        return node, desc

    def _congestion_event(self, severity: float) -> tuple[str, str]:
        """Port/DC congestion spike."""
        ports = [n for n in NODE_IDS if "port" in n or "hub" in n]
        node = self._rng.choice(ports)
        causes = [
            "labor action", "equipment failure", "vessel bunching",
            "customs backlog", "berth shortage",
        ]
        cause = self._rng.choice(causes)
        desc = f"Congestion at {node} due to {cause} (sev {severity:.1f})"
        return node, desc

    def _geopolitical_event(self, severity: float) -> tuple[str, str]:
        """Trade lane disruption from geopolitical crisis."""
        hotspots = [
            ("shanghai_port", "Strait of Malacca tensions"),
            ("dubai_hub", "Red Sea shipping threat"),
            ("rotterdam_port", "EU trade policy change"),
            ("la_port", "US-China tariff escalation"),
            ("mumbai_hub", "Regional security concern"),
        ]
        node, crisis = hotspots[int(self._rng.integers(0, len(hotspots)))]
        desc = f"{crisis} disrupting {node} (sev {severity:.1f})"
        return node, desc

    def _carrier_event(self, severity: float) -> tuple[str, str]:
        """Carrier-level disruption."""
        nodes = self._rng.choice(NODE_IDS)
        issues = [
            "vessel mechanical failure", "crew shortage",
            "schedule disruption", "port omission",
        ]
        issue = self._rng.choice(issues)
        desc = f"Carrier {issue} at {nodes} (sev {severity:.1f})"
        return nodes, desc

    def _supplier_event(self, severity: float) -> tuple[str, str]:
        """Supplier-related disruption."""
        nodes = ["shanghai_port", "mumbai_hub", "seoul_hub",
                 "singapore_port", "tokyo_hub"]
        node = self._rng.choice(nodes)
        issues = [
            "factory shutdown", "raw material shortage",
            "quality control failure", "production delay",
        ]
        issue = self._rng.choice(issues)
        desc = f"Supplier {issue} affecting {node} (sev {severity:.1f})"
        return node, desc

    def _financial_event(self, severity: float) -> tuple[str, str]:
        """Financial shock disruption."""
        node = self._rng.choice(NODE_IDS)
        issues = [
            "credit downgrade", "currency crisis",
            "insurance withdrawal", "bankruptcy filing",
        ]
        issue = self._rng.choice(issues)
        desc = f"Financial {issue} at {node} (sev {severity:.1f})"
        return node, desc

    # ── Curriculum Generator ──────────────────────────────────────

    def generate_curriculum(
        self, num_scenarios: int = 2000
    ) -> list[TrainingScenario]:
        """
        Generate a full training curriculum with ramping difficulty.

        Phase 1 (0-25%):   easy
        Phase 2 (25-50%):  easy + medium
        Phase 3 (50-75%):  medium + hard
        Phase 4 (75-100%): hard + extreme

        Returns a list of scenarios in curriculum order.
        """
        scenarios = []
        for i in range(num_scenarios):
            progress = i / num_scenarios
            if progress < 0.25:
                diff = "easy"
            elif progress < 0.50:
                diff = self._rng.choice(["easy", "medium"], p=[0.3, 0.7])
            elif progress < 0.75:
                diff = self._rng.choice(["medium", "hard"], p=[0.4, 0.6])
            else:
                diff = self._rng.choice(["hard", "extreme"], p=[0.5, 0.5])
            scenarios.append(self.generate(difficulty=diff))
        return scenarios
