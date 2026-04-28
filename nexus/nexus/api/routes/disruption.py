"""
Disruption injection and query endpoints.

Provides both scripted demo scenarios (Hamburg storm, Red Sea crisis,
Shanghai lockdown) and ad-hoc disruption injection for live demos.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/disruption", tags=["Disruptions"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Request Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class WeatherInjection(BaseModel):
    """Inject a weather disruption at a specific node."""
    node_id: str = Field(..., description="Target node ID")
    severity: float = Field(7.0, ge=1.0, le=10.0, description="1-10 severity")
    duration_hours: int = Field(72, ge=1, le=720, description="Duration in hours")


class CongestionInjection(BaseModel):
    """Inject congestion at a specific node."""
    node_id: str = Field(..., description="Target node ID")
    queue_multiplier: float = Field(3.0, ge=1.1, le=10.0, description="Queue depth multiplier")
    duration_hours: int = Field(96, ge=1, le=720, description="Duration in hours")


class CarrierInjection(BaseModel):
    """Inject carrier performance degradation."""
    carrier_id: str = Field(..., description="Target carrier ID")
    otp_drop: float = Field(0.20, ge=0.05, le=0.80, description="OTP drop fraction")
    duration_hours: int = Field(168, ge=1, le=720, description="Duration in hours")


class GeopoliticalInjection(BaseModel):
    """Inject geopolitical risk on a lane."""
    from_node: str = Field(..., description="Source node ID")
    to_node: str = Field(..., description="Destination node ID")
    risk_increase: float = Field(0.4, ge=0.1, le=1.0, description="Risk increase")
    duration_hours: int = Field(336, ge=1, le=720, description="Duration in hours")


class SupplierInjection(BaseModel):
    """Inject supplier financial distress."""
    supplier_id: str = Field(..., description="Supplier ID")
    connected_node: str = Field(..., description="Connected node ID")
    severity: float = Field(7.0, ge=1.0, le=10.0, description="1-10 severity")
    duration_hours: int = Field(720, ge=1, le=1440, description="Duration in hours")


class LaborInjection(BaseModel):
    """Inject labor disruption at a node."""
    node_id: str = Field(..., description="Target node ID")
    severity: float = Field(6.0, ge=1.0, le=10.0, description="1-10 severity")
    duration_hours: int = Field(120, ge=1, le=720, description="Duration in hours")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Dependency
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _get_state():
    from nexus.api.main import sim
    if sim.env is None:
        raise HTTPException(503, "Simulation not initialised.")
    return sim


def _validate_node(sim_state, node_id: str):
    if node_id not in sim_state.env.network.nodes:
        raise HTTPException(404, f"Node '{node_id}' not found")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Demo Scenarios
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


AVAILABLE_SCENARIOS = {
    "hamburg_storm": "Hamburg port storm surge with supplier/carrier cascading effects",
    "red_sea_crisis": "Red Sea geopolitical crisis affecting Asia-Europe lanes",
    "shanghai_lockdown": "Shanghai COVID-era lockdown with massive throughput reduction",
}


@router.post(
    "/scenario/{scenario_name}",
    summary="Inject a pre-built demo scenario",
)
async def inject_scenario(scenario_name: str):
    """
    Inject one of three pre-built disruption scenarios:

    - **hamburg_storm**: Weather + congestion at Hamburg, Gujarat supplier
      distress, ONE carrier degradation
    - **red_sea_crisis**: Geopolitical risk spikes on Asia-Europe lanes
    - **shanghai_lockdown**: Severe throughput reduction + supplier stress
    """
    s = _get_state()
    de = s.env.disruption_engine
    step = s.env.current_step

    if scenario_name == "hamburg_storm":
        events = de.inject_hamburg_scenario(step)
    elif scenario_name == "red_sea_crisis":
        events = de.inject_red_sea_scenario(step)
    elif scenario_name == "shanghai_lockdown":
        events = de.inject_shanghai_lockdown_scenario(step)
    else:
        raise HTTPException(
            404,
            f"Unknown scenario '{scenario_name}'. "
            f"Available: {list(AVAILABLE_SCENARIOS.keys())}",
        )

    # Broadcast via WebSocket
    from nexus.api.routes.websocket import get_manager
    mgr = get_manager()
    for event in events:
        await mgr.broadcast_disruption(event.to_dict())

    return {
        "scenario": scenario_name,
        "description": AVAILABLE_SCENARIOS[scenario_name],
        "events_injected": len(events),
        "events": [e.to_dict() for e in events],
        "simulation_step": step,
    }


@router.get("/scenarios", summary="List available demo scenarios")
async def list_scenarios():
    """Returns all available pre-built demo scenarios."""
    return {"scenarios": AVAILABLE_SCENARIOS}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Ad-Hoc Injection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.post("/inject/weather", summary="Inject weather disruption")
async def inject_weather(body: WeatherInjection):
    """Inject a weather event at a specific node."""
    s = _get_state()
    _validate_node(s, body.node_id)

    event = s.env.disruption_engine.inject_weather(
        body.node_id, body.severity, body.duration_hours, s.env.current_step,
    )

    from nexus.api.routes.websocket import get_manager
    await get_manager().broadcast_disruption(event.to_dict())

    return {
        "status": "injected",
        "event": event.to_dict(),
    }


@router.post("/inject/congestion", summary="Inject congestion")
async def inject_congestion(body: CongestionInjection):
    """Inject port/hub congestion at a specific node."""
    s = _get_state()
    _validate_node(s, body.node_id)

    event = s.env.disruption_engine.inject_congestion(
        body.node_id, body.queue_multiplier, body.duration_hours,
        s.env.current_step,
    )

    from nexus.api.routes.websocket import get_manager
    await get_manager().broadcast_disruption(event.to_dict())

    return {
        "status": "injected",
        "event": event.to_dict(),
    }


@router.post("/inject/carrier", summary="Inject carrier disruption")
async def inject_carrier(body: CarrierInjection):
    """Inject carrier performance degradation."""
    s = _get_state()

    event = s.env.disruption_engine.inject_carrier_disruption(
        body.carrier_id, body.otp_drop, body.duration_hours,
        s.env.current_step,
    )

    from nexus.api.routes.websocket import get_manager
    await get_manager().broadcast_disruption(event.to_dict())

    return {
        "status": "injected",
        "event": event.to_dict(),
    }


@router.post("/inject/geopolitical", summary="Inject geopolitical risk")
async def inject_geopolitical(body: GeopoliticalInjection):
    """Inject geopolitical risk increase on a lane."""
    s = _get_state()
    _validate_node(s, body.from_node)
    _validate_node(s, body.to_node)

    event = s.env.disruption_engine.inject_geopolitical(
        body.from_node, body.to_node, body.risk_increase,
        body.duration_hours, s.env.current_step,
    )

    from nexus.api.routes.websocket import get_manager
    await get_manager().broadcast_disruption(event.to_dict())

    return {
        "status": "injected",
        "event": event.to_dict(),
    }


@router.post("/inject/supplier", summary="Inject supplier distress")
async def inject_supplier(body: SupplierInjection):
    """Inject supplier financial distress."""
    s = _get_state()
    _validate_node(s, body.connected_node)

    event = s.env.disruption_engine.inject_supplier_stress(
        body.supplier_id, body.connected_node, body.severity,
        body.duration_hours, s.env.current_step,
    )

    from nexus.api.routes.websocket import get_manager
    await get_manager().broadcast_disruption(event.to_dict())

    return {
        "status": "injected",
        "event": event.to_dict(),
    }


@router.post("/inject/labor", summary="Inject labor disruption")
async def inject_labor(body: LaborInjection):
    """Inject labor disruption (strike, work stoppage)."""
    s = _get_state()
    _validate_node(s, body.node_id)

    event = s.env.disruption_engine.inject_labor(
        body.node_id, body.severity, body.duration_hours,
        s.env.current_step,
    )

    from nexus.api.routes.websocket import get_manager
    await get_manager().broadcast_disruption(event.to_dict())

    return {
        "status": "injected",
        "event": event.to_dict(),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Queries
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/active", summary="List active disruptions")
async def list_active():
    """Returns all currently active disruption events."""
    s = _get_state()
    events = s.env.disruption_engine.get_active_events()
    return {
        "total": len(events),
        "events": events,
    }


@router.get("/history", summary="List resolved disruptions")
async def list_history():
    """Returns all resolved (expired) disruption events."""
    s = _get_state()
    events = s.env.disruption_engine.get_history()
    return {
        "total": len(events),
        "events": events,
    }
