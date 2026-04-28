"""
WebSocket connection manager and live event broadcast for NEXUS.

Manages client connections and broadcasts simulation events
(agent decisions, disruption alerts, shipment updates) at
1-2 events per second as specified in the NEXUS architecture.

Event Types
-----------
  sentinel_decision  — SENTINEL risk flags with reasoning
  disruption_event   — New / resolved disruption
  shipment_update    — Shipment status change
  simulation_tick    — Periodic state snapshot
  network_health     — Node health summary
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Connection Manager
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ConnectionManager:
    """
    Manages WebSocket client connections.

    Thread-safe broadcast to all connected clients with
    automatic cleanup of dead connections.
    """

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._lock = asyncio.Lock()
        self._event_count = 0
        self._start_time = time.time()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(
            "WebSocket client connected. Total: %d",
            len(self.active_connections),
        )
        # Send welcome event
        await self._send_safe(websocket, {
            "event": "connected",
            "data": {
                "message": "Connected to NEXUS live stream",
                "active_clients": len(self.active_connections),
            },
        })

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected. Total: %d",
            len(self.active_connections),
        )

    async def broadcast(self, event: dict[str, Any]) -> None:
        """
        Broadcast an event to all connected clients.

        Automatically removes dead connections.
        """
        self._event_count += 1
        event["_seq"] = self._event_count
        event["_ts"] = time.time()

        dead: list[WebSocket] = []
        async with self._lock:
            connections = list(self.active_connections)

        for ws in connections:
            if not await self._send_safe(ws, event):
                dead.append(ws)

        # Clean up dead connections
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self.active_connections:
                        self.active_connections.remove(ws)

    async def broadcast_agent_decision(self, decision: dict) -> None:
        """Broadcast a structured agent decision."""
        await self.broadcast({
            "event": "sentinel_decision",
            "data": decision,
        })

    async def broadcast_disruption(
        self, event_data: dict, resolved: bool = False
    ) -> None:
        """Broadcast a disruption event (new or resolved)."""
        await self.broadcast({
            "event": "disruption_resolved" if resolved else "disruption_event",
            "data": event_data,
        })

    async def broadcast_tick(self, state_summary: dict) -> None:
        """Broadcast a periodic simulation tick summary."""
        await self.broadcast({
            "event": "simulation_tick",
            "data": state_summary,
        })

    async def broadcast_network_health(self, health_data: dict) -> None:
        """Broadcast node health summary."""
        await self.broadcast({
            "event": "network_health",
            "data": health_data,
        })

    @property
    def client_count(self) -> int:
        return len(self.active_connections)

    @property
    def events_per_second(self) -> float:
        elapsed = max(time.time() - self._start_time, 1)
        return self._event_count / elapsed

    @staticmethod
    async def _send_safe(ws: WebSocket, data: dict) -> bool:
        """Send JSON to a WebSocket, return False if connection dead."""
        try:
            await ws.send_json(data)
            return True
        except Exception:
            return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Global Connection Manager (singleton)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

manager = ConnectionManager()


def get_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return manager


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WebSocket Endpoint
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@router.websocket("/live")
async def websocket_live(websocket: WebSocket):
    """
    Live simulation event stream.

    Clients receive real-time events:
      • sentinel_decision — risk flags with full reasoning
      • disruption_event  — new disruption injected
      • disruption_resolved — disruption expired
      • simulation_tick   — periodic state snapshot
      • network_health    — node health updates

    Clients can send commands:
      • {"command": "ping"} → responds with pong
      • {"command": "get_state"} → responds with full state
    """
    await manager.connect(websocket)
    try:
        while True:
            # Listen for client messages (commands)
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=30.0
                )
                await _handle_client_message(websocket, data)
            except asyncio.TimeoutError:
                # Send keepalive ping
                await manager._send_safe(websocket, {
                    "event": "keepalive",
                    "data": {"clients": manager.client_count},
                })
            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.warning("WebSocket receive error: %s", exc)
                break

    finally:
        await manager.disconnect(websocket)


async def _handle_client_message(
    websocket: WebSocket, data: dict
) -> None:
    """Handle incoming client commands."""
    command = data.get("command", "")

    if command == "ping":
        await manager._send_safe(websocket, {
            "event": "pong",
            "data": {"ts": time.time()},
        })

    elif command == "get_state":
        # Import here to avoid circular import
        from nexus.api.main import get_simulation_state
        state = get_simulation_state()
        await manager._send_safe(websocket, {
            "event": "full_state",
            "data": state,
        })

    elif command == "subscribe":
        # Acknowledge subscription (all clients receive all events)
        await manager._send_safe(websocket, {
            "event": "subscribed",
            "data": {"topics": data.get("topics", ["all"])},
        })

    else:
        await manager._send_safe(websocket, {
            "event": "error",
            "data": {"message": f"Unknown command: {command}"},
        })
