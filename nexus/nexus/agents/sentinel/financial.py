"""
Supplier Financial Health Radar for NEXUS SENTINEL agent.

Fuses four categories of weak-signal intelligence to compute a
composite health score for each supplier in the supply chain:

  1. **Financial Signals** — payment delays, Altman-Z proxy,
     revenue trends, cash flow health, debt/equity ratio.
  2. **Operational Signals** — LinkedIn hiring velocity,
     Glassdoor sentiment, employee review red-flag keywords.
  3. **Market Signals** — news sentiment, credit insurance status,
     CDS spread, tier-n supplier risk.
  4. **Satellite Signals** — facility activity score, parking lot
     occupancy, shipping dock activity (proxy for satellite imagery).

Status Thresholds
-----------------
  Green  : composite > 0.70
  Amber  : 0.40 <= composite <= 0.70
  Red    : composite < 0.40

The key insight from the NEXUS thesis: traditional supply chain risk
management only tracks Tier-1 suppliers.  This radar tracks Tier 1-3
and fuses operational/satellite signals that surface distress signals
*weeks before* financial statements show problems.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from nexus.data import load_json

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Scoring Weights (tunable hyperparameters)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Weights for the four signal categories
CATEGORY_WEIGHTS = {
    "financial":   0.35,
    "operational": 0.25,
    "market":      0.20,
    "satellite":   0.20,
}

# Sub-signal weights within each category
FINANCIAL_WEIGHTS = {
    "payment_delay":  0.25,   # Higher delay → worse
    "altman_z":       0.30,   # Higher Z → better
    "revenue_trend":  0.20,   # Positive trend → better
    "cash_flow":      0.15,   # Higher → better
    "debt_equity":    0.10,   # Lower → better
}

OPERATIONAL_WEIGHTS = {
    "hiring_trend":    0.25,
    "glassdoor":       0.35,
    "review_flags":    0.40,
}

MARKET_WEIGHTS = {
    "news_sentiment":       0.30,
    "credit_insurance":     0.35,
    "cds_spread":           0.15,
    "supplier_supplier":    0.20,
}

SATELLITE_WEIGHTS = {
    "facility_activity":    0.40,
    "parking_occupancy":    0.30,
    "dock_activity":        0.30,
}

# Status thresholds
GREEN_THRESHOLD = 0.70
AMBER_THRESHOLD = 0.40

# Credit insurance status scoring
CREDIT_INSURANCE_SCORES = {
    "full_coverage":    1.0,
    "partial_coverage": 0.6,
    "coverage_reduced": 0.3,
    "under_review":     0.2,
    "withdrawn":        0.0,
}

# LinkedIn hiring trend scoring
HIRING_TREND_SCORES = {
    "positive":   1.0,
    "flat":       0.5,
    "declining":  0.1,
}

# Employee review red-flag penalty per flag
REVIEW_FLAG_PENALTIES = {
    "layoffs_mentioned":       0.20,
    "management_instability":  0.15,
    "delayed_salaries":        0.25,
    "restructuring_rumor":     0.10,
    "bankruptcy_rumor":        0.30,
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Data Structures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class SubSignalBreakdown:
    """Detailed scoring breakdown for a single signal category."""
    category: str
    components: dict[str, float]   # sub-signal name → 0-1 normalised score
    weighted_score: float          # category weighted score
    raw_values: dict               # original data values

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "components": {
                k: round(v, 4) for k, v in self.components.items()
            },
            "weighted_score": round(self.weighted_score, 4),
        }


@dataclass
class SupplierAssessment:
    """Complete health assessment for a single supplier."""
    supplier_id: str
    name: str
    tier: int
    country: str
    connected_nodes: list[str]
    composite_score: float
    status: str                    # "green" | "amber" | "red"
    breakdowns: list[SubSignalBreakdown]
    trend_direction: str           # "improving" | "stable" | "deteriorating"
    trend_velocity: float          # rate of change per step
    risk_reasoning: str            # Human-readable risk explanation
    alert_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "supplier_id": self.supplier_id,
            "name": self.name,
            "tier": self.tier,
            "country": self.country,
            "connected_nodes": self.connected_nodes,
            "composite_score": round(self.composite_score, 4),
            "status": self.status,
            "breakdowns": [b.to_dict() for b in self.breakdowns],
            "trend_direction": self.trend_direction,
            "trend_velocity": round(self.trend_velocity, 4),
            "risk_reasoning": self.risk_reasoning,
            "alert_flags": self.alert_flags,
        }


@dataclass
class FinancialRadarReport:
    """Full radar scan output across all suppliers."""
    total_suppliers: int
    green_count: int
    amber_count: int
    red_count: int
    assessments: list[SupplierAssessment]
    critical_alerts: list[SupplierAssessment]
    summary: str

    def to_dict(self) -> dict:
        return {
            "total_suppliers": self.total_suppliers,
            "green": self.green_count,
            "amber": self.amber_count,
            "red": self.red_count,
            "assessments": [a.to_dict() for a in self.assessments],
            "critical_alerts": [a.to_dict() for a in self.critical_alerts],
            "summary": self.summary,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Supplier Health Radar
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SupplierHealthRadar:
    """
    Multi-source supplier health assessment engine.

    Fuses financial + operational + market + satellite signals
    into composite health scores per supplier, with trend tracking
    and human-readable risk reasoning.
    """

    def __init__(self):
        # Score history for trend detection: {supplier_id: [scores]}
        self._score_history: dict[str, list[float]] = {}
        # Cached supplier data
        self._suppliers: list[dict] = []

    def load_suppliers(
        self, supplier_data: Optional[list[dict]] = None
    ) -> None:
        """Load or reload supplier data."""
        if supplier_data is not None:
            self._suppliers = deepcopy(supplier_data)
        else:
            self._suppliers = deepcopy(
                load_json("suppliers.json")["suppliers"]
            )

    # ── Primary API ───────────────────────────────────────────────

    def scan(
        self, supplier_data: Optional[list[dict]] = None
    ) -> FinancialRadarReport:
        """
        Run a full radar scan across all suppliers.

        Args:
            supplier_data: Optional override for supplier list.
                           If None, uses the loaded/cached data.

        Returns:
            FinancialRadarReport with per-supplier assessments.
        """
        if supplier_data is not None:
            self._suppliers = deepcopy(supplier_data)
        elif not self._suppliers:
            self.load_suppliers()

        assessments: list[SupplierAssessment] = []
        for supplier in self._suppliers:
            assessment = self._assess_supplier(supplier)
            assessments.append(assessment)

        # Counts
        green = sum(1 for a in assessments if a.status == "green")
        amber = sum(1 for a in assessments if a.status == "amber")
        red = sum(1 for a in assessments if a.status == "red")

        # Critical alerts (red + deteriorating amber)
        critical = [
            a for a in assessments
            if a.status == "red"
            or (a.status == "amber" and a.trend_direction == "deteriorating")
        ]

        # Sort by composite score ascending (worst first)
        critical.sort(key=lambda a: a.composite_score)

        # Summary
        if critical:
            crit_names = ", ".join(a.name for a in critical[:3])
            summary = (
                f"Radar scan: {len(assessments)} suppliers assessed. "
                f"{green} green, {amber} amber, {red} red. "
                f"Critical alerts: [{crit_names}]"
            )
        else:
            summary = (
                f"Radar scan: {len(assessments)} suppliers assessed. "
                f"{green} green, {amber} amber, {red} red. "
                f"No critical alerts."
            )

        return FinancialRadarReport(
            total_suppliers=len(assessments),
            green_count=green,
            amber_count=amber,
            red_count=red,
            assessments=assessments,
            critical_alerts=critical,
            summary=summary,
        )

    def get_health_vector(
        self, supplier_data: Optional[list[dict]] = None
    ) -> np.ndarray:
        """
        Return a numpy array of composite health scores for all
        suppliers (used by SENTINEL as observation input).
        """
        report = self.scan(supplier_data)
        return np.array(
            [a.composite_score for a in report.assessments],
            dtype=np.float32,
        )

    def get_node_risk_contribution(
        self, supplier_data: Optional[list[dict]] = None
    ) -> dict[str, float]:
        """
        Compute per-node risk contribution from supplier health.

        For each node, the risk is the inverse of the *weakest*
        supplier connected to it.
        """
        report = self.scan(supplier_data)
        node_risk: dict[str, float] = {}

        for assessment in report.assessments:
            risk = 1.0 - assessment.composite_score
            for node_id in assessment.connected_nodes:
                if node_id not in node_risk:
                    node_risk[node_id] = risk
                else:
                    # Take the maximum risk (worst supplier wins)
                    node_risk[node_id] = max(node_risk[node_id], risk)

        return node_risk

    # ── Individual Supplier Assessment ────────────────────────────

    def _assess_supplier(self, supplier: dict) -> SupplierAssessment:
        """Run the full 4-category assessment on a single supplier."""
        sid = supplier["supplier_id"]

        # Score each category
        fin_breakdown = self._score_financial(supplier)
        ops_breakdown = self._score_operational(supplier)
        mkt_breakdown = self._score_market(supplier)
        sat_breakdown = self._score_satellite(supplier)

        # Weighted composite
        composite = (
            CATEGORY_WEIGHTS["financial"] * fin_breakdown.weighted_score
            + CATEGORY_WEIGHTS["operational"] * ops_breakdown.weighted_score
            + CATEGORY_WEIGHTS["market"] * mkt_breakdown.weighted_score
            + CATEGORY_WEIGHTS["satellite"] * sat_breakdown.weighted_score
        )
        composite = float(np.clip(composite, 0, 1))

        # Status
        if composite >= GREEN_THRESHOLD:
            status = "green"
        elif composite >= AMBER_THRESHOLD:
            status = "amber"
        else:
            status = "red"

        # Trend detection
        trend_dir, trend_vel = self._compute_trend(sid, composite)

        # Alert flags
        alert_flags = self._detect_alert_flags(
            supplier, fin_breakdown, ops_breakdown, mkt_breakdown
        )

        # Human-readable reasoning
        reasoning = self._generate_reasoning(
            supplier, composite, status,
            fin_breakdown, ops_breakdown, mkt_breakdown, sat_breakdown,
            trend_dir, alert_flags,
        )

        return SupplierAssessment(
            supplier_id=sid,
            name=supplier.get("name", sid),
            tier=supplier.get("tier", 0),
            country=supplier.get("country", ""),
            connected_nodes=supplier.get("connected_nodes", []),
            composite_score=composite,
            status=status,
            breakdowns=[fin_breakdown, ops_breakdown, mkt_breakdown, sat_breakdown],
            trend_direction=trend_dir,
            trend_velocity=trend_vel,
            risk_reasoning=reasoning,
            alert_flags=alert_flags,
        )

    # ── Category Scoring ──────────────────────────────────────────

    def _score_financial(self, s: dict) -> SubSignalBreakdown:
        """Score financial signals (0-1, higher = healthier)."""
        fin = s.get("financial_signals", {})

        # Payment delay: 0-60 days → 1.0-0.0
        delay = fin.get("payment_delay_days", 15)
        payment_score = max(0, 1.0 - delay / 60.0)

        # Altman-Z proxy: <1.8 distress, 1.8-3.0 grey, >3.0 safe
        z = fin.get("altman_z_proxy", 2.5)
        if z >= 3.0:
            z_score = 1.0
        elif z >= 1.8:
            z_score = 0.4 + (z - 1.8) / (3.0 - 1.8) * 0.6
        else:
            z_score = max(0, z / 1.8 * 0.4)

        # Revenue trend: -20% to +20% → 0.0-1.0
        trend = fin.get("revenue_trend_pct", 0)
        trend_score = float(np.clip((trend + 20) / 40, 0, 1))

        # Cash flow health: direct 0-1
        cash = fin.get("cash_flow_health", 0.5)

        # Debt/equity: 0-3 → 1.0-0.0
        de_ratio = fin.get("debt_to_equity", 0.5)
        de_score = max(0, 1.0 - de_ratio / 3.0)

        components = {
            "payment_delay": payment_score,
            "altman_z": z_score,
            "revenue_trend": trend_score,
            "cash_flow": cash,
            "debt_equity": de_score,
        }

        weighted = sum(
            components[k] * FINANCIAL_WEIGHTS[k]
            for k in FINANCIAL_WEIGHTS
        )

        return SubSignalBreakdown(
            category="financial",
            components=components,
            weighted_score=weighted,
            raw_values=fin,
        )

    def _score_operational(self, s: dict) -> SubSignalBreakdown:
        """Score operational signals (LinkedIn, Glassdoor, reviews)."""
        ops = s.get("operational_signals", {})

        # Hiring trend
        trend = ops.get("linkedin_hiring_trend", "flat")
        hiring_score = HIRING_TREND_SCORES.get(trend, 0.5)

        # Enrich with hiring velocity (roles now vs 30d ago)
        roles_now = ops.get("linkedin_open_roles", 0)
        roles_30d = ops.get("linkedin_open_roles_30d_ago", roles_now)
        if roles_30d > 0:
            velocity = roles_now / roles_30d
            # velocity > 1 = growing, < 1 = shrinking
            hiring_score = float(np.clip(velocity * 0.5 + 0.25, 0, 1))

        # Glassdoor sentiment: direct 0-1
        glassdoor = ops.get("glassdoor_sentiment", 0.5)

        # Review flags: penalty per flag
        flags = ops.get("employee_review_flags", [])
        flag_penalty = sum(
            REVIEW_FLAG_PENALTIES.get(f, 0.1) for f in flags
        )
        flag_score = max(0, 1.0 - flag_penalty)

        components = {
            "hiring_trend": hiring_score,
            "glassdoor": glassdoor,
            "review_flags": flag_score,
        }

        weighted = sum(
            components[k] * OPERATIONAL_WEIGHTS[k]
            for k in OPERATIONAL_WEIGHTS
        )

        return SubSignalBreakdown(
            category="operational",
            components=components,
            weighted_score=weighted,
            raw_values=ops,
        )

    def _score_market(self, s: dict) -> SubSignalBreakdown:
        """Score market signals (news, credit insurance, CDS, tier-n)."""
        mkt = s.get("market_signals", {})

        # News sentiment: -1 to +1 → 0-1
        news = mkt.get("news_sentiment_score", 0)
        news_score = float(np.clip((news + 1) / 2, 0, 1))

        # Credit insurance status
        insurance = mkt.get("credit_insurance_status", "full_coverage")
        insurance_score = CREDIT_INSURANCE_SCORES.get(insurance, 0.5)

        # CDS spread: lower is better. <100bps good, >500bps bad
        cds = mkt.get("cds_spread_bps")
        if cds is not None:
            cds_score = max(0, 1.0 - cds / 500.0)
        else:
            cds_score = 0.5  # unknown → neutral

        # Supplier's supplier risk: direct 0-1, but inverse
        sub_risk = mkt.get("supplier_supplier_risk", 0.1)
        sub_score = 1.0 - sub_risk

        components = {
            "news_sentiment": news_score,
            "credit_insurance": insurance_score,
            "cds_spread": cds_score,
            "supplier_supplier": sub_score,
        }

        weighted = sum(
            components[k] * MARKET_WEIGHTS[k]
            for k in MARKET_WEIGHTS
        )

        return SubSignalBreakdown(
            category="market",
            components=components,
            weighted_score=weighted,
            raw_values=mkt,
        )

    def _score_satellite(self, s: dict) -> SubSignalBreakdown:
        """Score satellite/imagery proxy signals."""
        sat = s.get("satellite_signals", {})

        facility = sat.get("facility_activity_score", 0.5)
        parking = sat.get("parking_lot_occupancy", 0.5)
        dock = sat.get("shipping_dock_activity", 0.5)

        components = {
            "facility_activity": facility,
            "parking_occupancy": parking,
            "dock_activity": dock,
        }

        weighted = sum(
            components[k] * SATELLITE_WEIGHTS[k]
            for k in SATELLITE_WEIGHTS
        )

        return SubSignalBreakdown(
            category="satellite",
            components=components,
            weighted_score=weighted,
            raw_values=sat,
        )

    # ── Trend Detection ───────────────────────────────────────────

    def _compute_trend(
        self, supplier_id: str, current_score: float
    ) -> tuple[str, float]:
        """
        Detect score trend over the last N observations.

        Returns (direction, velocity) where:
          direction: "improving" | "stable" | "deteriorating"
          velocity:  rate of change per step (-1 to +1)
        """
        history = self._score_history.setdefault(supplier_id, [])
        history.append(current_score)

        # Keep last 20 observations
        if len(history) > 20:
            self._score_history[supplier_id] = history[-20:]
            history = self._score_history[supplier_id]

        if len(history) < 3:
            return "stable", 0.0

        # Simple linear regression slope
        x = np.arange(len(history), dtype=np.float64)
        y = np.array(history, dtype=np.float64)
        slope = float(np.polyfit(x, y, 1)[0])

        if slope > 0.005:
            direction = "improving"
        elif slope < -0.005:
            direction = "deteriorating"
        else:
            direction = "stable"

        return direction, float(np.clip(slope, -1, 1))

    # ── Alert Flag Detection ──────────────────────────────────────

    def _detect_alert_flags(
        self,
        supplier: dict,
        fin: SubSignalBreakdown,
        ops: SubSignalBreakdown,
        mkt: SubSignalBreakdown,
    ) -> list[str]:
        """Detect specific alert conditions worth flagging."""
        flags: list[str] = []

        # Financial distress signals
        if fin.components.get("altman_z", 1) < 0.4:
            flags.append("ALTMAN_Z_DISTRESS_ZONE")
        if fin.components.get("payment_delay", 1) < 0.3:
            flags.append("SEVERE_PAYMENT_DELAYS")
        if fin.components.get("cash_flow", 1) < 0.35:
            flags.append("CASH_FLOW_CRITICAL")

        # Operational red flags
        review_flags = supplier.get("operational_signals", {}).get(
            "employee_review_flags", []
        )
        if "bankruptcy_rumor" in review_flags:
            flags.append("BANKRUPTCY_RUMOR_DETECTED")
        if "delayed_salaries" in review_flags:
            flags.append("SALARY_DELAYS_REPORTED")
        if ops.components.get("hiring_trend", 1) < 0.2:
            flags.append("HIRING_FREEZE_DETECTED")

        # Market signals
        if mkt.components.get("credit_insurance", 1) < 0.1:
            flags.append("CREDIT_INSURANCE_WITHDRAWN")
        if mkt.components.get("news_sentiment", 1) < 0.2:
            flags.append("NEGATIVE_NEWS_SENTIMENT")

        return flags

    # ── Reasoning Generation ──────────────────────────────────────

    def _generate_reasoning(
        self,
        supplier: dict,
        composite: float,
        status: str,
        fin: SubSignalBreakdown,
        ops: SubSignalBreakdown,
        mkt: SubSignalBreakdown,
        sat: SubSignalBreakdown,
        trend: str,
        flags: list[str],
    ) -> str:
        """Generate human-readable risk reasoning for the assessment."""
        name = supplier.get("name", supplier["supplier_id"])
        tier = supplier.get("tier", "?")
        country = supplier.get("country", "??")

        lines = [
            f"Supplier '{name}' (Tier {tier}, {country}): "
            f"composite score {composite:.2f}/1.00 ({status.upper()})."
        ]

        # Category breakdown
        categories = [
            ("Financial", fin.weighted_score),
            ("Operational", ops.weighted_score),
            ("Market", mkt.weighted_score),
            ("Satellite", sat.weighted_score),
        ]
        weakest = min(categories, key=lambda x: x[1])
        strongest = max(categories, key=lambda x: x[1])

        lines.append(
            f"Weakest signal: {weakest[0]} ({weakest[1]:.2f}). "
            f"Strongest: {strongest[0]} ({strongest[1]:.2f})."
        )

        # Trend
        if trend == "deteriorating":
            lines.append("TREND: Score is declining — situation worsening.")
        elif trend == "improving":
            lines.append("TREND: Score is improving — recovery underway.")

        # Specific flags
        if flags:
            flag_str = ", ".join(flags)
            lines.append(f"ALERT FLAGS: {flag_str}")

        # Actionable recommendation
        if status == "red":
            lines.append(
                "RECOMMENDATION: Begin qualifying backup suppliers "
                "immediately. Escalate to procurement leadership."
            )
        elif status == "amber" and trend == "deteriorating":
            lines.append(
                "RECOMMENDATION: Increase monitoring frequency. "
                "Initiate backup supplier shortlisting."
            )
        elif status == "amber":
            lines.append(
                "RECOMMENDATION: Monitor closely. No immediate action "
                "required but stay alert for trend changes."
            )

        return " ".join(lines)
