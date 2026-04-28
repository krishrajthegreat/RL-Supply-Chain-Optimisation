"""
Network graph data model for the NEXUS supply chain simulation.

Manages the global logistics network topology — 15 nodes (ports, DCs, hubs)
and 35 directed edges (lanes) — with pathfinding, disruption effects,
route metric computation, and circuit breaker state management.
"""

import heapq
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from nexus.data import load_json


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Enums
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class CircuitState(str, Enum):
    """Circuit breaker state for a network node."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Isolated — excluded from routing
    HALF_OPEN = "half_open" # Probing recovery


class TransportMode(str, Enum):
    """Transport mode for a lane/edge."""
    SEA = "sea"
    ROAD = "road"
    RAIL = "rail"
    AIR = "air"


# GLEC carbon emission factors (kg CO2 per tonne-km)
CARBON_FACTORS = {
    TransportMode.AIR: 2.100,
    TransportMode.ROAD: 0.096,
    TransportMode.SEA: 0.016,
    TransportMode.RAIL: 0.028,
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Data Models
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class Node:
    """
    A supply chain network node — port, distribution center, or logistics hub.

    Tracks both static properties (coordinates, type) and dynamic state
    (health, congestion, circuit breaker status) that evolves during simulation.
    """
    id: str
    name: str
    type: str              # "port" | "dc" | "hub"
    region: str
    country: str
    lat: float
    lng: float
    throughput_capacity: int
    current_queue_depth: int
    avg_dwell_hours: float
    health_score: float
    circuit_state: CircuitState
    weather_severity: float
    congestion_score: float

    # Cached originals for reset and ratio computation
    _original_throughput: int = field(init=False, repr=False)
    _original_dwell_hours: float = field(init=False, repr=False)
    _original_queue_depth: int = field(init=False, repr=False)

    def __post_init__(self):
        if isinstance(self.circuit_state, str):
            self.circuit_state = CircuitState(self.circuit_state)
        self._original_throughput = self.throughput_capacity
        self._original_dwell_hours = self.avg_dwell_hours
        self._original_queue_depth = self.current_queue_depth

    # ── Health Computation ────────────────────────────────────────

    def compute_health(self) -> float:
        """
        Recompute health score from current operational metrics.

        Health = weighted sum of four normalised factors:
          30% throughput ratio   (current / baseline)
          25% congestion factor  (inverse of congestion)
          25% weather factor     (inverse of weather severity)
          20% queue factor       (inverse of queue pressure)
        """
        throughput_ratio = min(
            self.throughput_capacity / max(self._original_throughput, 1), 1.0
        )
        congestion_factor = 1.0 - self.congestion_score
        weather_factor = 1.0 - min(self.weather_severity / 10.0, 1.0) * 0.5
        queue_pressure = min(
            self.current_queue_depth / max(self._original_throughput * 0.02, 1), 1.0
        )
        queue_factor = 1.0 - queue_pressure

        self.health_score = max(0.0, min(1.0,
            0.30 * throughput_ratio
            + 0.25 * congestion_factor
            + 0.25 * weather_factor
            + 0.20 * queue_factor
        ))
        return self.health_score

    @property
    def throughput_ratio(self) -> float:
        return self.throughput_capacity / max(self._original_throughput, 1)

    @property
    def dwell_ratio(self) -> float:
        return self.avg_dwell_hours / max(self._original_dwell_hours, 1)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "region": self.region,
            "country": self.country,
            "lat": self.lat,
            "lng": self.lng,
            "throughput_capacity": self.throughput_capacity,
            "current_queue_depth": self.current_queue_depth,
            "avg_dwell_hours": round(self.avg_dwell_hours, 1),
            "health_score": round(self.health_score, 4),
            "circuit_state": self.circuit_state.value,
            "weather_severity": round(self.weather_severity, 2),
            "congestion_score": round(self.congestion_score, 4),
        }


@dataclass
class Edge:
    """
    A directed lane connecting two network nodes.

    Carries static cost/performance attributes and dynamic state
    that degrades under disruption (risk premiums, reliability drops).
    """
    from_node: str
    to_node: str
    mode: TransportMode
    transit_hours: float
    cost_per_teu: float
    carbon_kg_per_teu: float
    reliability_score: float
    geopolitical_risk_score: float
    capacity_utilization: float

    _original_transit_hours: float = field(init=False, repr=False)
    _original_cost: float = field(init=False, repr=False)
    _original_reliability: float = field(init=False, repr=False)

    def __post_init__(self):
        if isinstance(self.mode, str):
            self.mode = TransportMode(self.mode)
        self._original_transit_hours = self.transit_hours
        self._original_cost = self.cost_per_teu
        self._original_reliability = self.reliability_score

    def effective_cost(self, risk_weight: float = 0.3) -> float:
        """Cost adjusted for geopolitical risk and reliability."""
        risk_premium = self.geopolitical_risk_score * self.cost_per_teu * risk_weight
        reliability_penalty = (1.0 - self.reliability_score) * self.cost_per_teu * 0.1
        return self.cost_per_teu + risk_premium + reliability_penalty

    def to_dict(self) -> dict:
        return {
            "from": self.from_node,
            "to": self.to_node,
            "mode": self.mode.value,
            "transit_hours": self.transit_hours,
            "cost_per_teu": round(self.cost_per_teu, 2),
            "carbon_kg_per_teu": round(self.carbon_kg_per_teu, 1),
            "reliability_score": round(self.reliability_score, 4),
            "geopolitical_risk_score": round(self.geopolitical_risk_score, 4),
            "capacity_utilization": round(self.capacity_utilization, 4),
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Supply Chain Network
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SupplyChainNetwork:
    """
    Global supply chain network model.

    Manages the logistics graph topology with nodes (ports, DCs, hubs),
    directed edges (lanes), and provides:
      • Dijkstra single-source shortest path
      • Yen's K-shortest simple paths
      • Route metric aggregation (time / cost / carbon / risk)
      • Disruption effect application and rollback
      • Circuit breaker state management
    """

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: dict[tuple[str, str], Edge] = {}
        self.adjacency: dict[str, list[str]] = {}       # forward adjacency
        self.reverse_adj: dict[str, list[str]] = {}      # reverse adjacency
        self._seed_data: dict | None = None              # cached seed JSON
        self._load_network()

    # ── Initialisation ────────────────────────────────────────────

    def _load_network(self):
        """Load network topology from JSON seed data (cached after first read)."""
        if self._seed_data is None:
            self._seed_data = load_json("nodes.json")
        data = self._seed_data

        for node_data in data["nodes"]:
            node = Node(**node_data)
            self.nodes[node.id] = node
            self.adjacency.setdefault(node.id, [])
            self.reverse_adj.setdefault(node.id, [])

        for edge_data in data["edges"]:
            edge = Edge(
                from_node=edge_data["from"],
                to_node=edge_data["to"],
                mode=edge_data["mode"],
                transit_hours=edge_data["transit_hours"],
                cost_per_teu=edge_data["cost_per_teu"],
                carbon_kg_per_teu=edge_data["carbon_kg_per_teu"],
                reliability_score=edge_data["reliability_score"],
                geopolitical_risk_score=edge_data["geopolitical_risk_score"],
                capacity_utilization=edge_data["capacity_utilization"],
            )
            self.edges[(edge.from_node, edge.to_node)] = edge
            if edge.to_node not in self.adjacency[edge.from_node]:
                self.adjacency[edge.from_node].append(edge.to_node)
            if edge.from_node not in self.reverse_adj[edge.to_node]:
                self.reverse_adj[edge.to_node].append(edge.from_node)

    # ── Accessors ─────────────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def get_edge(self, from_id: str, to_id: str) -> Optional[Edge]:
        return self.edges.get((from_id, to_id))

    def get_neighbors(self, node_id: str) -> list[str]:
        return list(self.adjacency.get(node_id, []))

    def get_edges_from(self, node_id: str) -> list[Edge]:
        return [
            self.edges[(node_id, nb)]
            for nb in self.adjacency.get(node_id, [])
            if (node_id, nb) in self.edges
        ]

    def get_edges_to(self, node_id: str) -> list[Edge]:
        return [
            self.edges[(nb, node_id)]
            for nb in self.reverse_adj.get(node_id, [])
            if (nb, node_id) in self.edges
        ]

    def get_active_nodes(self) -> list[Node]:
        """Nodes with circuit CLOSED or HALF_OPEN."""
        return [n for n in self.nodes.values()
                if n.circuit_state != CircuitState.OPEN]

    def get_nodes_by_type(self, node_type: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.type == node_type]

    @property
    def node_ids(self) -> list[str]:
        return list(self.nodes.keys())

    @property
    def num_nodes(self) -> int:
        return len(self.nodes)

    @property
    def num_edges(self) -> int:
        return len(self.edges)

    # ── Pathfinding — Dijkstra ────────────────────────────────────

    def dijkstra(
        self,
        start: str,
        end: str,
        weight: str = "transit_hours",
        avoid_open_circuits: bool = True,
        excluded_nodes: Optional[set[str]] = None,
        excluded_edges: Optional[set[tuple[str, str]]] = None,
    ) -> tuple[list[str], float]:
        """
        Shortest path via Dijkstra's algorithm.

        Args:
            start / end: Source and destination node IDs.
            weight: Edge attribute to minimise
                    ("transit_hours" | "cost_per_teu" | "carbon_kg_per_teu").
            avoid_open_circuits: Skip nodes with OPEN circuit state.
            excluded_nodes: Set of node IDs to skip (for Yen's algorithm).
            excluded_edges: Set of (from, to) edge keys to skip.

        Returns:
            (path, total_weight) or ([], inf) if unreachable.
        """
        if start not in self.nodes or end not in self.nodes:
            return [], float("inf")

        excluded_nodes = excluded_nodes or set()
        excluded_edges = excluded_edges or set()

        dist: dict[str, float] = {nid: float("inf") for nid in self.nodes}
        dist[start] = 0.0
        prev: dict[str, Optional[str]] = {nid: None for nid in self.nodes}
        visited: set[str] = set()
        heap: list[tuple[float, str]] = [(0.0, start)]

        while heap:
            d, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)
            if u == end:
                break

            for v in self.adjacency.get(u, []):
                if v in visited or v in excluded_nodes:
                    continue
                if (u, v) in excluded_edges:
                    continue
                if (avoid_open_circuits
                        and v != end
                        and self.nodes[v].circuit_state == CircuitState.OPEN):
                    continue

                edge = self.edges.get((u, v))
                if edge is None:
                    continue

                w = getattr(edge, weight, edge.transit_hours)
                new_dist = d + w
                if new_dist < dist[v]:
                    dist[v] = new_dist
                    prev[v] = u
                    heapq.heappush(heap, (new_dist, v))

        if dist[end] == float("inf"):
            return [], float("inf")

        path: list[str] = []
        cur: Optional[str] = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        return path, dist[end]

    # ── Pathfinding — Yen's K-Shortest ────────────────────────────

    def k_shortest_paths(
        self,
        start: str,
        end: str,
        k: int = 5,
        weight: str = "transit_hours",
        avoid_open_circuits: bool = True,
    ) -> list[tuple[list[str], float]]:
        """
        Find K shortest simple paths (Yen's algorithm).

        Returns a list of (path, total_weight) sorted ascending by weight.
        """
        first_path, first_cost = self.dijkstra(
            start, end, weight, avoid_open_circuits
        )
        if not first_path:
            return []

        A: list[tuple[list[str], float]] = [(first_path, first_cost)]
        B: list[tuple[float, int, list[str]]] = []  # (cost, tiebreaker, path)
        tb = 0  # tiebreaker counter for heap stability

        for i in range(1, k):
            prev_path = A[i - 1][0]

            for j in range(len(prev_path) - 1):
                spur_node = prev_path[j]
                root_path = prev_path[: j + 1]

                # Collect edges to exclude (shared root prefix)
                excl_edges: set[tuple[str, str]] = set()
                for (path_a, _) in A:
                    if len(path_a) > j and path_a[: j + 1] == root_path:
                        excl_edges.add((path_a[j], path_a[j + 1]))

                # Exclude root path nodes except spur node
                excl_nodes = set(root_path[:-1])

                spur_path, spur_cost = self.dijkstra(
                    spur_node, end, weight, avoid_open_circuits,
                    excluded_nodes=excl_nodes, excluded_edges=excl_edges,
                )

                if spur_path:
                    total_path = root_path[:-1] + spur_path
                    # Recompute exact total cost
                    total_cost = self._path_cost(total_path, weight)
                    # Deduplicate
                    if not any(p == total_path for p, _ in A):
                        if not any(p == total_path for _, _, p in B):
                            tb += 1
                            heapq.heappush(B, (total_cost, tb, total_path))

            if not B:
                break
            cost, _, path = heapq.heappop(B)
            A.append((path, cost))

        return A

    def _path_cost(self, path: list[str], weight: str) -> float:
        """Sum a weight attribute over a path's edges."""
        total = 0.0
        for i in range(len(path) - 1):
            edge = self.edges.get((path[i], path[i + 1]))
            if edge:
                total += getattr(edge, weight, edge.transit_hours)
            else:
                return float("inf")
        return total

    # ── Route Metrics ─────────────────────────────────────────────

    def compute_route_metrics(self, route: list[str]) -> dict:
        """Aggregate time / cost / carbon / risk / reliability for a route."""
        total_hours = 0.0
        total_cost = 0.0
        total_carbon = 0.0
        max_geo_risk = 0.0
        min_reliability = 1.0
        modes: list[str] = []

        for i in range(len(route) - 1):
            edge = self.edges.get((route[i], route[i + 1]))
            if edge is None:
                return {"error": f"No edge {route[i]} → {route[i + 1]}"}

            total_hours += edge.transit_hours
            total_cost += edge.cost_per_teu
            total_carbon += edge.carbon_kg_per_teu
            max_geo_risk = max(max_geo_risk, edge.geopolitical_risk_score)
            min_reliability = min(min_reliability, edge.reliability_score)
            modes.append(edge.mode.value)

            # Dwell at intermediate nodes
            if i < len(route) - 2:
                node = self.nodes.get(route[i + 1])
                if node:
                    total_hours += node.avg_dwell_hours

        # Green-Resilience Score: lower carbon + higher reliability = better
        carbon_normalised = 1.0 - min(total_carbon / 5000.0, 1.0)
        green_resilience = 0.5 * carbon_normalised + 0.5 * min_reliability

        return {
            "route": route,
            "total_transit_hours": round(total_hours, 1),
            "total_cost_usd": round(total_cost, 2),
            "total_carbon_kg": round(total_carbon, 1),
            "max_geopolitical_risk": round(max_geo_risk, 4),
            "min_reliability": round(min_reliability, 4),
            "transport_modes": modes,
            "num_hops": len(route) - 1,
            "green_resilience_score": round(green_resilience, 4),
        }

    # ── Circuit Breaker ───────────────────────────────────────────

    def set_circuit_state(self, node_id: str, state: CircuitState) -> dict:
        """Update a node's circuit breaker state.  Returns transition record."""
        node = self.nodes.get(node_id)
        if node is None:
            return {"error": f"Node {node_id} not found"}

        old = node.circuit_state
        node.circuit_state = state
        return {
            "node_id": node_id,
            "old_state": old.value,
            "new_state": state.value,
            "health_score": round(node.health_score, 4),
        }

    def get_downstream_nodes(self, node_id: str, depth: int = 2) -> list[str]:
        """BFS to find nodes reachable within *depth* hops (forward)."""
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(node_id, 0)]
        downstream: list[str] = []

        while queue:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)
            if current != node_id:
                downstream.append(current)
            for nb in self.adjacency.get(current, []):
                if nb not in visited:
                    queue.append((nb, d + 1))

        return downstream

    def get_upstream_nodes(self, node_id: str, depth: int = 2) -> list[str]:
        """BFS backward to find feeder nodes within *depth* hops."""
        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(node_id, 0)]
        upstream: list[str] = []

        while queue:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)
            if current != node_id:
                upstream.append(current)
            for nb in self.reverse_adj.get(current, []):
                if nb not in visited:
                    queue.append((nb, d + 1))

        return upstream

    def get_affected_shipments(
        self, node_id: str, shipments: list[dict]
    ) -> list[dict]:
        """Shipments whose planned route passes through *node_id*."""
        return [
            s for s in shipments
            if node_id in s.get("route_planned", [])
        ]

    # ── Disruption Effects ────────────────────────────────────────

    def apply_weather_disruption(self, node_id: str, severity: float):
        """Degrade throughput 40-80 % proportional to severity."""
        node = self.nodes.get(node_id)
        if not node:
            return
        node.weather_severity = min(10.0, max(node.weather_severity, severity))
        degradation = 0.4 + (severity / 10.0) * 0.4          # 40-80 %
        node.throughput_capacity = max(1, int(
            node._original_throughput * (1.0 - degradation)
        ))
        # Cap dwell hours to 5× original to stay within obs space bounds
        node.avg_dwell_hours = min(
            node._original_dwell_hours * 5.0,
            node._original_dwell_hours * (1.0 + degradation),
        )
        node.current_queue_depth = int(
            node._original_queue_depth * (1.0 + degradation * 0.8)
        )
        node.compute_health()

    def apply_congestion(self, node_id: str, queue_multiplier: float = 3.0):
        """Spike queue depth and dwell time."""
        node = self.nodes.get(node_id)
        if not node:
            return
        # Cap queue multiplier to prevent obs-space overflow
        queue_multiplier = min(queue_multiplier, 10.0)
        node.current_queue_depth = int(
            node._original_queue_depth * queue_multiplier
        )
        node.congestion_score = min(1.0, node.congestion_score + 0.4)
        # Cap dwell hours to 5× original
        node.avg_dwell_hours = min(
            node._original_dwell_hours * 5.0,
            node._original_dwell_hours * (1.0 + (queue_multiplier - 1) * 0.5),
        )
        node.compute_health()

    def apply_geopolitical_risk(
        self, from_id: str, to_id: str, risk_increase: float
    ):
        """Raise geopolitical risk premium on a lane."""
        edge = self.edges.get((from_id, to_id))
        if not edge:
            return
        edge.geopolitical_risk_score = min(
            1.0, edge.geopolitical_risk_score + risk_increase
        )
        edge.cost_per_teu = edge._original_cost * (
            1.0 + edge.geopolitical_risk_score * 0.5
        )
        edge.reliability_score = max(
            0.0, edge._original_reliability - risk_increase * 0.3
        )

    # ── Reset ─────────────────────────────────────────────────────

    def reset_node(self, node_id: str):
        """Restore a single node to seed-data state."""
        data = self._seed_data or load_json("nodes.json")
        for nd in data["nodes"]:
            if nd["id"] == node_id:
                node = self.nodes[node_id]
                node.throughput_capacity = nd["throughput_capacity"]
                node.current_queue_depth = nd["current_queue_depth"]
                node.avg_dwell_hours = nd["avg_dwell_hours"]
                node.weather_severity = nd["weather_severity"]
                node.congestion_score = nd["congestion_score"]
                node.circuit_state = CircuitState(nd["circuit_state"])
                node._original_throughput = nd["throughput_capacity"]
                node._original_dwell_hours = nd["avg_dwell_hours"]
                node._original_queue_depth = nd["current_queue_depth"]
                node.compute_health()
                break

    def reset_edge(self, from_id: str, to_id: str):
        """Restore a single edge to seed-data state."""
        data = self._seed_data or load_json("nodes.json")
        for ed in data["edges"]:
            if ed["from"] == from_id and ed["to"] == to_id:
                edge = self.edges[(from_id, to_id)]
                edge.transit_hours = ed["transit_hours"]
                edge.cost_per_teu = ed["cost_per_teu"]
                edge.carbon_kg_per_teu = ed["carbon_kg_per_teu"]
                edge.reliability_score = ed["reliability_score"]
                edge.geopolitical_risk_score = ed["geopolitical_risk_score"]
                edge.capacity_utilization = ed["capacity_utilization"]
                edge._original_transit_hours = ed["transit_hours"]
                edge._original_cost = ed["cost_per_teu"]
                edge._original_reliability = ed["reliability_score"]
                break

    def reset_all(self):
        """Reload entire network from seed data."""
        self.nodes.clear()
        self.edges.clear()
        self.adjacency.clear()
        self.reverse_adj.clear()
        self._load_network()

    # ── Serialisation ─────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Full network state as a JSON-serialisable dict."""
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "summary": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "open_circuits": sum(
                    1 for n in self.nodes.values()
                    if n.circuit_state == CircuitState.OPEN
                ),
                "half_open_circuits": sum(
                    1 for n in self.nodes.values()
                    if n.circuit_state == CircuitState.HALF_OPEN
                ),
                "avg_health": round(
                    sum(n.health_score for n in self.nodes.values())
                    / max(len(self.nodes), 1),
                    4,
                ),
            },
        }
