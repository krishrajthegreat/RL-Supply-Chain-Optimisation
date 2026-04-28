# GLOBAL HACKATHON EXECUTION CONTEXT

> **Purpose:** This is a living document maintained across conversations to track exactly what we are building today for the Google Solutions Challenge Hackathon. It outlines our GCP migration strategy, demo setup, and current progress.

## 1. Primary Objective Today
Migrate the local NEXUS solution to Google Cloud Platform (GCP) and host it live. The application must be accessible online for the hackathon submission and demo.

## 2. Infrastructure Strategy (GCP)
We are optimizing for speed of deployment, cost efficiency (staying well under the $300 credit limit), and high visual impact for judges.

*   **Backend & Inference Hosting:** Google Cloud Run
    *   *Why:* Serverless, scales to zero, provides an instant HTTPS endpoint, and is perfect for hosting our FastAPI app.
    *   *Status:* [ ] To be containerized (Docker) and deployed.
*   **Real-time State Sync:** Firebase Realtime Database (or Firestore)
    *   *Why:* Instantly pushes RL agent decisions to the frontend map without managing custom WebSockets.
    *   *Status:* [ ] To be integrated into backend and frontend.
*   **RL Explainability & OSINT:** Gemini API (Vertex AI / Google AI Studio)
    *   *Why:* Acts as an intelligent chatbot that explains *why* the RL agent made specific routing decisions, increasing trust.
    *   *Status:* [ ] To be implemented in the `SENTINEL` agent.
*   **Control Tower Visualization:** Deck.gl + MapLibre GL (with path to Google Maps API)
    *   *Why:* Provides a beautiful, dynamic, dark-mode map for the frontend control tower with zero cost for development. Deck.gl allows easy porting to Google Maps API for the final GCP demo.
    *   *Status:* [x] Integrated into the Vite React frontend with mock data scenarios.

## 3. Demo & ML Strategy
*   **Model Strategy:** We are **NOT** training online. We have a pre-trained HAPPO model located in the local `checkpoints` directory. We will load these saved weights purely for *inference* inside the Cloud Run backend.
*   **Environment Setup:** We are sticking strictly to a **Controlled Demo Setup**. We will use mock JSON data and "God-mode" injection buttons (e.g., "Trigger Hamburg Storm") rather than fragile live APIs. This guarantees a flawless 5-minute presentation.

## 4. Execution Checklist
- [ ] Ensure local backend serves the trained HAPPO model from `checkpoints/` successfully.
- [ ] Integrate Gemini API into the backend for OSINT/Chatbot explainability.
- [x] Migrate frontend visualization to use Deck.gl + MapLibre GL with mock demo scenarios.
- [ ] Connect backend and frontend via Firebase for real-time state synchronization.
- [ ] Write `Dockerfile` for the FastAPI backend.
- [ ] Deploy backend to Google Cloud Run.
- [ ] Deploy frontend to Firebase Hosting or Vercel/Netlify.
- [ ] Final end-to-end test of the "Hamburg Storm Surge" demo scenario.

---
*Note to AI Assistant: Always check and update this document when major architectural changes, deployment steps, or GCP integrations are completed.*
