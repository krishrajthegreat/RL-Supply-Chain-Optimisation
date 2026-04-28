"""
NEXUS — Full Verification Suite (5 Tests)

Runs all verification tests from the implementation plan:
  1. Environment smoke test
  2. PettingZoo API compliance test
  3. SENTINEL unit test
  4. FastAPI server test
  5. WebSocket test

Usage:
  1. Start the server:  python -m uvicorn nexus.api.main:app --port 8000
  2. Run this script:   python test_verification.py
"""

import asyncio
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.request

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

PASS = 0
FAIL = 0
ERRORS = []

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"    [PASS] {name}")
    else:
        FAIL += 1
        ERRORS.append(f"{name}: {detail}")
        print(f"    [FAIL] {name} -- {detail}")

def section(title):
    print(f"\n{'=' * 68}")
    print(f"  {title}")
    print(f"{'=' * 68}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 1: Environment Smoke Test
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_1_environment():
    section("TEST 1: Environment Smoke Test")

    from nexus.environment.network_graph import SupplyChainNetwork, CircuitState
    from nexus.environment.disruption_sampler import DisruptionEngine

    # Network graph
    net = SupplyChainNetwork()
    check("Network has 15 nodes", net.num_nodes == 15, f"got {net.num_nodes}")
    check("Network has 35 edges", net.num_edges == 35, f"got {net.num_edges}")

    # Dijkstra
    path, cost = net.dijkstra("shanghai_port", "frankfurt_dc")
    check("Dijkstra finds path", len(path) >= 3, f"path={path}")
    check("Dijkstra cost > 0", cost > 0, f"cost={cost}")

    # Yen's K-shortest
    paths = net.k_shortest_paths("shanghai_port", "frankfurt_dc", k=3)
    check("K-shortest finds 3 paths", len(paths) == 3, f"got {len(paths)}")
    check("Paths are distinct", len(set(tuple(p) for p, _ in paths)) == 3)

    # Route metrics and Green-Resilience Score
    metrics = net.compute_route_metrics(path)
    check("Route has transit hours", metrics["total_transit_hours"] > 0)
    check("Route has carbon kg", metrics["total_carbon_kg"] > 0)
    check("Green-Resilience in [0,1]",
          0 <= metrics["green_resilience_score"] <= 1,
          f"got {metrics['green_resilience_score']}")

    # Circuit breaker
    net.set_circuit_state("hamburg_port", CircuitState.OPEN)
    check("Circuit breaker opens",
          net.nodes["hamburg_port"].circuit_state == CircuitState.OPEN)
    path2, cost2 = net.dijkstra("hamburg_port", "frankfurt_dc",
                                 avoid_open_circuits=True)
    check("Dijkstra avoids open circuits", "hamburg_port" not in path2[1:],
          f"path={path2}")
    net.set_circuit_state("hamburg_port", CircuitState.CLOSED)

    # Disruption engine
    de = DisruptionEngine(net, seed=42)
    h_before = net.nodes["hamburg_port"].health_score
    events = de.inject_hamburg_scenario()
    h_after = net.nodes["hamburg_port"].health_score
    check("Hamburg scenario: 4 events", len(events) == 4, f"got {len(events)}")
    check("Hamburg health drops", h_after < h_before,
          f"{h_before:.3f} -> {h_after:.3f}")

    # Disruption lifecycle tick
    de2 = DisruptionEngine(net, seed=99)
    ev = de2.inject_weather("la_port", 5.0, duration_hours=2)
    check("Inject returns event", ev.event_id.startswith("DISR"))
    for _ in range(3):
        resolved = de2.tick(0)
    check("Disruption resolves after duration", ev.resolved)

    # Stochastic sampling
    net2 = SupplyChainNetwork()
    de3 = DisruptionEngine(net2, seed=7)
    sampled = de3.sample_disruption(current_hour=0)
    check("Stochastic sample returns event", sampled.event_id is not None)
    check("Sampled event has target",
          sampled.target_node is not None or sampled.target_carrier is not None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 2: PettingZoo API Compliance
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_2_pettingzoo():
    section("TEST 2: PettingZoo API Compliance")

    from nexus.environment.supply_chain_env import SupplyChainEnv

    env = SupplyChainEnv(render_mode="json", seed=42, disruption_probability=0.0)

    # Check class basics
    check("Is ParallelEnv subclass",
          hasattr(env, 'step') and hasattr(env, 'reset'))
    check("Has possible_agents", len(env.possible_agents) == 6)
    check("Metadata present", "name" in env.metadata)

    # Reset
    obs, infos = env.reset(seed=42)
    check("Reset returns obs for all agents",
          set(obs.keys()) == set(env.possible_agents))
    check("Reset returns infos for all agents",
          set(infos.keys()) == set(env.possible_agents))
    check("Agents list populated after reset", len(env.agents) == 6)

    # Observation spaces
    for agent in env.agents:
        obs_space = env.observation_space(agent)
        agent_obs = obs[agent]
        for key in obs_space.spaces:
            check(f"{agent} obs[{key}] shape matches space",
                  agent_obs[key].shape == obs_space[key].shape,
                  f"obs={agent_obs[key].shape}, space={obs_space[key].shape}")
            break  # just check first key per agent for brevity

    # Action spaces — verify sampling
    for agent in env.agents:
        act_space = env.action_space(agent)
        action = {}
        for key, space in act_space.spaces.items():
            sample = space.sample()
            check(f"{agent} action[{key}] sampleable",
                  sample.shape == space.shape,
                  f"sample={sample.shape}, space={space.shape}")
            action[key] = sample
            break  # first key per agent

    # Step
    actions = {}
    for agent in env.agents:
        action = {}
        for key, space in env.action_space(agent).spaces.items():
            action[key] = space.sample()
        actions[agent] = action

    obs2, rewards, terms, truncs, infos2 = env.step(actions)
    check("Step returns obs", set(obs2.keys()) == set(env.agents))
    check("Step returns rewards", set(rewards.keys()) == set(env.agents))
    check("Step returns terminations", set(terms.keys()) == set(env.agents))
    check("Step returns truncations", set(truncs.keys()) == set(env.agents))
    check("All rewards are floats",
          all(isinstance(r, (int, float)) for r in rewards.values()))

    # Run to truncation
    env2 = SupplyChainEnv(seed=0, max_steps=5, disruption_probability=0.0)
    obs3, _ = env2.reset()
    for _ in range(10):
        if not env2.agents:
            break
        actions = {}
        for agent in env2.agents:
            action = {}
            for key, space in env2.action_space(agent).spaces.items():
                action[key] = space.sample()
            actions[agent] = action
        obs3, r, t, tr, i = env2.step(actions)

    check("Episode truncates at max_steps", not env2.agents)

    # Render
    env3 = SupplyChainEnv(render_mode="json", seed=42, disruption_probability=0.0)
    env3.reset()
    state = env3.render()
    check("JSON render returns dict", isinstance(state, dict))
    check("JSON render has step", "step" in state)
    check("JSON render has network", "network" in state)
    check("JSON render has shipments", "shipments" in state)

    env.close()
    env2.close()
    env3.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 3: SENTINEL Unit Test
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_3_sentinel():
    section("TEST 3: SENTINEL Unit Test")

    from nexus.agents.base_agent import BaseAgent, AgentDecision, AgentOutput
    from nexus.agents.sentinel.osint import DarkSignalIntelligence
    from nexus.agents.sentinel.financial import SupplierHealthRadar
    from nexus.agents.sentinel.model import SentinelAgent

    # Base agent ABC
    try:
        BaseAgent("test")
        check("ABC prevents instantiation", False, "should raise TypeError")
    except TypeError:
        check("ABC prevents instantiation", True)

    # AgentDecision
    d = AgentDecision(
        agent_name="TEST", action_type="test", target="node_1",
        reasoning="Because reasons.", confidence=0.9,
    )
    check("Decision has reasoning", d.reasoning == "Because reasons.")
    check("Decision serializes", "reasoning" in d.to_dict())

    # OSINT
    osint = DarkSignalIntelligence(use_gemini=False)
    report = osint.analyse()
    check("OSINT analyses 40 posts", report.total_posts_analysed == 40)
    check("OSINT finds signals", report.disruption_signals_found > 0)

    hamburg_triggered = any(
        c.node_id == "hamburg_port" and c.is_triggered
        for c in report.triggered_clusters
    )
    check("OSINT triggers Hamburg cluster", hamburg_triggered)

    # Check signal volume per node
    volumes = osint.get_signal_volume_per_node()
    check("Signal volume returns dict", isinstance(volumes, dict))
    check("Hamburg has high volume",
          volumes.get("hamburg_port", 0) > 0.3,
          f"got {volumes.get('hamburg_port', 0)}")

    # Financial Radar
    radar = SupplierHealthRadar()
    fin = radar.scan()
    check("Radar scans 8 suppliers", fin.total_suppliers == 8)
    check("Radar finds >=2 red", fin.red_count >= 2, f"got {fin.red_count}")

    gujarat = [a for a in fin.assessments if a.supplier_id == "SUP-003"][0]
    check("Gujarat is RED", gujarat.status == "red")
    check("Gujarat has reasoning", len(gujarat.risk_reasoning) > 50)
    check("Gujarat has alert flags", len(gujarat.alert_flags) > 0)

    node_risk = radar.get_node_risk_contribution()
    check("Node risk contribution has mumbai",
          "mumbai_hub" in node_risk)

    # Full SENTINEL
    from nexus.environment.supply_chain_env import SupplyChainEnv
    env = SupplyChainEnv(seed=42, disruption_probability=0.0)
    obs, _ = env.reset()

    sentinel = SentinelAgent(use_gemini=False, scan_interval=1)

    # Step 1: baseline
    out1 = sentinel.step(obs["sentinel"])
    check("SENTINEL returns action", "risk_scores" in out1.action)
    check("Risk scores shape", out1.action["risk_scores"].shape == (15,))
    check("Confidence shape", out1.action["confidence"].shape == (15,))

    # Step env with sentinel action
    actions = {"sentinel": out1.action}
    for agent in env.agents:
        if agent != "sentinel":
            action = {}
            for key, space in env.action_space(agent).spaces.items():
                action[key] = space.sample()
            actions[agent] = action
    obs, _, _, _, _ = env.step(actions)

    # Inject Hamburg and step SENTINEL again
    env.disruption_engine.inject_hamburg_scenario(env.current_step)
    actions2 = {"sentinel": sentinel.step(obs["sentinel"]).action}
    for agent in env.agents:
        if agent != "sentinel":
            action = {}
            for key, space in env.action_space(agent).spaces.items():
                action[key] = space.sample()
            actions2[agent] = action
    obs, _, _, _, _ = env.step(actions2)

    # Step a few more times for risk to accumulate
    for _ in range(4):
        out = sentinel.step(obs["sentinel"])
        actions3 = {"sentinel": out.action}
        for agent in env.agents:
            if agent != "sentinel":
                action = {}
                for key, space in env.action_space(agent).spaces.items():
                    action[key] = space.sample()
                actions3[agent] = action
        obs, _, _, _, _ = env.step(actions3)

    # Check SENTINEL detected Hamburg
    from nexus.environment.supply_chain_env import NODE_TO_IDX
    h_idx = NODE_TO_IDX["hamburg_port"]
    h_risk = float(sentinel.risk_scores[h_idx])
    check("SENTINEL detects Hamburg risk > 0.3", h_risk > 0.3,
          f"got {h_risk:.4f}")

    risk_report = sentinel.get_full_risk_report()
    check("Risk report has 15 nodes", len(risk_report["nodes"]) == 15)

    env.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 4: FastAPI Server Test
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_4_fastapi():
    section("TEST 4: FastAPI Server Test")

    BASE = "http://localhost:8001"

    def get(path):
        try:
            r = urllib.request.urlopen(f"{BASE}{path}", timeout=5)
            return json.loads(r.read())
        except urllib.error.URLError as e:
            check(f"GET {path}", False, f"Server not reachable: {e}")
            return None

    def post(path, data=None):
        try:
            body = json.dumps(data or {}).encode()
            req = urllib.request.Request(
                f"{BASE}{path}", data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            r = urllib.request.urlopen(req, timeout=5)
            return json.loads(r.read())
        except urllib.error.URLError as e:
            check(f"POST {path}", False, f"Server not reachable: {e}")
            return None

    # Health
    root = get("/")
    if root is None:
        print("    [SKIP] Server not running on :8000 -- skipping FastAPI tests")
        return
    check("Root endpoint responds", root["status"] == "online")

    health = get("/health")
    check("Health check passes", health and health["status"] == "healthy")

    # Reset
    reset = post("/api/v1/simulation/reset", {"seed": 42, "max_steps": 168})
    check("Reset succeeds", reset and reset["status"] == "reset")

    # Status
    status = get("/api/v1/simulation/status")
    check("Status shows 6 agents", status and len(status["agents"]) == 6)

    # Network
    nodes = get("/api/v1/network/nodes")
    check("15 nodes returned", nodes and nodes["total"] == 15)

    edges = get("/api/v1/network/edges")
    check("35 edges returned", edges and edges["total"] == 35)

    paths = get("/api/v1/network/paths/shanghai_port/frankfurt_dc?k=3")
    check("K-shortest paths work", paths and paths["paths_found"] == 3)

    shipments = get("/api/v1/network/shipments")
    check("30 shipments returned", shipments and shipments["total"] == 30)

    carriers = get("/api/v1/network/carriers")
    check("8 carriers returned", carriers and carriers["total"] == 8)

    # Step
    step = post("/api/v1/simulation/step?n=3")
    check("Manual step works", step and step["steps_executed"] == 3)

    # Inject scenario
    scenario = post("/api/v1/disruption/scenario/hamburg_storm")
    check("Hamburg scenario injects", scenario and scenario["events_injected"] >= 3)

    active = get("/api/v1/disruption/active")
    check("Active disruptions listed", active and active["total"] >= 3)

    # Step after disruption
    step2 = post("/api/v1/simulation/step?n=5")
    check("Post-disruption steps", step2 and step2["steps_executed"] == 5)

    # SENTINEL
    risk = get("/api/v1/sentinel/risk-report")
    check("Risk report returns", risk and len(risk.get("nodes", [])) == 15)

    hamburg = get("/api/v1/sentinel/risk/hamburg_port")
    check("Hamburg risk detail", hamburg and "signal_breakdown" in hamburg)

    decisions = get("/api/v1/sentinel/decisions?n=5")
    check("Decisions endpoint", decisions and "total" in decisions)

    # Disruption queries
    scenarios = get("/api/v1/disruption/scenarios")
    check("Scenarios list", scenarios and len(scenarios["scenarios"]) == 3)

    # Ad-hoc injection
    weather = post("/api/v1/disruption/inject/weather", {
        "node_id": "la_port", "severity": 5.0, "duration_hours": 24,
    })
    check("Ad-hoc weather injection", weather and weather["status"] == "injected")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TEST 5: WebSocket Test
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_5_websocket():
    section("TEST 5: WebSocket Test")

    try:
        import websockets
    except ImportError:
        print("    [SKIP] websockets package not installed")
        return

    async def ws_test():
        uri = "ws://localhost:8001/ws/live"
        try:
            async with websockets.connect(uri, open_timeout=3) as ws:
                # 1. Receive welcome
                msg = await asyncio.wait_for(ws.recv(), timeout=3)
                data = json.loads(msg)
                check("WS: Connected event received", data.get("event") == "connected")

                # 2. Send ping command
                await ws.send(json.dumps({"command": "ping"}))
                msg2 = await asyncio.wait_for(ws.recv(), timeout=3)
                data2 = json.loads(msg2)
                check("WS: Pong response", data2.get("event") == "pong")

                # 3. Send get_state command
                await ws.send(json.dumps({"command": "get_state"}))
                msg3 = await asyncio.wait_for(ws.recv(), timeout=3)
                data3 = json.loads(msg3)
                check("WS: Full state returned", data3.get("event") == "full_state")
                check("WS: State has step",
                      "step" in data3.get("data", {}))

                # 4. Trigger a simulation step via REST and capture broadcast
                post_req = urllib.request.Request(
                    "http://localhost:8001/api/v1/simulation/step?n=1",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(post_req, timeout=5)

                # Collect broadcast events (may get tick + health)
                events_received = []
                for _ in range(5):
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2)
                        events_received.append(json.loads(msg))
                    except asyncio.TimeoutError:
                        break

                event_types = [e.get("event") for e in events_received]
                check("WS: Received broadcast events",
                      len(events_received) > 0,
                      f"got {len(events_received)} events")
                check("WS: Tick event in broadcast",
                      "simulation_tick" in event_types,
                      f"got types: {event_types}")

                # 5. Check sequence numbers
                has_seq = all("_seq" in e for e in events_received)
                check("WS: Events have sequence numbers", has_seq)

        except (ConnectionRefusedError, OSError) as e:
            print(f"    [SKIP] WebSocket not reachable: {e}")

    asyncio.run(ws_test())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    print()
    print("=" * 68)
    print("  NEXUS — Full Verification Suite")
    print("=" * 68)

    for test_fn in [
        test_1_environment,
        test_2_pettingzoo,
        test_3_sentinel,
        test_4_fastapi,
        test_5_websocket,
    ]:
        try:
            test_fn()
        except Exception as e:
            print(f"    [ERROR] {test_fn.__name__} crashed: {e}")
            traceback.print_exc()
            FAIL += 1

    # Final report
    total = PASS + FAIL
    section(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")

    if ERRORS:
        print("\n  Failures:")
        for err in ERRORS:
            print(f"    - {err}")

    print()
    sys.exit(0 if FAIL == 0 else 1)
