# NEXUS — Multi-Agent Supply Chain Resilience System

> **Google Solutions Challenge 2026** | Team NEXUS
>
> A multi-agent reinforcement learning system that detects supply chain
> disruptions **9.5 hours before official alerts** using OSINT dark signal
> intelligence and optimises rerouting with a Green-Resilience Score
> (carbon + reliability).

---

## Architecture

```
nexus/
  nexus/
    __init__.py
    data/                     # Seed data (JSON)
      __init__.py             # load_json() utility
      nodes.json              # 15-node global logistics network
      shipments.json          # 30 active shipments
      carriers.json           # 8 carrier profiles
      suppliers.json          # 8 supplier health profiles
      mock_social_posts.json  # 40 OSINT posts (Hamburg scenario)
    environment/              # PettingZoo simulation
      __init__.py
      network_graph.py        # Dijkstra, Yen's K-shortest, circuit breaker
      disruption_sampler.py   # 6 disruption types, 3 demo scenarios
      supply_chain_env.py     # PettingZoo ParallelEnv (6 agents)
    agents/                   # MARL agents
      __init__.py
      base_agent.py           # ABC with explainability enforcement
      sentinel/
        __init__.py
        model.py              # 5-signal risk fusion engine
        osint.py              # Dark Signal Intelligence (NLP pipeline)
        financial.py          # Supplier Health Radar (4-category)
    api/                      # FastAPI backend
      __init__.py
      main.py                 # App + simulation control
      routes/
        __init__.py
        network.py            # Network, shipment, path endpoints
        disruption.py         # Disruption injection endpoints
        sentinel.py           # Risk analysis endpoints
        websocket.py          # Real-time WebSocket stream
  requirements.txt
  .env.example
  README.md
```

## Quick Start

### 1. Install Dependencies

```bash
cd nexus/
python -m pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env — GEMINI_API_KEY is optional (mock mode works without it)
```

### 3. Start the API Server

```bash
python -m uvicorn nexus.api.main:app --reload --port 8000
```

The server auto-initialises the 15-node supply chain simulation on startup.

### 4. Open the Dashboard

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **WebSocket**: `ws://localhost:8000/ws/live`

---

## API Reference

### Simulation Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/simulation/status` | Current simulation state |
| `POST` | `/api/v1/simulation/reset` | Reset with optional config |
| `POST` | `/api/v1/simulation/step?n=N` | Advance N steps manually |
| `POST` | `/api/v1/simulation/start?speed=S` | Start auto-simulation |
| `POST` | `/api/v1/simulation/stop` | Stop auto-simulation |

### Network & Logistics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/network/state` | Full simulation state dump |
| `GET` | `/api/v1/network/nodes` | All 15 nodes with health |
| `GET` | `/api/v1/network/nodes/{id}` | Node detail + dependencies |
| `GET` | `/api/v1/network/edges` | All 35 directed edges |
| `GET` | `/api/v1/network/paths/{o}/{d}` | K-shortest path finding |
| `GET` | `/api/v1/network/shipments` | All 30 shipments |
| `GET` | `/api/v1/network/carriers` | 8 carrier profiles |
| `GET` | `/api/v1/network/suppliers` | 8 supplier profiles |

### Disruption Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/disruption/scenario/{name}` | Inject demo scenario |
| `GET` | `/api/v1/disruption/scenarios` | List available scenarios |
| `POST` | `/api/v1/disruption/inject/weather` | Ad-hoc weather event |
| `POST` | `/api/v1/disruption/inject/congestion` | Ad-hoc congestion |
| `POST` | `/api/v1/disruption/inject/carrier` | Carrier degradation |
| `POST` | `/api/v1/disruption/inject/geopolitical` | Geopolitical risk |
| `POST` | `/api/v1/disruption/inject/supplier` | Supplier distress |
| `POST` | `/api/v1/disruption/inject/labor` | Labor disruption |
| `GET` | `/api/v1/disruption/active` | Active disruptions |
| `GET` | `/api/v1/disruption/history` | Resolved disruptions |

### SENTINEL Intelligence

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/sentinel/risk-report` | Full risk heatmap |
| `GET` | `/api/v1/sentinel/risk/{node_id}` | Node signal breakdown |
| `GET` | `/api/v1/sentinel/osint` | Latest OSINT report |
| `POST` | `/api/v1/sentinel/osint/scan` | Trigger fresh OSINT scan |
| `GET` | `/api/v1/sentinel/financial` | Latest supplier radar |
| `POST` | `/api/v1/sentinel/financial/scan` | Trigger fresh financial scan |
| `GET` | `/api/v1/sentinel/decisions` | Decision history |
| `GET` | `/api/v1/sentinel/supplier-risk-map` | Node risk from suppliers |

### WebSocket

```
WS /ws/live
```

Events: `sentinel_decision`, `disruption_event`, `simulation_tick`, `network_health`

---

## Demo Scenarios

### Hamburg Storm Surge (Primary)

```bash
curl -X POST http://localhost:8000/api/v1/disruption/scenario/hamburg_storm
```

Injects: weather (sev 8.5) + congestion (3.5x) at Hamburg, Gujarat supplier
distress, ONE carrier degradation. Demonstrates the full NEXUS response chain.

### Red Sea Crisis

```bash
curl -X POST http://localhost:8000/api/v1/disruption/scenario/red_sea_crisis
```

Geopolitical risk spikes on Asia-Europe lanes through the Suez corridor.

### Shanghai Lockdown

```bash
curl -X POST http://localhost:8000/api/v1/disruption/scenario/shanghai_lockdown
```

COVID-era throughput reduction with cascading supplier stress.

---

## Running Tests

```bash
cd nexus/

# Environment smoke test (network graph, disruption engine, PettingZoo env)
python test_environment.py

# SENTINEL agent test (base agent, OSINT, financial radar, integration)
python test_sentinel.py

# FastAPI backend test (requires server running on port 8000)
python -m uvicorn nexus.api.main:app --port 8000 &
python test_api.py

# Full verification suite (all 5 tests)
python test_verification.py
```

---

## Agents

| Agent | Role | Key Capability |
|-------|------|---------------|
| **SENTINEL** | Risk assessment | 5-signal fusion, 9.5h early warning |
| **NAVIGATOR** | Dynamic routing | Yen's K-shortest, Green-Resilience Score |
| **GUARDIAN** | Circuit breaker | 3-state machine (Closed/Open/Half-Open) |
| **STOCKPILE** | Inventory pre-positioning | Risk-weighted buffer allocation |
| **BROKER** | Carrier management | OTP monitoring, soft blackout |
| **HERALD** | Communication | SLA breach alerting, alarm fatigue control |

---

## Key Metrics

- **9.5-hour lead time**: OSINT detects Hamburg storm surge before official alerts
- **Green-Resilience Score**: Composite of carbon (GLEC), reliability, cost, time
- **5-signal fusion**: Weather + OSINT + supplier + congestion + geopolitical
- **2.5-sigma trigger**: Statistical anomaly detection on OSINT signal clusters

---

## Tech Stack

- **Simulation**: PettingZoo + Gymnasium (multi-agent parallel environment)
- **Backend**: FastAPI + Uvicorn (REST + WebSocket)
- **AI**: Google Gemini 1.5 Flash (OSINT classification, optional)
- **Data**: NumPy (signal processing, route optimisation)

---

## License

Built for Google Solutions Challenge 2026.
