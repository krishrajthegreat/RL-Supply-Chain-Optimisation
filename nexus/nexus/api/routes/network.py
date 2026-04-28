"""
Network, shipment, carrier, and supplier query endpoints.

Provides read-only REST access to the current simulation state
including network topology, node health, shipment tracking,
carrier fleet status, and pathfinding.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/network", tags=["Network"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Dependency — access global simulation state
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _get_state():
    """Import simulation state lazily to avoid circular imports."""
    from nexus.api.main import sim
    if sim.env is None:
        raise HTTPException(503, "Simulation not initialised. POST /api/v1/simulation/reset first.")
    return sim


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Full State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/state", summary="Full network + simulation state")
async def get_full_state():
    """
    Returns the complete simulation state including network topology,
    all shipments, carriers, suppliers, risk scores, active disruptions,
    and episode metrics.
    """
    s = _get_state()
    return s.env.get_state()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Nodes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/nodes", summary="List all network nodes")
async def list_nodes(
    node_type: Optional[str] = Query(
        None, description="Filter by type: port | dc | hub"
    ),
):
    """
    Returns all 15 network nodes with current health, congestion,
    weather severity, circuit breaker state, and throughput.
    """
    s = _get_state()
    net = s.env.network
    nodes = [n.to_dict() for n in net.nodes.values()]

    if node_type:
        nodes = [n for n in nodes if n["type"] == node_type]

    return {
        "total": len(nodes),
        "nodes": nodes,
    }


@router.get("/nodes/{node_id}", summary="Get a single node")
async def get_node(node_id: str):
    """
    Returns detailed state for a specific node including health,
    circuit state, and downstream dependencies.
    """
    s = _get_state()
    net = s.env.network
    node = net.get_node(node_id)
    if node is None:
        raise HTTPException(404, f"Node '{node_id}' not found")

    downstream = net.get_downstream_nodes(node_id, depth=2)
    upstream = net.get_upstream_nodes(node_id, depth=2)
    edges_out = [e.to_dict() for e in net.get_edges_from(node_id)]
    edges_in = [e.to_dict() for e in net.get_edges_to(node_id)]

    # Shipments passing through this node
    affected_shipments = net.get_affected_shipments(
        node_id, s.env.shipments
    )

    # Risk score from SENTINEL
    from nexus.environment.supply_chain_env import NODE_TO_IDX
    risk_idx = NODE_TO_IDX.get(node_id, -1)
    risk_score = (
        float(s.env.risk_scores[risk_idx]) if risk_idx >= 0 else 0.0
    )

    return {
        "node": node.to_dict(),
        "risk_score": round(risk_score, 4),
        "downstream_nodes": downstream,
        "upstream_nodes": upstream,
        "outbound_edges": edges_out,
        "inbound_edges": edges_in,
        "affected_shipments": len(affected_shipments),
        "affected_shipment_ids": [
            sh["shipment_id"] for sh in affected_shipments
        ],
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Edges
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/edges", summary="List all network edges (lanes)")
async def list_edges(
    mode: Optional[str] = Query(
        None, description="Filter by mode: sea | road | rail | air"
    ),
):
    """
    Returns all 35 directed edges with transit time, cost, carbon,
    reliability, and geopolitical risk.
    """
    s = _get_state()
    edges = [e.to_dict() for e in s.env.network.edges.values()]

    if mode:
        edges = [e for e in edges if e["mode"] == mode]

    return {
        "total": len(edges),
        "edges": edges,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Pathfinding
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get(
    "/paths/{origin}/{destination}",
    summary="Find K-shortest paths between two nodes",
)
async def find_paths(
    origin: str,
    destination: str,
    k: int = Query(5, ge=1, le=10, description="Number of paths"),
    weight: str = Query(
        "transit_hours",
        description="Optimise for: transit_hours | cost_per_teu | carbon_kg_per_teu",
    ),
    avoid_open: bool = Query(
        True, description="Skip nodes with OPEN circuit breaker"
    ),
):
    """
    Computes K shortest paths using Yen's algorithm with full
    route metrics (time, cost, carbon, green-resilience score).
    """
    s = _get_state()
    net = s.env.network

    if origin not in net.nodes:
        raise HTTPException(404, f"Origin node '{origin}' not found")
    if destination not in net.nodes:
        raise HTTPException(404, f"Destination node '{destination}' not found")
    if weight not in ("transit_hours", "cost_per_teu", "carbon_kg_per_teu"):
        raise HTTPException(400, f"Invalid weight: '{weight}'")

    paths = net.k_shortest_paths(
        origin, destination, k=k,
        weight=weight, avoid_open_circuits=avoid_open,
    )

    results = []
    for path, cost in paths:
        metrics = net.compute_route_metrics(path)
        results.append(metrics)

    return {
        "origin": origin,
        "destination": destination,
        "weight": weight,
        "avoid_open_circuits": avoid_open,
        "paths_found": len(results),
        "routes": results,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Shipments
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/shipments", summary="List all shipments")
async def list_shipments(
    status: Optional[str] = Query(
        None,
        description="Filter: in_transit | at_node | blocked | delivered | route_error",
    ),
    priority: Optional[str] = Query(
        None,
        description="Filter: platinum | gold | silver",
    ),
    at_risk: Optional[bool] = Query(
        None,
        description="Filter to shipments at risk",
    ),
):
    """
    Returns all 30 shipments with current position, delay,
    SLA status, and routing information.
    """
    s = _get_state()
    shipments = [s.env._shipment_dict(sh) for sh in s.env.shipments]

    if status:
        shipments = [sh for sh in shipments if sh["status"] == status]
    if priority:
        shipments = [
            sh for sh in shipments if sh["priority_tier"] == priority
        ]
    if at_risk is not None:
        if at_risk:
            shipments = [
                sh for sh in shipments
                if sh["sla_breached"] or sh["total_delay_hours"] > 0
            ]
        else:
            shipments = [
                sh for sh in shipments
                if not sh["sla_breached"] and sh["total_delay_hours"] == 0
            ]

    # Summary stats
    total = len(s.env.shipments)
    delivered = sum(1 for sh in s.env.shipments if sh["delivered"])
    breached = sum(1 for sh in s.env.shipments if sh["sla_breached"])
    delayed = sum(
        1 for sh in s.env.shipments
        if sh["total_delay_hours"] > 0 and not sh["delivered"]
    )

    return {
        "total": total,
        "filtered": len(shipments),
        "summary": {
            "delivered": delivered,
            "in_transit": total - delivered,
            "sla_breached": breached,
            "delayed": delayed,
        },
        "shipments": shipments,
    }


@router.get("/shipments/{shipment_id}", summary="Get a single shipment")
async def get_shipment(shipment_id: str):
    """Returns detailed tracking for a specific shipment."""
    s = _get_state()

    for sh in s.env.shipments:
        if sh["shipment_id"] == shipment_id:
            result = s.env._shipment_dict(sh)
            # Add route metrics
            metrics = s.env.network.compute_route_metrics(
                sh["route_planned"]
            )
            result["route_metrics"] = metrics
            return result

    raise HTTPException(404, f"Shipment '{shipment_id}' not found")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Carriers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/carriers", summary="List all carriers")
async def list_carriers():
    """
    Returns all 8 carrier profiles with OTP, health score,
    capacity, and blackout status.
    """
    s = _get_state()
    return {
        "total": len(s.env.carriers),
        "carriers": s.env.carriers,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Suppliers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.get("/suppliers", summary="List all suppliers")
async def list_suppliers():
    """
    Returns all 8 supplier profiles with composite health,
    status, and connected nodes.
    """
    s = _get_state()
    return {
        "total": len(s.env.suppliers),
        "suppliers": s.env.suppliers,
    }
