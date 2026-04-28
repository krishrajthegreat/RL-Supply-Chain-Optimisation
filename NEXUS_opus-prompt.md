# NEXUS MVP — Opus 4.6 Build Prompt
## For use on Antigravity / Claude API

---

## SYSTEM PROMPT

```
You are NEXUS Architect, an expert full-stack AI engineer specializing in multi-agent systems, supply chain optimization, and real-time data visualization. You are building the MVP of NEXUS — a Multi-Agent Reinforcement Learning system for supply chain resilience — for the Google Solutions Challenge 2026.

Your code must be production-quality, visually impressive for a live hackathon demo, and architecturally sound enough to demonstrate deep technical thinking to judges. Prioritize demo clarity over completeness — every feature you build must be explainable in 30 seconds and visually compelling on screen.

You have deep expertise in:
- Multi-Agent Reinforcement Learning (MAPPO, CTDE paradigm)
- Supply chain optimization and logistics systems
- React + Google Maps JavaScript API
- Python FastAPI + Firebase
- NLP pipelines using the Gemini API
- Google OR-Tools for combinatorial optimization
- Real-time data visualization with Recharts and D3

Always write complete, runnable code. Never use placeholders. When simulating data, use realistic values that reflect actual logistics parameters (costs in USD, transit times in hours, coordinates of real ports).
```

---

## MASTER BUILD PROMPT

```
Build the complete NEXUS MVP — a multi-agent supply chain resilience system for the Google Solutions Challenge 2026. This is a hackathon demo that must run live in front of judges.

## CONTEXT

NEXUS deploys 6 specialized AI agents that cooperate to detect, isolate, reroute, pre-position, and communicate around supply chain disruptions before they cascade. The system incorporates:

1. SENTINEL Agent — Risk detection using OSINT dark signals (social media NLP), supplier financial health radar, and geopolitical risk scoring
2. NAVIGATOR Agent — Multi-objective route optimization (time/cost/carbon Pareto frontier) with geopolitical risk-adjusted lane costs
3. GUARDIAN Agent — Circuit breaker system that isolates degrading nodes before cascade failures
4. STOCKPILE Agent — Proactive inventory pre-positioning triggered by risk horizon signals
5. BROKER Agent — Carrier intelligence with dynamic health scoring and blackout detection
6. HERALD Agent — Behavioral nudge engine + intelligent alert triage

## WHAT TO BUILD

### COMPONENT 1: Simulated Environment (Python)

Create `environment/supply_chain_env.py`:

Build a realistic supply chain simulation with:
- 15 nodes: {Shanghai Port, Rotterdam Port, Hamburg Port, Singapore Port, LA Port, Frankfurt DC, London DC, Paris DC, New York DC, Chicago DC, Dubai Hub, Mumbai Hub, Tokyo Hub, Seoul Hub, Sydney DC}
- 30 active shipments with realistic attributes:
  - shipment_id, origin, destination, cargo_type, value_usd, sla_deadline_hours, current_node, current_carrier, route_planned, status
- Node attributes: throughput_capacity, current_queue_depth, avg_dwell_hours, health_score (0-1), circuit_state (closed/open/half-open)
- Edge/lane attributes: transit_hours, cost_per_teu, carbon_kg_per_teu, reliability_score, geopolitical_risk_score, capacity_utilization
- Carrier fleet: {Maersk, MSC, CMA CGM, Hapag-Lloyd, ONE, FedEx, DHL, UPS} with health scores

Implement a `DisruptionEngine` that can inject:
- Weather event: affects specific nodes, degrades throughput by 40-80%
- Port congestion: queue depth spike, dwell time increase
- Carrier disruption: specific carrier OTP drop
- Geopolitical: lane closure, risk premium increase
- Supplier financial stress: tier-2 supplier health score degradation

---

### COMPONENT 2: SENTINEL Agent (Python + Gemini API)

Create `agents/sentinel/sentinel_agent.py`:

**Dark Signal Intelligence Module**:
Use the Gemini API to classify freight disruption signals from a mock social media feed. Build a pipeline that:
1. Takes a list of mock social posts (realistic, you write them — include actual port names, carrier names, delay language)
2. Uses Gemini to classify each post: {disruption_signal: true/false, location: string, severity: low/medium/high, carrier_affected: string|null}
3. Aggregates signals by geographic cluster
4. Triggers when signal_volume × severity_weight exceeds 2.5σ baseline

**Supplier Financial Health Radar**:
Create composite health scores for 8 mock suppliers using:
- payment_delay_days (PAYDEX proxy)
- linkedin_hiring_trend (positive/flat/declining)
- news_sentiment_score (-1 to 1)
- satellite_facility_score (0-1 representing inferred facility activity)
- altman_z_proxy (financial health proxy)

**Risk Scoring Engine**:
Combine all signals into per-node risk scores. Output:
```json
{
  "node_id": "hamburg_port",
  "risk_score": 0.82,
  "horizon_hours": 72,
  "primary_driver": "dark_signal_osint",
  "secondary_driver": "weather",
  "confidence": 0.74,
  "recommended_action": "reroute_now"
}
```

---

### COMPONENT 3: NAVIGATOR Agent (Python + OR-Tools)

Create `agents/navigator/navigator_agent.py`:

**Multi-Objective Route Optimizer**:
Given a flagged shipment and a set of risk-adjusted network edges, generate K=5 alternative routes and compute Pareto-optimal set.

Objectives:
1. Minimize: expected_transit_hours × (1 + disruption_risk × 0.5)
2. Minimize: total_cost_usd (freight + insurance_premium + SLA_breach_probability × SLA_penalty)
3. Minimize: carbon_kg (GLEC framework: air=2.1 kg/t-km, road=0.096, sea=0.016, rail=0.028)
4. Minimize: geopolitical_risk_score (0-1 per corridor)

Use OR-Tools to enumerate route candidates. Return:
```json
{
  "shipment_id": "SHP-001",
  "recommended_route": {...},
  "alternatives": [...],
  "pareto_frontier": [...],
  "green_resilience_score": 0.84,
  "auto_execute": true,
  "confidence": 0.91
}
```

**Green-Resilience Correlation**:
Compute a `green_resilience_score` per route: routes with lower carbon intensity that also have higher historical reliability get a combined score bonus. This demonstrates the Green-Resilience thesis.

---

### COMPONENT 4: GUARDIAN Agent (Python)

Create `agents/guardian/circuit_breaker.py`:

Implement the full circuit breaker state machine:

```python
class CircuitBreaker:
    states = {CLOSED, OPEN, HALF_OPEN}
    
    def evaluate_node(self, node_metrics) -> CircuitAction:
        # Compute health score from:
        # - throughput_ratio (current/30d_avg)
        # - dwell_time_ratio
        # - queue_depth_velocity (rate of increase)
        # - error_rate
        # Returns: {action: open|close|half_open, health_score, downstream_impact}
    
    def cascade_prevention(self, opened_node) -> List[PreemptiveAction]:
        # Identify downstream nodes that will be stressed
        # Return preemptive load reduction actions
```

Thresholds:
- health_score < 0.35: OPEN circuit
- health_score > 0.70 for 3 consecutive probes: CLOSE circuit
- HALF_OPEN probe interval: 15 minutes (simulated as 15 seconds in demo)

---

### COMPONENT 5: STOCKPILE Agent (Python)

Create `agents/stockpile/preposition_agent.py`:

```python
def evaluate_preposition(dc_state, risk_scores, transfer_costs, demand_forecasts):
    """
    For each DC pair, compute:
    expected_disruption_cost = stockout_probability × units_at_risk × margin_per_unit
    transfer_cost = freight_cost + handling_cost
    
    Trigger if expected_disruption_cost > transfer_cost × safety_factor(1.3)
    
    Return prioritized transfer recommendations:
    [
      {from_dc, to_dc, sku, units, urgency, expected_cost_avoided, transfer_cost}
    ]
    """
```

Use realistic DC inventory data: each DC has 5 SKU categories with current stock, reorder points, and safety stock levels.

---

### COMPONENT 6: HERALD Agent + Behavioral Nudge Engine (Python)

Create `agents/herald/herald_agent.py` and `agents/herald/nudge_engine.py`:

**Alert Triage**:
```python
def compute_priority(event, shipment, operator_context):
    severity = event.magnitude × affected_shipment_count × disruption_duration
    business_impact = shipment.value × customer_tier_multiplier × sla_penalty_exposure
    p_sla_breach = compute_breach_probability(shipment.sla_deadline, expected_delay)
    
    priority_score = severity × business_impact × p_sla_breach × time_sensitivity
    return {priority_score, channel, message, escalation_path}
```

**Behavioral Nudge Engine**:
```python
class NudgeEngine:
    def generate_nudge(self, operator_id, recommendation, historical_overrides):
        """
        Analyze operator's override history on similar scenarios.
        Compute: algorithm_win_rate when operator historically overrides this pattern.
        
        Choose framing based on operator profile:
        - loss_aversion_framing: "Overriding costs you $X"
        - gain_framing: "Accepting saves you $X"  
        - social_proof: "81% of similar operators accepted this recommendation"
        - personal_history: "Last 5 times you overrode this pattern: 4 delays, 1 success"
        
        Return: {nudge_text, framing_type, urgency, historical_accuracy}
        """
```

---

### COMPONENT 7: FastAPI Backend

Create `api/main.py`:

Build a complete REST + WebSocket API:

```
GET  /api/network          → Full network state (nodes, shipments, agents)
GET  /api/shipments        → All active shipments with status
GET  /api/alerts           → Prioritized alert feed
POST /api/disruption       → Inject disruption event (for demo)
POST /api/override         → Operator override with nudge response
WS   /ws/live              → WebSocket for real-time agent decision stream

POST /api/sentinel/analyze → Run SENTINEL on current state
POST /api/navigator/route  → Get route recommendations for shipment
POST /api/guardian/check   → Evaluate circuit breaker state for node
POST /api/stockpile/eval   → Get pre-positioning recommendations
```

The WebSocket endpoint streams:
```json
{
  "type": "agent_decision",
  "agent": "SENTINEL",
  "timestamp": "...",
  "action": "risk_flag",
  "target": "hamburg_port",
  "risk_score": 0.82,
  "reasoning": "Dark signal spike detected: 47 social posts in 2h vs 3/h baseline"
}
```

Use Firebase Realtime Database to persist live state so the frontend can sync.

---

### COMPONENT 8: Control Tower Frontend (React)

Create a single-file React application `frontend/ControlTower.jsx`:

**Layout**: Split-panel design
- Left 60%: Google Maps with shipment markers, node status, disruption zones
- Right 40%: Agent decision feed, alert triage, circuit breaker panel

**Map Layer**:
- Use Google Maps JavaScript API
- Color-coded node markers: green (healthy), amber (at-risk), red (circuit open)
- Animated shipment paths along active routes
- Disruption zone overlays as pulsing circles
- Click node → show circuit breaker state, health metrics, affected shipments

**Agent Decision Feed** (right panel, top):
Real-time stream of agent decisions rendered as a live feed:
```
[SENTINEL 14:32:07] ⚠ Hamburg risk score → 0.82 | Dark signal spike
[GUARDIAN 14:32:09] 🔴 Hamburg circuit OPEN | 6 shipments rerouted
[NAVIGATOR 14:32:11] ↗ SHP-047 rerouted: Rotterdam via Denmark | +€1,200 / -4 days delay
[STOCKPILE 14:32:14] 📦 Frankfurt DC ← Rotterdam DC: 2,400 units pre-positioned
[HERALD 14:32:16] 📣 12 customers notified | 3 priority alerts escalated
```

**Pareto Route Chart**:
When a rerouting event occurs, display an animated scatter chart (Recharts):
- X-axis: Transit time (hours)
- Y-axis: Cost (USD)
- Bubble size: Carbon footprint
- Color: Geopolitical risk
- Highlight recommended route and current route

**Circuit Breaker Panel**:
Grid of all 15 nodes with visual circuit state (green closed padlock, red open padlock, yellow half-open). Animate transitions between states.

**Behavioral Nudge Modal**:
When operator clicks "Override Recommendation", show the nudge modal:
- Framed message (loss aversion format)
- Historical accuracy chart: "Your last 8 overrides in this scenario type"
- Two buttons: "Accept Recommendation" (highlighted) | "Override Anyway" (dimmed)
- If override: capture reason from dropdown + free text

**Inventory Pre-Positioning Panel**:
Bar chart comparing expected stockout risk before vs. after STOCKPILE action. Show transfer arrows on the map.

**Green-Resilience Frontier**:
Separate tab showing Pareto chart of available routes: carbon intensity vs. resilience score. Demonstrate that the recommended route sits near the optimal frontier on both dimensions simultaneously.

**Demo Controls Panel** (bottom strip):
Buttons for live demo control:
- "🌩 Inject Weather Event" → Hamburg port disruption
- "💸 Trigger Supplier Stress" → Tier-2 supplier health drop
- "📱 Simulate OSINT Spike" → Social media signal surge
- "⚡ Fast-Forward 2h" → Advance simulation time
- "🔄 Reset Network" → Return to clean state

---

### COMPONENT 9: Demo Script Automation

Create `demo/auto_demo.py`:

A script that runs the demo automatically with pre-scripted timing:
```
T+0s:   Initialize network, all green
T+10s:  OSINT spike begins (simulated social posts)
T+25s:  SENTINEL flags Hamburg risk 0.82
T+30s:  GUARDIAN opens Hamburg circuit
T+35s:  NAVIGATOR reroutes 6 shipments, shows Pareto chart
T+45s:  STOCKPILE triggers Frankfurt pre-positioning
T+55s:  HERALD sends 12 customer notifications
T+65s:  Operator attempts override — nudge fires
T+75s:  Show comparison: NEXUS vs Traditional outcome
T+90s:  Show Green-Resilience frontier
T+120s: Show Federated Intelligence concept slide
```

---

## DELIVERABLES

1. All Python agent files (complete, runnable with pip install requirements)
2. FastAPI main.py with all endpoints
3. Single-file React ControlTower.jsx (complete, production-quality)
4. requirements.txt
5. .env.example with all needed API keys
6. README.md with 3-step setup: pip install, python api/main.py, open frontend

## CONSTRAINTS

- All Gemini API calls use `gemini-1.5-flash` for cost efficiency
- Google Maps API key should be read from environment variable GOOGLE_MAPS_API_KEY
- No paid third-party services beyond Google Cloud
- All simulation data must use realistic logistics values (real port names, realistic costs, actual GLEC carbon factors)
- Frontend must run without a build step (use CDN imports) OR provide a simple npm dev setup
- Total cold-start time for demo: < 30 seconds

## QUALITY BAR

This demo will run live in front of Google engineers and supply chain industry experts. The UI must look like a production system, not a hackathon prototype. The agent reasoning must be explainable in plain English. The Pareto charts must be publication-quality. The behavioral nudge must be psychologically sophisticated and feel real.

Build this to win.
```

---

## FOLLOW-UP PROMPTS (Use these after the master prompt)

### Prompt 2 — MARL Training Demo
```
Now build the MARL training visualization component. Create a React component `MARLTrainingViz.jsx` that shows:
1. A live training curve (episodic reward vs. episode number) with 6 agent reward lines
2. Agent coordination quality metric: joint action optimality vs. IPPO baseline
3. A replay viewer: given a disruption scenario, step through agent decisions frame-by-frame
4. Curriculum stage indicator: which training phase the model is currently in

Use mock training data that shows clear improvement over 5,000 episodes with occasional dips representing curriculum transitions. Animate the curves drawing in real time.
```

### Prompt 3 — Federated Intelligence Visualization
```
Build a Federated Intelligence Network visualization as a React component `FederatedViz.jsx`:
1. Show 5 "company nodes" arranged in a ring around a central aggregator
2. Animate gradient flows from each company to the aggregator (using SVG path animations)
3. Show the privacy layer: gradients get "noised" before transmission (visual noise effect)
4. Display aggregate model accuracy improving with each round
5. Show what each company contributes (disruption signal volume) vs. receives (global intelligence score)
This should feel like a living network diagram, not a static chart.
```

### Prompt 4 — Supplier Health Dashboard
```
Build `SupplierRadar.jsx`: a supplier financial health monitoring dashboard showing:
1. A radar/spider chart for each of 8 suppliers with 5 axes: Financial, Operational, Market, Satellite, Trend
2. A timeline showing health score changes over 90 days (with simulated deterioration for 2 suppliers)
3. A tier mapping visualization: show how tier-1 suppliers depend on tier-2 and tier-3 nodes
4. Alert indicators for suppliers approaching the 0.4 amber threshold
5. Auto-generated "Early Warning Summary" text using the Gemini API: given a supplier's deteriorating metrics, generate a 3-sentence risk briefing
```

### Prompt 5 — Stress Test & Scenario Engine
```
Build `ScenarioEngine.jsx`: an interactive stress-testing tool that lets judges:
1. Select a disruption scenario from a library: {Red Sea closure, Shanghai lockdown, Carrier bankruptcy, Hurricane season, Geopolitical sanctions}
2. Configure severity (1-10 slider) and duration (1-90 days)
3. Click "Run Simulation" — runs 1,000 Monte Carlo episodes
4. Show: probability distribution of delay days, SLA breach probability, expected financial impact
5. Compare: NEXUS system outcome vs. naive/baseline system
6. Show carbon impact: how emergency air freight escalation increases emissions in baseline vs. NEXUS
This is the "stress test" that proves the system's resilience advantage quantitatively.
```

---

## ARCHITECTURE NOTES FOR OPUS

When building this system, keep the following architectural principles in mind:

**MARL Implementation Note**: For the MVP, implement the MARL agents as rule-based systems with learned-parameter overlays — the full MAPPO training loop is too expensive for a hackathon demo. The key is to demonstrate the MARL *architecture* and *reasoning*, with agent decisions that look and behave like trained policies. Use pre-computed Q-tables or simple neural network inference for action selection, trained offline on simulated data.

**Demo-First Engineering**: Every component should be buildable in isolation and demonstrable without other components running. The frontend should work with mock data if the backend is down. The backend should work without real API keys using stubbed responses.

**Explainability is Critical**: Every agent decision must include a `reasoning` field in plain English. Judges must be able to understand what each agent did and why. This is what separates a system from a black box.

**Performance**: The live demo WebSocket stream should update at 1-2 events per second. Fast enough to feel real-time, slow enough for judges to read each decision.

---

*NEXUS MVP Build Prompt v1.0 | Google Solutions Challenge 2026*
