"""Smoke test for NEXUS FastAPI Backend (Component 4)."""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000"

def get(path):
    """GET request and return parsed JSON."""
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

def post(path, data=None):
    """POST request with JSON body."""
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

errors = []

def check(name, condition, detail=""):
    if condition:
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} - {detail}")
        errors.append(name)

# ── Test 1: Health & Root ──
print("=" * 64)
print("TEST 1: Health & Root")
print("=" * 64)
root = get("/")
check("Root returns name", root["name"] == "NEXUS Supply Chain Intelligence API")
check("Root has endpoints", "endpoints" in root)

health = get("/health")
check("Health check", health["status"] == "healthy")
check("Simulation initialised", health["simulation_initialised"])
print()

# ── Test 2: Simulation Status ──
print("=" * 64)
print("TEST 2: Simulation Status")
print("=" * 64)
status = get("/api/v1/simulation/status")
check("Status returns step", "step" in status)
check("Status shows paused", status["status"] == "paused")
check("6 agents present", len(status["agents"]) == 6)
print()

# ── Test 3: Network Endpoints ──
print("=" * 64)
print("TEST 3: Network Endpoints")
print("=" * 64)
nodes = get("/api/v1/network/nodes")
check("15 nodes", nodes["total"] == 15)
check("Nodes have health", "health_score" in nodes["nodes"][0])

ports = get("/api/v1/network/nodes?node_type=port")
check("Port filter works", all(n["type"] == "port" for n in ports["nodes"]))

hamburg = get("/api/v1/network/nodes/hamburg_port")
check("Hamburg node exists", hamburg["node"]["id"] == "hamburg_port")
check("Hamburg has downstream", len(hamburg["downstream_nodes"]) > 0)

edges = get("/api/v1/network/edges")
check("35 edges", edges["total"] == 35)

sea_edges = get("/api/v1/network/edges?mode=sea")
check("Sea filter works", all(e["mode"] == "sea" for e in sea_edges["edges"]))

paths = get("/api/v1/network/paths/shanghai_port/frankfurt_dc?k=3")
check("3 paths found", paths["paths_found"] == 3)
check("Paths have metrics", "total_transit_hours" in paths["routes"][0])
check("Green-resilience score", "green_resilience_score" in paths["routes"][0])
print()

# ── Test 4: Shipment Endpoints ──
print("=" * 64)
print("TEST 4: Shipment Endpoints")
print("=" * 64)
shipments = get("/api/v1/network/shipments")
check("30 shipments", shipments["total"] == 30)
check("Has summary stats", "delivered" in shipments["summary"])

platinum = get("/api/v1/network/shipments?priority=platinum")
check("Priority filter works",
      all(s["priority_tier"] == "platinum" for s in platinum["shipments"]))

carriers = get("/api/v1/network/carriers")
check("8 carriers", carriers["total"] == 8)

suppliers = get("/api/v1/network/suppliers")
check("8 suppliers", suppliers["total"] == 8)
print()

# ── Test 5: Step Simulation ──
print("=" * 64)
print("TEST 5: Step Simulation")
print("=" * 64)
step_result = post("/api/v1/simulation/step?n=3")
check("3 steps executed", step_result["steps_executed"] == 3)
check("Step results present", len(step_result["results"]) == 3)
print(f"  Steps: {[r['step'] for r in step_result['results']]}")
print()

# ── Test 6: Inject Hamburg Scenario ──
print("=" * 64)
print("TEST 6: Inject Hamburg Scenario")
print("=" * 64)
scenario = post("/api/v1/disruption/scenario/hamburg_storm")
check("Scenario injected", scenario["events_injected"] >= 3)
check("Events returned", len(scenario["events"]) >= 3)
print(f"  Events: {[e['type'] for e in scenario['events']]}")

active = get("/api/v1/disruption/active")
check("Active disruptions", active["total"] >= 3)
print()

# ── Test 7: Step After Disruption ──
print("=" * 64)
print("TEST 7: Step After Disruption + SENTINEL Detection")
print("=" * 64)
step2 = post("/api/v1/simulation/step?n=5")
check("5 more steps", step2["steps_executed"] == 5)

# Check SENTINEL detected it
risk_report = get("/api/v1/sentinel/risk-report")
check("Risk report has nodes", len(risk_report["nodes"]) == 15)
check("OSINT summary present", "OSINT" in risk_report.get("osint_summary", ""))

# Find Hamburg risk
hamburg_risk = None
for n in risk_report["nodes"]:
    if n["node_id"] == "hamburg_port":
        hamburg_risk = n
        break
check("Hamburg in risk report", hamburg_risk is not None)
if hamburg_risk:
    check("Hamburg risk elevated", hamburg_risk["risk_score"] > 0.3,
          f"got {hamburg_risk['risk_score']}")
    print(f"  Hamburg risk: {hamburg_risk['risk_score']:.4f} ({hamburg_risk['status']})")
print()

# ── Test 8: SENTINEL Endpoints ──
print("=" * 64)
print("TEST 8: SENTINEL Endpoints")
print("=" * 64)
node_risk = get("/api/v1/sentinel/risk/hamburg_port")
check("Node risk detail", "signal_breakdown" in node_risk)
print(f"  Hamburg breakdown: {node_risk['signal_breakdown']}")

# Trigger OSINT scan
osint = post("/api/v1/sentinel/osint/scan")
check("OSINT scan complete", osint.get("total_posts_analysed", 0) == 40)
check("Triggered clusters", len(osint.get("triggered_clusters", [])) > 0)

# Trigger financial scan
financial = post("/api/v1/sentinel/financial/scan")
check("Financial scan complete", financial.get("total_suppliers", 0) == 8)
check("Red suppliers", financial.get("red", 0) >= 2)

decisions = get("/api/v1/sentinel/decisions?n=10")
check("Decisions endpoint works", "total" in decisions)
print(f"  Total SENTINEL decisions: {decisions['total']}")

supplier_map = get("/api/v1/sentinel/supplier-risk-map")
check("Supplier risk map", "node_risks" in supplier_map)
print()

# ── Test 9: Disruption Queries ──
print("=" * 64)
print("TEST 9: Disruption Queries")
print("=" * 64)
scenarios = get("/api/v1/disruption/scenarios")
check("3 scenarios available", len(scenarios["scenarios"]) == 3)

# Inject ad-hoc weather
weather = post("/api/v1/disruption/inject/weather", {
    "node_id": "la_port",
    "severity": 6.0,
    "duration_hours": 48,
})
check("Weather injection", weather["status"] == "injected")
check("Weather event returned", weather["event"]["type"] == "weather")
print()

# ── Test 10: Simulation Reset ──
print("=" * 64)
print("TEST 10: Simulation Reset")
print("=" * 64)
reset = post("/api/v1/simulation/reset", {
    "seed": 123,
    "max_steps": 100,
    "disruption_probability": 0.05,
    "speed": 0.5,
})
check("Reset successful", reset["status"] == "reset")
check("Reset step = 0", reset["step"] == 0)
check("Custom max_steps", reset["max_steps"] == 100)

status2 = get("/api/v1/simulation/status")
check("Step reset to 0", status2["step"] == 0)
print()

# ── Summary ──
print("=" * 64)
if errors:
    print(f"FAILED: {len(errors)} test(s): {errors}")
else:
    print("ALL COMPONENT 4 TESTS PASSED")
print("=" * 64)
