# NEXUS — Neural EXecution and Unified Supply-chain Intelligence System
<img width="1919" height="874" alt="image" src="https://github.com/user-attachments/assets/e2b34f3d-c2da-41a6-bbe0-6ec643abd4cb" />

## Executive Summary
Checkout demo at: https://nexus-krish.web.app/ 


NEXUS is a multi-agent reinforcement learning (MARL) system designed to transform reactive supply chain management into a self-optimizing, proactively resilient network. Instead of relying on dashboards that display issues after they occur, NEXUS deploys six specialized AI agents that cooperate in real-time to predict, isolate, reroute, pre-position, and communicate around supply disruptions before they cascade. 

Built entirely on Google Cloud infrastructure, NEXUS demonstrates that applying AI to global logistics serves both efficiency and global sustainability.

---

## The Problem: Structural Failures in Logistics

Modern supply chains suffer from five critical structural failures:
1. **Information Asymmetry:** Stakeholders hoard information to avoid penalties, leading to reactive decision-making based on delayed data.
2. **The Upstream Blindspot:** Lack of visibility into tier-2 and tier-3 supplier financial health, where 94% of supply disruptions originate.
3. **The Cascade Amplification Problem:** Disruptions are highly contagious. Tightly coupled logistics networks lack circuit breakers to absorb localized shocks.
4. **Human Override:** Human operators frequently override algorithmic optimizations due to familiarity bias and fear of accountability.
5. **Sustainability as a Cost:** Carbon intensity is often viewed merely as an ESG metric rather than an indicator of route fragility and disruption risk.

---

## MARL Architecture & The Six Agents

NEXUS leverages **Heterogeneous-Agent Proximal Policy Optimization (HAPPO)** with a Centralized Training, Decentralized Execution (CTDE) paradigm. This allows for complex coordination between specialized agents during training while enabling autonomous, decentralized execution during production.

### 1. SENTINEL — Risk & Disruption Intelligence Agent
The early warning system. It continuously scores nodes, lanes, and suppliers for disruption probability using multimodal inputs, including weather, port congestion, operational health, and NLP-processed social OSINT signals (powered by the Gemini API).

### 2. NAVIGATOR — Dynamic Routing Agent
Executes optimal route adjustments based on disruption risks. It solves a multi-objective Pareto optimization problem, balancing transit time, cost, carbon footprint, and geopolitical risk. It also implements a Green-Resilience Correlation Module, proving that lower-carbon routes are often more resilient.

### 3. GUARDIAN — Circuit Breaker Agent
Monitors node health and automatically isolates degrading infrastructure nodes before failures propagate. It acts similarly to electrical circuit breakers, executing pre-signed capacity contracts when a node is flagged as "OPEN".

### 4. STOCKPILE — Inventory Pre-Positioning Agent
Proactively rebalances inventory across distribution centers based on early risk signals from SENTINEL. It triggers transfers when the cost of moving inventory is lower than the expected cost of a stockout.

### 5. BROKER — Carrier Intelligence & Selection Agent
Maintains a live intelligence model of carrier reliability, capacity, and financial health. It dynamically flags underperforming carriers and recommends capacity hedging on volatile lanes.

### 6. HERALD — Stakeholder Communication Agent
Manages all outbound communications and incorporates a Behavioral Nudge Engine. It tracks human overrides of algorithmic decisions and reframes recommendations to counter cognitive biases (e.g., loss aversion) and improve system trust.


---
**User Flow Diagram:**
<img width="6965" height="6489" alt="image" src="https://github.com/user-attachments/assets/82d3f552-ee70-44cd-a3af-a283262acf57" />

**System Architecture Diagram:**
<img width="8191" height="4634" alt="image" src="https://github.com/user-attachments/assets/224aa8eb-4e00-487b-b2a0-fd1801d054a9" />



---

## Infrastructure & Technology Stack

The project is optimized for speed, cost efficiency, and high visual impact, utilizing the following Google Cloud Platform (GCP) services:

* **Google Cloud Run:** Hosts the serverless FastAPI backend and pre-trained MARL inference engine.
* **Firebase Realtime Database:** Manages real-time state synchronization for the control tower UI, pushing RL agent decisions instantly to the frontend.
* **Gemini API (Vertex AI):** Powers the OSINT NLP layer for early signal extraction and acts as an explainability engine for RL routing decisions.
* **Deck.gl + MapLibre GL:** Renders the high-performance, WebGL-accelerated global map visualization on the frontend.
* **Frontend:** React, Tailwind CSS (v4), Three.js, Recharts, and D3.js for a brutalist-minimalist command center interface.

---

## Hackathon Execution Strategy & Demo

For the purpose of the Google Solutions Challenge Hackathon, the system operates in a **Controlled Demo Setup**:
* **Pre-trained Inference:** Models are pre-trained using historical data (FBX, ACLED, GDELT). The Cloud Run backend serves the saved HAPPO weights strictly for inference.
* **Scenario Execution:** The demo utilizes mock JSON data and scenario injection (e.g., "Hamburg Storm Surge") to guarantee a flawless presentation of the system's end-to-end capabilities without relying on fragile live APIs.

---

## Future Scope: The Roadmap to Global Resilience

While the current MVP demonstrates the core MARL logic on GCP, the roadmap for NEXUS extends into a global logistics nervous system:

1.  **Federated Intelligence Network:** Implementing Federated Learning to allow decentralized model training across different logistics firms, building a collective intelligence on global risks (port strikes, canal blockages) without sharing raw shipment data.
2.  **Live Multi-Modal OSINT Pipeline:** Moving beyond mock data to a live **Vertex AI** pipeline that scrapes and classifies real-time news and social signals using **Gemini 1.5 Pro**.
3.  **IoT & Telemetry Integration:** Connecting to **Google Cloud IoT Core** to ingest live telemetry from container sensors (temperature, vibration, GPS), allowing agents to respond to the physical condition of cargo.
4.  **Blockchain-Enabled Auto-Contracting:** Integrating with Google's **Blockchain Node Engine** to automatically trigger payments and capacity re-bookings when the `GUARDIAN` or `BROKER` agents execute a network pivot.
5.  **Advanced XAI (Explainable AI):** Expanding the Gemini explainability layer to provide counterfactual reasoning, answering questions like *"How much would we have lost if the circuit breaker hadn't fired?"*

---

## Submission Highlights (For Judges)

*   **Architectural Novelty:** Uses **HAPPO (Heterogeneous-Agent PPO)**, a cutting-edge MARL framework that handles specialized agents better than standard MAPPO.
*   **The "Dark Signal" Edge:** Mining informal social signals for early warnings—a capability missing from almost all commercial logistics platforms.
*   **The Behavioral Layer:** The **Behavioral Nudge Engine** treats the human-AI interface as a first-class engineering problem, tracking and mitigating human cognitive biases in logistics.
*   **Full GCP Integration:** Seamlessly leverages Cloud Run, Vertex AI (Gemini), Firebase Realtime DB, and the Google Maps Platform.

---


## Project Structure

```text
NEXUS/
├── frontend/              # Frontend React Application
│   ├── src/               # React components, pages, and UI assets
│   └── index.html         # Application entry point
└── nexus/                 # Python Backend & MARL Framework
    ├── nexus/
    │   ├── api/           # FastAPI Server
    │   ├── agents/        # MARL Agent implementations (Sentinel, Navigator, etc.)
    │   ├── environment/   # Simulation and disruption sampler
    │   ├── training/      # HAPPO Framework and evaluation
    │   └── data/          # Mock data scenarios for demo execution
    └── requirements.txt   # Backend dependencies
```
