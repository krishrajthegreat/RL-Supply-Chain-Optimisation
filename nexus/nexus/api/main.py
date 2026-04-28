"""
NEXUS FastAPI Backend — main application module.

Provides the REST + WebSocket API server for the NEXUS multi-agent
supply chain resilience system.  Manages the simulation lifecycle
(reset / step / auto-run) and coordinates SENTINEL and other agents.

Endpoints
---------
  REST : /api/v1/network/*     — network, nodes, shipments, paths
         /api/v1/disruption/*  — inject / query disruptions
         /api/v1/sentinel/*    — risk analysis, OSINT, financial
         /api/v1/simulation/*  — simulation control

  WS   : /ws/live              — real-time event stream

Quick Start
-----------
  $ cd nexus/
  $ python -m uvicorn nexus.api.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nexus.agents.sentinel.model import SentinelAgent
from nexus.api.routes import disruption, network, sentinel, websocket
from nexus.api.routes.websocket import get_manager
from nexus.environment.supply_chain_env import (
    NODE_IDS,
    NODE_TO_IDX,
    NUM_CARRIERS,
    NUM_NODES,
    SupplyChainEnv,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Global Simulation State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class SimulationState:
    """Holds all global simulation objects."""
    env: Optional[SupplyChainEnv] = None
    sentinel: Optional[SentinelAgent] = None
    running: bool = False
    speed: float = 1.0                # seconds per simulation step
    _task: Optional[asyncio.Task] = field(default=None, repr=False)
    _obs: Optional[dict] = field(default=None, repr=False)


# Singleton
sim = SimulationState()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Heuristic Agent Policies (for non-SENTINEL agents)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _guardian_heuristic(obs: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """
    GUARDIAN heuristic: open circuit if node_health < 0.30 and
    throughput_ratio < 0.30, probe half-open if health > 0.55.
    """
    actions = np.zeros(NUM_NODES, dtype=np.float32)
    node_health = obs["node_health"]
    throughput = obs["throughput_ratio"]
    circuit_states = obs["circuit_states"]

    for i in range(NUM_NODES):
        if circuit_states[i] == 0.0:  # CLOSED
            if node_health[i] < 0.30 and throughput[i] < 0.30:
                actions[i] = 0.50  # → OPEN
        elif circuit_states[i] == 1.0:  # OPEN
            if node_health[i] > 0.55:
                actions[i] = 0.80  # → HALF_OPEN probe
        elif circuit_states[i] == 2.0:  # HALF_OPEN
            if node_health[i] > 0.70:
                actions[i] = 0.50  # → CLOSED (via guardian logic)

    return {"circuit_actions": actions}


def _navigator_heuristic(
    obs: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """
    NAVIGATOR heuristic: reroute shipments that are at risk
    and have high urgency.
    """
    at_risk = obs["shipment_at_risk"]
    urgency = obs["shipment_urgency"]

    reroute = np.zeros_like(at_risk)
    for i in range(len(at_risk)):
        if at_risk[i] > 0.5 and urgency[i] > 0.3:
            reroute[i] = 0.8

    return {
        "reroute_flags": reroute,
        "urgency_level": urgency,
    }


def _stockpile_heuristic(
    obs: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """
    STOCKPILE heuristic: pre-position inventory at nodes with
    high risk and low current inventory.
    """
    risk = obs["risk_scores"]
    inventory = obs["inventory_levels"]

    triggers = np.zeros(NUM_NODES, dtype=np.float32)
    for i in range(NUM_NODES):
        if risk[i] > 0.4 and inventory[i] < 0.5:
            triggers[i] = 0.8
        elif risk[i] > 0.6:
            triggers[i] = 0.9

    return {"transfer_triggers": triggers}


def _broker_heuristic(
    obs: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """
    BROKER heuristic: flag carriers with low health for blackout.
    """
    health = obs["carrier_health"]
    flags = np.where(health < 0.45, 0.2, 0.7).astype(np.float32)
    return {"carrier_flags": flags}


def _herald_heuristic(
    obs: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    """
    HERALD heuristic: alert on shipments with high SLA breach
    probability or active risk flags.
    """
    breach_prob = obs["sla_breach_probability"]
    alerts = obs["active_alerts"]

    priorities = np.maximum(breach_prob, alerts).astype(np.float32)
    return {"alert_priorities": priorities}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Simulation Step Logic
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def _run_one_step() -> dict:
    """
    Execute a single simulation step:
      1. SENTINEL observes + produces risk scores
      2. Other agents use heuristic policies
      3. Environment steps
      4. Broadcast events via WebSocket
    """
    if sim.env is None or sim._obs is None:
        raise RuntimeError("Simulation not initialised")

    obs = sim._obs
    mgr = get_manager()

    # ── SENTINEL acts ─────────────────────────────────────────
    sentinel_output = sim.sentinel.step(obs["sentinel"])
    actions = {"sentinel": sentinel_output.action}

    # ── Other agents use heuristics ───────────────────────────
    actions["guardian"] = _guardian_heuristic(obs["guardian"])
    actions["navigator"] = _navigator_heuristic(obs["navigator"])
    actions["stockpile"] = _stockpile_heuristic(obs["stockpile"])
    actions["broker"] = _broker_heuristic(obs["broker"])
    actions["herald"] = _herald_heuristic(obs["herald"])

    # ── Step the environment ──────────────────────────────────
    new_obs, rewards, terms, truncs, infos = sim.env.step(actions)
    sim._obs = new_obs

    step = sim.env.current_step
    metrics = sim.env._episode_metrics

    # ── Broadcast SENTINEL decisions via WebSocket ────────────
    for decision in sentinel_output.decisions:
        await mgr.broadcast_agent_decision(decision.to_dict())

    # ── Broadcast tick summary ────────────────────────────────
    node_health_summary = {}
    for nid in NODE_IDS:
        node = sim.env.network.nodes[nid]
        node_health_summary[nid] = {
            "health": round(node.health_score, 4),
            "circuit": node.circuit_state.value,
            "risk": round(float(sim.env.risk_scores[NODE_TO_IDX[nid]]), 4),
        }

    await mgr.broadcast_tick({
        "step": step,
        "max_steps": sim.env.max_steps,
        "rewards": {k: round(float(v), 4) for k, v in rewards.items()},
        "metrics": {
            "delivered": metrics["shipments_delivered"],
            "sla_breaches": metrics["sla_breaches"],
            "total_delay": metrics["total_delay_hours"],
            "reroutes": metrics["reroutes"],
            "circuit_opens": metrics["circuit_opens"],
            "active_disruptions": len(
                sim.env.disruption_engine.active_disruptions
            ),
        },
        "sentinel_summary": sentinel_output.summary,
    })

    await mgr.broadcast_network_health(node_health_summary)

    # ── Check for episode end ─────────────────────────────────
    episode_done = all(truncs.get(a, False) for a in sim.env.possible_agents)

    return {
        "step": step,
        "episode_done": episode_done,
        "rewards": {k: round(float(v), 4) for k, v in rewards.items()},
        "sentinel_decisions": len(sentinel_output.decisions),
        "sentinel_summary": sentinel_output.summary,
    }


async def _auto_simulation_loop():
    """Background loop that continuously steps the simulation."""
    logger.info("Auto-simulation started (speed=%.2fs/step)", sim.speed)
    try:
        while sim.running and sim.env and sim.env.agents:
            t0 = time.time()
            result = await _run_one_step()
            elapsed = time.time() - t0

            if result["episode_done"]:
                logger.info("Episode complete at step %d", result["step"])
                sim.running = False
                break

            # Maintain target speed
            sleep_time = max(0, sim.speed - elapsed)
            await asyncio.sleep(sleep_time)

    except asyncio.CancelledError:
        logger.info("Auto-simulation cancelled")
    except Exception as exc:
        logger.exception("Auto-simulation error: %s", exc)
        sim.running = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Public helper for websocket module
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def get_simulation_state() -> dict:
    """Get current simulation state (called by websocket handler)."""
    if sim.env is None:
        return {"status": "not_initialised"}
    return sim.env.get_state()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FastAPI Lifespan
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: initialise the environment and SENTINEL agent.
    Shutdown: stop any running simulation.
    """
    logger.info("NEXUS API starting up...")

    # Auto-initialise environment
    sim.env = SupplyChainEnv(
        render_mode=None,
        seed=42,
        disruption_probability=0.02,
    )
    obs, _ = sim.env.reset()
    sim._obs = obs
    sim.sentinel = SentinelAgent(use_gemini=False, scan_interval=6)

    logger.info(
        "Environment initialised: %d nodes, %d edges, %d shipments",
        sim.env.network.num_nodes,
        sim.env.network.num_edges,
        len(sim.env.shipments),
    )

    yield

    # Shutdown
    logger.info("NEXUS API shutting down...")
    sim.running = False
    if sim._task and not sim._task.done():
        sim._task.cancel()
        try:
            await sim._task
        except asyncio.CancelledError:
            pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FastAPI App
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app = FastAPI(
    title="NEXUS Supply Chain Intelligence API",
    description=(
        "Multi-agent supply chain resilience system. "
        "Provides real-time risk analysis, disruption management, "
        "and dynamic routing through a 15-node global logistics network."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount Routers ──
app.include_router(network.router, prefix="/api/v1")
app.include_router(disruption.router, prefix="/api/v1")
app.include_router(sentinel.router, prefix="/api/v1")
app.include_router(websocket.router, prefix="/ws")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Simulation Control Endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class SimulationConfig(BaseModel):
    """Configuration for simulation reset."""
    seed: int = Field(42, description="Random seed")
    max_steps: int = Field(168, ge=1, le=720, description="Episode length in hours")
    disruption_probability: float = Field(
        0.02, ge=0.0, le=0.5,
        description="Per-step probability of random disruption",
    )
    speed: float = Field(
        1.0, ge=0.1, le=10.0,
        description="Seconds per step in auto-simulation mode",
    )


@app.get("/api/v1/simulation/status", tags=["Simulation"])
async def simulation_status():
    """
    Returns current simulation status including step count,
    whether auto-simulation is running, connected WebSocket clients,
    and key metrics.
    """
    if sim.env is None:
        return {
            "status": "not_initialised",
            "running": False,
        }

    return {
        "status": "running" if sim.running else "paused",
        "step": sim.env.current_step,
        "max_steps": sim.env.max_steps,
        "agents": sim.env.agents,
        "speed": sim.speed,
        "ws_clients": get_manager().client_count,
        "metrics": sim.env._episode_metrics,
    }


@app.post("/api/v1/simulation/reset", tags=["Simulation"])
async def simulation_reset(config: Optional[SimulationConfig] = None):
    """
    Reset the simulation to initial state with optional configuration.

    Stops any running auto-simulation first.
    """
    # Stop running simulation
    sim.running = False
    if sim._task and not sim._task.done():
        sim._task.cancel()
        try:
            await sim._task
        except asyncio.CancelledError:
            pass

    # Apply config
    seed = 42
    max_steps = 168
    disruption_prob = 0.02
    if config:
        seed = config.seed
        max_steps = config.max_steps
        disruption_prob = config.disruption_probability
        sim.speed = config.speed

    # Reset environment
    sim.env = SupplyChainEnv(
        render_mode=None,
        seed=seed,
        max_steps=max_steps,
        disruption_probability=disruption_prob,
    )
    obs, _ = sim.env.reset()
    sim._obs = obs

    # Reset SENTINEL
    sim.sentinel = SentinelAgent(use_gemini=False, scan_interval=6)

    logger.info("Simulation reset (seed=%d, max_steps=%d)", seed, max_steps)

    # Broadcast reset event
    await get_manager().broadcast({
        "event": "simulation_reset",
        "data": {
            "seed": seed,
            "max_steps": max_steps,
            "disruption_probability": disruption_prob,
        },
    })

    return {
        "status": "reset",
        "step": 0,
        "max_steps": max_steps,
        "seed": seed,
    }


@app.post("/api/v1/simulation/step", tags=["Simulation"])
async def simulation_step(n: int = 1):
    """
    Manually advance the simulation by N steps.

    Returns step results including SENTINEL decisions and rewards.
    This is used for step-by-step demo mode where the presenter
    controls the pace.
    """
    if sim.env is None:
        raise HTTPException(503, "Simulation not initialised. POST /reset first.")
    if sim.running:
        raise HTTPException(409, "Auto-simulation is running. POST /stop first.")
    if not sim.env.agents:
        raise HTTPException(
            400, "Episode is complete. POST /reset to start a new one."
        )

    n = min(n, 50)  # cap at 50 steps per call
    results = []
    for _ in range(n):
        if not sim.env.agents:
            break
        result = await _run_one_step()
        results.append(result)
        if result["episode_done"]:
            break
        await asyncio.sleep(0.05)  # small delay for WebSocket delivery

    return {
        "steps_executed": len(results),
        "results": results,
    }


@app.post("/api/v1/simulation/start", tags=["Simulation"])
async def simulation_start(
    speed: float = 1.0,
):
    """
    Start auto-simulation mode. The simulation will advance
    one step every {speed} seconds, broadcasting events via WebSocket.
    """
    if sim.env is None:
        raise HTTPException(503, "Simulation not initialised.")
    if sim.running:
        return {"status": "already_running", "step": sim.env.current_step}
    if not sim.env.agents:
        raise HTTPException(400, "Episode complete. POST /reset first.")

    sim.speed = max(0.1, min(speed, 10.0))
    sim.running = True
    sim._task = asyncio.create_task(_auto_simulation_loop())

    await get_manager().broadcast({
        "event": "simulation_started",
        "data": {"speed": sim.speed},
    })

    return {
        "status": "started",
        "speed": sim.speed,
        "step": sim.env.current_step,
    }


@app.post("/api/v1/simulation/stop", tags=["Simulation"])
async def simulation_stop():
    """Stop auto-simulation mode (keeps state intact for manual steps)."""
    sim.running = False
    if sim._task and not sim._task.done():
        sim._task.cancel()
        try:
            await sim._task
        except asyncio.CancelledError:
            pass

    step = sim.env.current_step if sim.env else 0

    await get_manager().broadcast({
        "event": "simulation_stopped",
        "data": {"step": step},
    })

    return {
        "status": "stopped",
        "step": step,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Root & Health
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.get("/", tags=["Health"])
async def root():
    """NEXUS API root — health check and API documentation links."""
    return {
        "name": "NEXUS Supply Chain Intelligence API",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
        "redoc": "/redoc",
        "websocket": "/ws/live",
        "api_prefix": "/api/v1",
        "endpoints": {
            "simulation": "/api/v1/simulation/status",
            "network": "/api/v1/network/state",
            "disruptions": "/api/v1/disruption/active",
            "sentinel": "/api/v1/sentinel/risk-report",
        },
    }


@app.get("/health", tags=["Health"])
async def health():
    """Readiness probe for container orchestrators."""
    return {
        "status": "healthy",
        "simulation_initialised": sim.env is not None,
        "step": sim.env.current_step if sim.env else 0,
        "ws_clients": get_manager().client_count,
    }
