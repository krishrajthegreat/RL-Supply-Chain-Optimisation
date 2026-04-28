"""Smoke test for NEXUS SENTINEL agent (Component 3)."""
import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Test 1: Base Agent Interface ──
print("=" * 64)
print("TEST 1: Base Agent Interface")
print("=" * 64)

from nexus.agents.base_agent import BaseAgent, AgentOutput, AgentDecision
import numpy as np

# Verify ABC can't be instantiated directly
try:
    agent = BaseAgent("test")
    print("  FAIL: Should not be able to instantiate ABC")
except TypeError:
    print("  ABC correctly prevents direct instantiation")

# Verify decision structure
d = AgentDecision(
    agent_name="TEST",
    action_type="test_action",
    target="node_1",
    details={"key": "value"},
    reasoning="This is a test reasoning field.",
    confidence=0.85,
    priority=0.7,
    timestamp_step=1,
)
d_dict = d.to_dict()
assert d_dict["agent"] == "TEST"
assert d_dict["reasoning"] == "This is a test reasoning field."
assert d_dict["confidence"] == 0.85
print(f"  AgentDecision serializes correctly: {list(d_dict.keys())}")
print("  [PASS] Base Agent Interface\n")


# ── Test 2: OSINT Dark Signal Intelligence ──
print("=" * 64)
print("TEST 2: OSINT Dark Signal Intelligence")
print("=" * 64)

from nexus.agents.sentinel.osint import DarkSignalIntelligence

osint = DarkSignalIntelligence(use_gemini=False)
report = osint.analyse()
print(f"  Posts analysed: {report.total_posts_analysed}")
print(f"  Disruption signals: {report.disruption_signals_found}")
print(f"  Clusters found: {len(report.clusters)}")
print(f"  Triggered clusters: {len(report.triggered_clusters)}")

for c in report.triggered_clusters:
    print(f"    -> {c.node_id}: {c.signal_count} signals, "
          f"sigma={c.sigma_score:.1f}, type={c.dominant_type}")

assert report.total_posts_analysed == 40
assert report.disruption_signals_found > 0
assert len(report.triggered_clusters) > 0, "Hamburg should trigger"

# Check Hamburg is detected
hamburg_clusters = [c for c in report.triggered_clusters
                    if c.node_id == "hamburg_port"]
assert len(hamburg_clusters) > 0, "Hamburg port must be triggered"
print(f"  Hamburg cluster: {hamburg_clusters[0].signal_count} signals, "
      f"sigma={hamburg_clusters[0].sigma_score:.1f}")

print(f"  Summary: {report.scan_summary}")
print("  [PASS] OSINT Dark Signal Intelligence\n")


# ── Test 3: Supplier Financial Health Radar ──
print("=" * 64)
print("TEST 3: Supplier Financial Health Radar")
print("=" * 64)

from nexus.agents.sentinel.financial import SupplierHealthRadar

radar = SupplierHealthRadar()
fin_report = radar.scan()
print(f"  Total suppliers: {fin_report.total_suppliers}")
print(f"  Green: {fin_report.green_count}, Amber: {fin_report.amber_count}, "
      f"Red: {fin_report.red_count}")

for a in fin_report.assessments:
    print(f"    {a.supplier_id} ({a.name:35s}): "
          f"score={a.composite_score:.3f} ({a.status:5s}) "
          f"trend={a.trend_direction}")

assert fin_report.total_suppliers == 8
assert fin_report.red_count >= 2, "Gujarat and Lagos should be red"
assert len(fin_report.critical_alerts) > 0

# Check Gujarat Chemical is red
gujarat = [a for a in fin_report.assessments if a.supplier_id == "SUP-003"]
assert gujarat[0].status == "red", "Gujarat Chemical must be red"
print(f"\n  Gujarat Chemical reasoning:")
print(f"    {gujarat[0].risk_reasoning[:200]}...")
print(f"    Flags: {gujarat[0].alert_flags}")

# Check node risk contribution
node_risks = radar.get_node_risk_contribution()
print(f"\n  Node risk contribution from suppliers:")
for nid, risk in sorted(node_risks.items(), key=lambda x: x[1], reverse=True):
    if risk > 0.1:
        print(f"    {nid}: {risk:.3f}")

print(f"  Summary: {fin_report.summary}")
print("  [PASS] Supplier Financial Health Radar\n")


# ── Test 4: Full SENTINEL Agent Integration ──
print("=" * 64)
print("TEST 4: Full SENTINEL Agent Integration")
print("=" * 64)

from nexus.agents.sentinel.model import SentinelAgent
from nexus.environment.supply_chain_env import SupplyChainEnv

# Create environment
env = SupplyChainEnv(seed=42, disruption_probability=0.0)
obs, infos = env.reset()

# Create SENTINEL agent
sentinel = SentinelAgent(use_gemini=False, scan_interval=1)

# Run SENTINEL for several steps
print("  Running SENTINEL for 6 steps...")
for step in range(6):
    # Get SENTINEL's observation
    sentinel_obs = obs["sentinel"]

    # Inject Hamburg disruption at step 2
    if step == 2:
        env.disruption_engine.inject_hamburg_scenario(env.current_step)
        print("    [Step 3] Hamburg disruption injected")

    # SENTINEL observe + act
    output = sentinel.step(sentinel_obs)

    # Build actions for all agents (SENTINEL real, others random)
    actions = {}
    actions["sentinel"] = output.action
    for agent in env.agents:
        if agent != "sentinel":
            action = {}
            for key, space in env.action_space(agent).spaces.items():
                action[key] = space.sample()
            actions[agent] = action

    # Step the environment
    obs, rewards, terms, truncs, infos = env.step(actions)

    # Print SENTINEL status
    n_decisions = len(output.decisions)
    print(f"    Step {step+1}: {n_decisions} decisions, "
          f"reward={rewards.get('sentinel', 0):.3f}")
    if output.decisions:
        for d in output.decisions[:3]:
            print(f"      [{d.action_type}] {d.target}: "
                  f"risk={d.details.get('risk_score', '?')}, "
                  f"conf={d.confidence:.2f}")
            print(f"        Reasoning: {d.reasoning[:150]}...")

# Final risk report
risk_report = sentinel.get_full_risk_report()
print(f"\n  Final Risk Report (step {risk_report['step']}):")
print(f"    Red nodes: {risk_report['red_count']}")
print(f"    Amber nodes: {risk_report['amber_count']}")
print(f"    OSINT: {risk_report['osint_summary']}")
print(f"    Suppliers: {risk_report['supplier_summary']}")

# Show top risk nodes
print(f"    Top risk nodes:")
for n in risk_report["nodes"][:5]:
    print(f"      {n['node_id']:20s} risk={n['risk_score']:.4f} "
          f"({n['status']}) trend={n['trend']}")

# Verify Hamburg was detected
hamburg_risk = sentinel.get_risk_for_node("hamburg_port")
print(f"\n  Hamburg port detailed:")
print(f"    Risk: {hamburg_risk['risk_score']:.4f}")
print(f"    Confidence: {hamburg_risk['confidence']:.4f}")
print(f"    Signal breakdown: {hamburg_risk['signal_breakdown']}")

env.close()
print("  [PASS] Full SENTINEL Agent Integration\n")


print("=" * 64)
print("ALL COMPONENT 3 TESTS PASSED")
print("=" * 64)
