"""Smoke test for NEXUS environment components."""
import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from nexus.environment.network_graph import SupplyChainNetwork
from nexus.environment.disruption_sampler import DisruptionEngine
from nexus.environment.supply_chain_env import SupplyChainEnv

# -- Test 1: Network Graph --
print("=" * 60)
print("TEST 1: Network Graph")
print("=" * 60)
net = SupplyChainNetwork()
print(f"  Nodes: {net.num_nodes}")
print(f"  Edges: {net.num_edges}")
path, cost = net.dijkstra("shanghai_port", "frankfurt_dc")
print(f"  Shanghai->Frankfurt: {' -> '.join(path)} ({cost}h)")
paths = net.k_shortest_paths("shanghai_port", "frankfurt_dc", k=3)
print(f"  K=3 paths found: {len(paths)}")
for i, (p, c) in enumerate(paths):
    print(f"    Route {i+1}: {' -> '.join(p)} ({c}h)")
print("  [PASS] Network Graph\n")

# -- Test 2: Disruption Engine --
print("=" * 60)
print("TEST 2: Disruption Engine")
print("=" * 60)
de = DisruptionEngine(net, seed=42)
h_before = net.nodes["hamburg_port"].health_score
print(f"  Hamburg health before: {h_before:.4f}")
events = de.inject_hamburg_scenario()
h_after = net.nodes["hamburg_port"].health_score
print(f"  Hamburg health after:  {h_after:.4f}")
print(f"  Active disruptions: {len(de.active_disruptions)}")
for e in events:
    target = e.target_node or e.target_carrier
    print(f"    [{e.event_id}] {e.disruption_type.value:12s} -> {target}")
assert h_after < h_before, "Health should drop after disruption"
print("  [PASS] Disruption Engine\n")

# -- Test 3: PettingZoo Environment --
print("=" * 60)
print("TEST 3: PettingZoo ParallelEnv")
print("=" * 60)
env = SupplyChainEnv(render_mode=None, seed=42, disruption_probability=0.0)
obs, infos = env.reset()
print(f"  Agents: {env.agents}")
print(f"  Obs keys per agent:")
for agent in env.agents:
    keys = list(obs[agent].keys())
    shapes = {k: obs[agent][k].shape for k in keys}
    print(f"    {agent:12s}: {shapes}")

# Take a few steps with random actions
import numpy as np
for step in range(3):
    actions = {}
    for agent in env.agents:
        action = {}
        for key, space in env.action_space(agent).spaces.items():
            action[key] = space.sample()
        actions[agent] = action
    obs, rewards, terms, truncs, infos = env.step(actions)
    r_str = ", ".join(f"{a}={r:.3f}" for a, r in rewards.items())
    print(f"  Step {step+1}: rewards = {r_str}")

# Inject disruption and check SENTINEL sees it
env.disruption_engine.inject_hamburg_scenario(env.current_step)
actions = {}
for agent in env.agents:
    action = {}
    for key, space in env.action_space(agent).spaces.items():
        action[key] = space.sample()
    actions[agent] = action
obs, rewards, terms, truncs, infos = env.step(actions)
hamburg_idx = 2  # NODE_IDS index
print(f"  After Hamburg disruption:")
print(f"    SENTINEL disruption_active[hamburg] = {obs['sentinel']['disruption_active'][hamburg_idx]:.2f}")
print(f"    GUARDIAN node_health[hamburg]        = {obs['guardian']['node_health'][hamburg_idx]:.4f}")
print(f"    GUARDIAN throughput_ratio[hamburg]    = {obs['guardian']['throughput_ratio'][hamburg_idx]:.4f}")

env.close()
print("  [PASS] PettingZoo Environment\n")

print("=" * 60)
print("ALL TESTS PASSED")
print("=" * 60)
