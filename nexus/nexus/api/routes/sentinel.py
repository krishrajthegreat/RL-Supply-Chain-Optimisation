"""
SENTINEL analysis and risk intelligence endpoints.

Exposes the SENTINEL agent's risk assessments, OSINT Dark Signal
Intelligence reports, supplier financial radar, and decision history
via REST endpoints for the frontend dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/sentinel", tags=["SENTINEL"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Dependency
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _get_state():
    from nexus.api.main import sim
    if sim.env is None or sim.sentinel is None:
        raise HTTPException(
            503, "Simulation not initialised. POST /api/v1/simulation/reset first."
        )
    return sim


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Risk Report
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/risk-report", summary="Full risk report across all nodes")
async def get_risk_report():
    """
    Returns SENTINEL's current risk assessment for all 15 nodes,
    including composite scores, status (GREEN/AMBER/RED), trend
    direction, OSINT summary, and supplier summary.

    This is the primary endpoint for the NEXUS dashboard's
    risk heatmap visualisation.
    """
    s = _get_state()
    return s.sentinel.get_full_risk_report()


@router.get("/risk/{node_id}", summary="Detailed risk for a specific node")
async def get_node_risk(node_id: str):
    """
    Returns SENTINEL's detailed risk assessment for a single node,
    including signal breakdown (weather, OSINT, supplier, congestion,
    geopolitical), confidence, trend, and history length.
    """
    s = _get_state()
    result = s.sentinel.get_risk_for_node(node_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  OSINT Intelligence
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/osint", summary="Latest OSINT Dark Signal report")
async def get_osint_report():
    """
    Returns the most recent OSINT Dark Signal Intelligence analysis:
    - Total posts analysed and disruption signals found
    - Geographic clusters with sigma scores
    - Triggered clusters (exceeding 2.5sigma threshold)
    - Contributing posts and carrier mentions

    The scan is performed periodically by SENTINEL (every N steps).
    To trigger a fresh scan, use POST /osint/scan.
    """
    s = _get_state()
    report = s.sentinel.latest_osint_report
    if report is None:
        return {
            "status": "no_scan_yet",
            "message": "SENTINEL has not performed an OSINT scan yet. "
                       "Run simulation steps or POST /osint/scan.",
        }
    return report.to_dict()


@router.post("/osint/scan", summary="Trigger a fresh OSINT scan")
async def trigger_osint_scan():
    """
    Forces SENTINEL to run a fresh OSINT Dark Signal Intelligence
    scan immediately, regardless of the scan interval.
    """
    s = _get_state()
    s.sentinel._run_osint_scan()
    report = s.sentinel.latest_osint_report
    if report is None:
        raise HTTPException(500, "OSINT scan failed")

    # Broadcast via WebSocket
    from nexus.api.routes.websocket import get_manager
    await get_manager().broadcast({
        "event": "osint_scan_complete",
        "data": {
            "signals_found": report.disruption_signals_found,
            "triggered_clusters": len(report.triggered_clusters),
            "summary": report.scan_summary,
        },
    })

    return report.to_dict()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Supplier Financial Health
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/financial", summary="Latest supplier financial radar report")
async def get_financial_report():
    """
    Returns the most recent Supplier Financial Health Radar analysis:
    - Per-supplier composite score and status
    - Category breakdowns (financial, operational, market, satellite)
    - Alert flags and trend direction
    - Human-readable risk reasoning
    """
    s = _get_state()
    report = s.sentinel.latest_financial_report
    if report is None:
        return {
            "status": "no_scan_yet",
            "message": "SENTINEL has not performed a financial scan yet.",
        }
    return report.to_dict()


@router.post("/financial/scan", summary="Trigger a fresh financial scan")
async def trigger_financial_scan():
    """
    Forces SENTINEL to run a fresh Supplier Financial Health Radar
    scan immediately.
    """
    s = _get_state()
    s.sentinel._run_financial_scan()
    report = s.sentinel.latest_financial_report
    if report is None:
        raise HTTPException(500, "Financial scan failed")

    from nexus.api.routes.websocket import get_manager
    await get_manager().broadcast({
        "event": "financial_scan_complete",
        "data": {
            "green": report.green_count,
            "amber": report.amber_count,
            "red": report.red_count,
            "summary": report.summary,
        },
    })

    return report.to_dict()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Decision History
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/decisions", summary="Recent SENTINEL decisions")
async def get_decisions(
    n: int = Query(20, ge=1, le=100, description="Number of recent decisions"),
    target: str = Query(None, description="Filter by target node ID"),
):
    """
    Returns SENTINEL's recent risk-flag decisions with
    full reasoning and signal breakdowns.

    Each decision includes:
    - action_type: risk_flag_red | risk_flag_amber
    - target: node_id
    - signal_breakdown: per-category risk scores
    - reasoning: human-readable explanation
    """
    s = _get_state()

    if target:
        decisions = s.sentinel.get_decisions_for_target(target)
        decisions = decisions[-n:]
    else:
        decisions = s.sentinel.get_recent_decisions(n)

    return {
        "total": len(decisions),
        "decisions": [d.to_dict() for d in decisions],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Node Risk Contribution (from suppliers)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get(
    "/supplier-risk-map",
    summary="Per-node risk contribution from suppliers",
)
async def get_supplier_risk_map():
    """
    Returns the risk contribution to each node from its connected
    suppliers.  Higher values indicate weaker supplier health
    affecting that node.
    """
    s = _get_state()
    risk_map = s.sentinel.financial_radar.get_node_risk_contribution()

    # Sort by risk descending
    sorted_map = dict(
        sorted(risk_map.items(), key=lambda x: x[1], reverse=True)
    )
    return {
        "node_risks": {
            k: round(v, 4) for k, v in sorted_map.items()
        },
    }
