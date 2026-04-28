import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * Custom hook for persistent WebSocket connection to NEXUS live stream.
 * Auto-reconnects on disconnect with exponential backoff.
 */
export function useWebSocket() {
  const [events, setEvents] = useState([]);
  const [connected, setConnected] = useState(false);
  const [lastTick, setLastTick] = useState(null);
  const wsRef = useRef(null);
  const retryRef = useRef(0);
  const maxEvents = 150;

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/live`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      retryRef.current = 0;
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.event === 'simulation_tick') {
          setLastTick(data.data);
        }
        if (data.event !== 'keepalive') {
          setEvents((prev) => [data, ...prev].slice(0, maxEvents));
        }
      } catch { /* ignore malformed */ }
    };

    ws.onclose = () => {
      setConnected(false);
      const delay = Math.min(1000 * 2 ** retryRef.current, 10000);
      retryRef.current += 1;
      setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => { if (wsRef.current) wsRef.current.close(); };
  }, [connect]);

  const send = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { events, connected, lastTick, send };
}
