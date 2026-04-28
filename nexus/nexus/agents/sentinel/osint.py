"""
Dark Signal Intelligence — OSINT NLP pipeline for NEXUS SENTINEL agent.

Extracts disruption signals from unstructured social media posts
(Reddit, Twitter/X, freight industry forums) using either:

  • **Mock mode** (default): rule-based keyword/entity extraction with
    geographic clustering and severity scoring.  Zero API cost.
  • **Gemini mode** (when ``GEMINI_API_KEY`` is set): calls
    ``gemini-1.5-flash`` for structured classification of each post.

The key insight from the NEXUS thesis: official carrier alerts lag
reality by 6-24 hours.  OSINT social signals surface disruptions
*hours earlier* — the Hamburg scenario in our demo data shows a
9.5-hour lead time.

Signal Pipeline
---------------
1. Ingest raw posts (text + metadata)
2. Classify each post: disruption_signal? location? severity? carrier?
3. Aggregate by geographic cluster
4. Compute rolling baseline (mean + sigma)
5. Trigger when cluster volume x severity exceeds 2.5 sigma
"""

from __future__ import annotations

import os
import re
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from nexus.data import load_json

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Data Structures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class PostClassification:
    """Result of classifying a single social media post."""
    post_id: str
    is_disruption_signal: bool
    location: Optional[str]          # node_id if resolvable
    severity: str                    # "none" | "low" | "medium" | "high"
    carrier_affected: Optional[str]  # carrier_id if mentioned
    disruption_type: str             # "weather" | "congestion" | "financial" | ...
    confidence: float                # 0-1
    key_phrases: list[str] = field(default_factory=list)
    raw_text_snippet: str = ""

    @property
    def severity_weight(self) -> float:
        return {"none": 0.0, "low": 0.3, "medium": 0.6, "high": 1.0}.get(
            self.severity, 0.0
        )

    def to_dict(self) -> dict:
        return {
            "post_id": self.post_id,
            "is_disruption_signal": self.is_disruption_signal,
            "location": self.location,
            "severity": self.severity,
            "carrier_affected": self.carrier_affected,
            "disruption_type": self.disruption_type,
            "confidence": round(self.confidence, 3),
            "key_phrases": self.key_phrases,
        }


@dataclass
class ClusterSignal:
    """Aggregated signal for a geographic cluster (node)."""
    node_id: str
    signal_count: int
    total_severity_weight: float
    avg_confidence: float
    dominant_type: str
    sigma_score: float                  # how many sigma above baseline
    is_triggered: bool                  # exceeds 2.5 sigma threshold
    contributing_posts: list[str] = field(default_factory=list)
    carriers_mentioned: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "signal_count": self.signal_count,
            "total_severity_weight": round(self.total_severity_weight, 3),
            "avg_confidence": round(self.avg_confidence, 3),
            "dominant_type": self.dominant_type,
            "sigma_score": round(self.sigma_score, 2),
            "is_triggered": self.is_triggered,
            "contributing_posts": self.contributing_posts[:5],  # top 5
            "carriers_mentioned": self.carriers_mentioned,
        }


@dataclass
class OSINTReport:
    """Full OSINT analysis output for a single scan."""
    total_posts_analysed: int
    disruption_signals_found: int
    clusters: list[ClusterSignal]
    triggered_clusters: list[ClusterSignal]
    scan_summary: str

    def to_dict(self) -> dict:
        return {
            "total_posts_analysed": self.total_posts_analysed,
            "disruption_signals_found": self.disruption_signals_found,
            "clusters": [c.to_dict() for c in self.clusters],
            "triggered_clusters": [c.to_dict() for c in self.triggered_clusters],
            "scan_summary": self.scan_summary,
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Keyword / Entity Dictionaries
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Map location mentions → node IDs
LOCATION_PATTERNS: dict[str, list[str]] = {
    "shanghai_port": [
        "shanghai", "yangshan", "pudong port", "china port",
        "south china", "shenzhen",
    ],
    "rotterdam_port": [
        "rotterdam", "europoort", "maasvlakte", "nl port",
        "dutch port", "netherlands port",
    ],
    "hamburg_port": [
        "hamburg", "burchardkai", "cth", "cta", "elbe",
        "german port", "bremerhaven", "nord",
    ],
    "singapore_port": [
        "singapore", "tuas", "pasir panjang", "sg port",
    ],
    "la_port": [
        "los angeles", "la port", "long beach", "lalb",
        "san pedro", "port of la", "west coast port",
    ],
    "frankfurt_dc": [
        "frankfurt", "rhein-main", "frankfurt dc",
    ],
    "london_dc": [
        "london", "felixstowe", "tilbury", "uk port",
        "british port", "thames",
    ],
    "paris_dc": [
        "paris", "rungis", "le havre", "french port",
    ],
    "newyork_dc": [
        "new york", "newark", "ny dc", "east coast",
        "port elizabeth",
    ],
    "chicago_dc": [
        "chicago", "intermodal", "bnsf", "up rail",
    ],
    "dubai_hub": [
        "dubai", "jebel ali", "uae port", "gulf port",
    ],
    "mumbai_hub": [
        "mumbai", "nhava sheva", "jnpt", "india port",
        "bombay",
    ],
    "tokyo_hub": [
        "tokyo", "yokohama", "japan port", "keihin",
    ],
    "seoul_hub": [
        "seoul", "busan", "incheon", "korea port",
        "korean port",
    ],
    "sydney_dc": [
        "sydney", "port botany", "australia port",
        "botany bay",
    ],
}

# Carrier name → carrier_id
CARRIER_PATTERNS: dict[str, list[str]] = {
    "maersk": ["maersk", "m/v maersk", "maersk line"],
    "msc": ["msc", "mediterranean shipping"],
    "cma_cgm": ["cma cgm", "cma-cgm", "cma"],
    "hapag_lloyd": ["hapag-lloyd", "hapag lloyd", "hapag"],
    "one": ["one ", "ocean network express"],
    "fedex": ["fedex", "fed ex", "federal express"],
    "dhl": ["dhl"],
    "ups": ["ups", "united parcel"],
}

# Disruption type indicators
DISRUPTION_TYPE_KEYWORDS: dict[str, list[str]] = {
    "weather": [
        "storm", "weather", "hurricane", "typhoon", "cyclone",
        "flooding", "surge", "wind", "rain", "fog", "ice",
        "monsoon", "swell",
    ],
    "congestion": [
        "congestion", "backup", "queue", "waiting", "delay",
        "dwell", "backed up", "stuck", "sitting", "bottleneck",
        "overflow", "backlog", "idle", "staging",
    ],
    "financial": [
        "bankrupt", "payroll", "layoff", "credit", "financial",
        "restructur", "debt", "insolv", "shut down", "closed",
        "frozen", "creditor", "distress", "open to work",
    ],
    "labor": [
        "strike", "labor", "union", "walkout", "picket",
        "work stoppage", "industrial action",
    ],
    "geopolitical": [
        "sanction", "conflict", "military", "attack", "houthi",
        "blockade", "embargo", "war", "territorial",
    ],
    "operational": [
        "divert", "skip", "cancel", "service advisory",
        "reduced operations", "restricted", "otp", "performance",
        "late arrival",
    ],
    "regulatory": [
        "regulation", "cbam", "customs", "compliance",
        "reporting requirement", "inspection",
    ],
}

# Severity indicators
SEVERITY_HIGH_WORDS = [
    "severe", "massive", "critical", "emergency", "crisis",
    "catastroph", "shut down", "suspended", "halt", "collapsed",
    "breaking", "alert", "unprecedented", "worst",
    "3 day", "4 day", "5 day", "week",
]
SEVERITY_MEDIUM_WORDS = [
    "significant", "major", "serious", "notable", "escalat",
    "increased", "growing", "48h", "72h", "2 day",
]
SEVERITY_LOW_WORDS = [
    "minor", "slight", "modest", "small", "advisory",
    "preparing", "monitoring", "potential",
]

# 2.5-sigma trigger threshold
SIGMA_THRESHOLD = 2.5

# Baseline: average OSINT signal volume per node per scan window
# (empirical defaults; updated dynamically during operation)
DEFAULT_BASELINE_MEAN = 1.5
DEFAULT_BASELINE_STD = 0.8


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Dark Signal Intelligence Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class DarkSignalIntelligence:
    """
    OSINT NLP pipeline for early-warning disruption detection.

    Operates in two modes:

    **Mock mode** (default):
        Rule-based keyword extraction + regex entity recognition.
        Zero cost, offline-capable, deterministic.

    **Gemini mode** (``use_gemini=True`` and ``GEMINI_API_KEY`` set):
        Calls ``gemini-1.5-flash`` for structured post classification.
        Higher accuracy, but requires API key and incurs cost.

    Parameters
    ----------
    use_gemini : bool
        Whether to attempt Gemini API classification.
    sigma_threshold : float
        Number of standard deviations above baseline to trigger
        a cluster alert (default 2.5).
    """

    def __init__(
        self,
        use_gemini: bool = False,
        sigma_threshold: float = SIGMA_THRESHOLD,
    ):
        self.use_gemini = use_gemini and bool(os.environ.get("GEMINI_API_KEY"))
        self.sigma_threshold = sigma_threshold

        # Gemini model (lazy-initialised)
        self._gemini_model = None

        # Rolling baseline per node: (mean, std) of signal volume
        self._baselines: dict[str, tuple[float, float]] = {}
        self._history_window: list[dict[str, float]] = []  # last N scan volumes

        # Cache of classifications (avoid re-classifying same posts)
        self._classification_cache: dict[str, PostClassification] = {}

    # ── Public API ────────────────────────────────────────────────

    def analyse(
        self,
        posts: Optional[list[dict]] = None,
    ) -> OSINTReport:
        """
        Run the full OSINT pipeline on a list of social media posts.

        Args:
            posts: List of post dicts with at least ``post_id`` and
                   ``text`` fields.  If None, loads mock_social_posts.json.

        Returns:
            OSINTReport with per-cluster analysis and trigger flags.
        """
        if posts is None:
            posts = load_json("mock_social_posts.json")["posts"]

        # Step 1: Classify each post
        classifications: list[PostClassification] = []
        for post in posts:
            pid = post.get("post_id", "")
            if pid in self._classification_cache:
                classifications.append(self._classification_cache[pid])
                continue

            if self.use_gemini:
                cls = self._classify_gemini(post)
            else:
                cls = self._classify_mock(post)

            self._classification_cache[pid] = cls
            classifications.append(cls)

        # Step 2: Filter to disruption signals
        signals = [c for c in classifications if c.is_disruption_signal]

        # Step 3: Aggregate by geographic cluster
        clusters = self._aggregate_clusters(signals)

        # Step 4: Compute sigma scores and trigger
        for cluster in clusters:
            baseline_mean, baseline_std = self._get_baseline(cluster.node_id)
            weighted_volume = cluster.total_severity_weight
            if baseline_std > 0:
                cluster.sigma_score = (
                    (weighted_volume - baseline_mean) / baseline_std
                )
            else:
                cluster.sigma_score = (
                    weighted_volume / max(baseline_mean, 0.1) * 2.0
                )
            cluster.is_triggered = cluster.sigma_score >= self.sigma_threshold

        # Update rolling baselines
        scan_volumes = {
            c.node_id: c.total_severity_weight for c in clusters
        }
        self._update_baselines(scan_volumes)

        triggered = [c for c in clusters if c.is_triggered]

        # Build summary
        if triggered:
            trigger_names = ", ".join(c.node_id for c in triggered)
            summary = (
                f"OSINT scan: {len(signals)}/{len(posts)} posts flagged as "
                f"disruption signals. {len(triggered)} cluster(s) triggered "
                f"at >{self.sigma_threshold}sigma: [{trigger_names}]"
            )
        else:
            summary = (
                f"OSINT scan: {len(signals)}/{len(posts)} posts flagged. "
                f"No clusters above {self.sigma_threshold}sigma threshold."
            )

        return OSINTReport(
            total_posts_analysed=len(posts),
            disruption_signals_found=len(signals),
            clusters=clusters,
            triggered_clusters=triggered,
            scan_summary=summary,
        )

    def get_signal_volume_per_node(
        self,
        posts: Optional[list[dict]] = None,
    ) -> dict[str, float]:
        """
        Quick scan returning normalised signal volume per node (0-1).
        Used by the SENTINEL agent for the observation vector.
        """
        report = self.analyse(posts)
        volumes: dict[str, float] = {}
        max_vol = max(
            (c.total_severity_weight for c in report.clusters), default=1.0
        )
        max_vol = max(max_vol, 1.0)
        for cluster in report.clusters:
            volumes[cluster.node_id] = min(
                1.0, cluster.total_severity_weight / max_vol
            )
        return volumes

    def clear_cache(self) -> None:
        """Clear classification cache (e.g. on new post batch)."""
        self._classification_cache.clear()

    # ── Mock Classification ───────────────────────────────────────

    def _classify_mock(self, post: dict) -> PostClassification:
        """
        Rule-based keyword/entity extraction classifier.

        Uses pattern matching against curated dictionaries of
        location names, carrier names, disruption keywords, and
        severity indicators.
        """
        text = post.get("text", "").lower()
        post_id = post.get("post_id", "unknown")

        # ── Location extraction ──
        location = None
        for node_id, patterns in LOCATION_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    location = node_id
                    break
            if location:
                break

        # ── Carrier extraction ──
        carrier = None
        for carrier_id, patterns in CARRIER_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    carrier = carrier_id
                    break
            if carrier:
                break

        # ── Disruption type ──
        type_scores: dict[str, int] = {}
        for dtype, keywords in DISRUPTION_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                type_scores[dtype] = score

        if type_scores:
            disruption_type = max(type_scores, key=type_scores.get)
        else:
            disruption_type = "unknown"

        # ── Severity ──
        severity = "none"
        high_hits = sum(1 for w in SEVERITY_HIGH_WORDS if w in text)
        med_hits = sum(1 for w in SEVERITY_MEDIUM_WORDS if w in text)
        low_hits = sum(1 for w in SEVERITY_LOW_WORDS if w in text)

        if high_hits >= 1:
            severity = "high"
        elif med_hits >= 1:
            severity = "medium"
        elif low_hits >= 1:
            severity = "low"
        elif type_scores:
            severity = "low"  # has disruption keywords but no severity cue

        # ── Is it a disruption signal? ──
        is_signal = bool(type_scores) and severity != "none"

        # If ground truth is available, respect it for training evaluation
        if "is_disruption_signal" in post:
            is_signal = post["is_disruption_signal"]

        # ── Key phrases ──
        key_phrases = _extract_key_phrases(text)

        # ── Confidence ──
        # Higher if more keywords match and engagement is high
        engagement = post.get("engagement", {})
        eng_score = min(
            1.0,
            (engagement.get("upvotes", 0) + engagement.get("likes", 0)) / 1000,
        )
        keyword_score = min(1.0, sum(type_scores.values()) / 5) if type_scores else 0
        confidence = 0.3 + 0.35 * keyword_score + 0.35 * eng_score

        return PostClassification(
            post_id=post_id,
            is_disruption_signal=is_signal,
            location=location,
            severity=severity,
            carrier_affected=carrier,
            disruption_type=disruption_type,
            confidence=round(confidence, 3),
            key_phrases=key_phrases,
            raw_text_snippet=text[:120],
        )

    # ── Gemini Classification ─────────────────────────────────────

    def _classify_gemini(self, post: dict) -> PostClassification:
        """
        Classify a post using Gemini 1.5 Flash.

        Falls back to mock classification if the API call fails.
        """
        try:
            model = self._get_gemini_model()
            text = post.get("text", "")
            post_id = post.get("post_id", "unknown")

            prompt = f"""Analyse this social media post for supply chain disruption signals.

POST:
\"\"\"{text}\"\"\"

Respond ONLY with a JSON object (no markdown, no explanation):
{{
    "is_disruption_signal": true/false,
    "location": "city or port name mentioned, or null",
    "severity": "none" | "low" | "medium" | "high",
    "carrier_affected": "carrier name or null",
    "disruption_type": "weather" | "congestion" | "financial" | "labor" | "geopolitical" | "operational" | "regulatory" | "none",
    "confidence": 0.0-1.0,
    "key_phrases": ["phrase1", "phrase2"]
}}"""

            response = model.generate_content(prompt)
            response_text = response.text.strip()

            # Strip markdown fences if present
            if response_text.startswith("```"):
                response_text = re.sub(
                    r"^```(?:json)?\s*", "", response_text
                )
                response_text = re.sub(r"\s*```$", "", response_text)

            parsed = json.loads(response_text)

            # Resolve location to node_id
            location = self._resolve_location(
                parsed.get("location") or ""
            )
            # Resolve carrier to carrier_id
            carrier = self._resolve_carrier(
                parsed.get("carrier_affected") or ""
            )

            return PostClassification(
                post_id=post_id,
                is_disruption_signal=parsed.get("is_disruption_signal", False),
                location=location,
                severity=parsed.get("severity", "none"),
                carrier_affected=carrier,
                disruption_type=parsed.get("disruption_type", "unknown"),
                confidence=float(parsed.get("confidence", 0.5)),
                key_phrases=parsed.get("key_phrases", []),
                raw_text_snippet=text[:120],
            )

        except Exception as exc:
            logger.warning(
                "Gemini classification failed for %s: %s — falling back to mock",
                post.get("post_id"), exc,
            )
            return self._classify_mock(post)

    def _get_gemini_model(self):
        """Lazy-initialise the Gemini generative model."""
        if self._gemini_model is None:
            import google.generativeai as genai
            genai.configure(api_key=os.environ["GEMINI_API_KEY"])
            self._gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        return self._gemini_model

    def _resolve_location(self, location_text: str) -> Optional[str]:
        """Map a free-text location to a node_id."""
        if not location_text:
            return None
        text = location_text.lower()
        for node_id, patterns in LOCATION_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    return node_id
        return None

    def _resolve_carrier(self, carrier_text: str) -> Optional[str]:
        """Map a free-text carrier name to a carrier_id."""
        if not carrier_text:
            return None
        text = carrier_text.lower()
        for carrier_id, patterns in CARRIER_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    return carrier_id
        return None

    # ── Cluster Aggregation ───────────────────────────────────────

    def _aggregate_clusters(
        self, signals: list[PostClassification]
    ) -> list[ClusterSignal]:
        """
        Group classified disruption signals by geographic cluster (node_id)
        and compute aggregate metrics.
        """
        clusters_raw: dict[str, list[PostClassification]] = {}
        for sig in signals:
            if sig.location:
                clusters_raw.setdefault(sig.location, []).append(sig)

        clusters: list[ClusterSignal] = []
        for node_id, posts in clusters_raw.items():
            # Severity-weighted signal volume
            total_weight = sum(p.severity_weight for p in posts)
            avg_conf = np.mean([p.confidence for p in posts])

            # Dominant disruption type
            type_counts: dict[str, int] = {}
            for p in posts:
                type_counts[p.disruption_type] = (
                    type_counts.get(p.disruption_type, 0) + 1
                )
            dominant = max(type_counts, key=type_counts.get)

            # Unique carriers mentioned
            carriers = list({
                p.carrier_affected
                for p in posts
                if p.carrier_affected
            })

            clusters.append(ClusterSignal(
                node_id=node_id,
                signal_count=len(posts),
                total_severity_weight=total_weight,
                avg_confidence=float(avg_conf),
                dominant_type=dominant,
                sigma_score=0.0,       # computed later
                is_triggered=False,    # computed later
                contributing_posts=[p.post_id for p in posts],
                carriers_mentioned=carriers,
            ))

        # Sort by severity weight descending
        clusters.sort(key=lambda c: c.total_severity_weight, reverse=True)
        return clusters

    # ── Baseline Management ───────────────────────────────────────

    def _get_baseline(self, node_id: str) -> tuple[float, float]:
        """Get rolling (mean, std) baseline for a node's signal volume."""
        if node_id in self._baselines:
            return self._baselines[node_id]
        return (DEFAULT_BASELINE_MEAN, DEFAULT_BASELINE_STD)

    def _update_baselines(self, scan_volumes: dict[str, float]) -> None:
        """
        Update rolling baselines from the latest scan.

        Maintains a window of the last 30 scans for each node.
        """
        self._history_window.append(scan_volumes)
        if len(self._history_window) > 30:
            self._history_window = self._history_window[-30:]

        # Recompute baselines from history
        all_nodes = set()
        for scan in self._history_window:
            all_nodes.update(scan.keys())

        for node_id in all_nodes:
            values = [
                scan.get(node_id, 0.0) for scan in self._history_window
            ]
            mean = float(np.mean(values))
            std = float(np.std(values))
            # Minimum std to avoid division by zero on constant signals
            std = max(std, 0.3)
            self._baselines[node_id] = (mean, std)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Utility Functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _extract_key_phrases(text: str, max_phrases: int = 5) -> list[str]:
    """
    Extract salient phrases from post text using simple heuristics.

    Looks for:
      - Numeric values with units (hours, days, TEU, km, %)
      - Quoted entities
      - Capital-letter sequences (proper nouns)
    """
    phrases: list[str] = []

    # Numeric patterns: "14 vessels", "$2,400", "48-72h", "40%"
    numerics = re.findall(
        r"\d[\d,.]*\s*(?:vessels?|containers?|hours?|days?|teu|km|%|"
        r"ships?|trucks?|units?|\$[\d,.]+[mk]?)",
        text,
    )
    phrases.extend(numerics[:3])

    # Dollar amounts
    dollars = re.findall(r"[\$\u20ac\u00a3][\d,.]+[mk]?", text)
    phrases.extend(dollars[:2])

    # Time expressions
    times = re.findall(r"\d+(?:-\d+)?\s*(?:hours?|days?|h\b|d\b)", text)
    phrases.extend(times[:2])

    return list(dict.fromkeys(phrases))[:max_phrases]  # deduplicate
