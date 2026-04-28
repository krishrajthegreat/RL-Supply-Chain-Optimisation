import { useState, useEffect, useCallback } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import * as api from './utils/api';
import ControlTower from './components/ControlTower';
import AgentFeed from './components/AgentFeed';
import CircuitBreakerPanel from './components/CircuitBreakerPanel';
import StockpileView from './components/StockpileView';
import ParetoChart from './components/ParetoChart';
import NudgeModal from './components/NudgeModal';
import './index.css';

export default function App() {
  /* ── Global state ──────────────────────────────────── */
  const { events, connected, lastTick, send } = useWebSocket();
  const [state, setState] = useState(null);
  const [risk, setRisk] = useState(null);
  const [simRunning, setSimRunning] = useState(false);
  const [nudge, setNudge] = useState(null);
  const [loading, setLoading] = useState(true);

  /* ── Load initial state ────────────────────────────── */
  const refresh = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([api.getState(), api.getRiskReport()]);
      setState(s);
      setRisk(r);
    } catch (e) { console.warn('Refresh failed:', e); }
  }, []);

  useEffect(() => { refresh().then(() => setLoading(false)); }, [refresh]);

  /* ── Auto-refresh on simulation tick ────────────────── */
  useEffect(() => {
    if (lastTick) refresh();
  }, [lastTick, refresh]);

  /* ── Check for nudge triggers ──────────────────────── */
  useEffect(() => {
    const sentinel = events.find(e => e.event === 'sentinel_decision');
    if (sentinel && sentinel.data?.action_type === 'risk_flag_red' && !nudge) {
      setNudge({
        title: `RED ALERT: ${sentinel.data.target}`,
        message: sentinel.data.reasoning,
        options: [
          { label: 'Inject Hamburg Scenario', action: 'inject' },
          { label: 'Step Simulation (+10)', action: 'step' },
          { label: 'Dismiss', action: 'dismiss' },
        ],
      });
    }
  }, [events, nudge]);

  /* ── Simulation controls ───────────────────────────── */
  const handleReset = async () => {
    await api.simReset({ seed: 42, max_steps: 168, disruption_probability: 0.02 });
    refresh();
  };

  const handleStep = async (n = 1) => {
    await api.simStep(n);
    refresh();
  };

  const handleToggleRun = async () => {
    if (simRunning) {
      await api.simStop();
      setSimRunning(false);
    } else {
      await api.simStart(0.8);
      setSimRunning(true);
    }
  };

  const handleInjectHamburg = async () => {
    await api.injectScenario('hamburg_storm');
    refresh();
  };

  const handleNudge = async (action) => {
    setNudge(null);
    if (action === 'inject') await handleInjectHamburg();
    if (action === 'step') await handleStep(10);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full border-2 border-t-[var(--color-nexus-accent)] border-[var(--color-nexus-border)] animate-spin" />
          <p className="text-[var(--color-nexus-muted)] text-sm tracking-wider uppercase">Initialising NEXUS</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Header ───────────────────────────────────── */}
      <header className="h-14 px-5 flex items-center justify-between border-b border-[var(--color-nexus-border)] bg-[var(--color-nexus-panel)]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-white font-black text-sm">N</div>
          <h1 className="text-lg font-bold tracking-tight">NEXUS <span className="text-[var(--color-nexus-muted)] font-normal text-sm ml-1">Control Tower</span></h1>
        </div>

        <div className="flex items-center gap-3">
          {/* WebSocket status */}
          <span className={`flex items-center gap-1.5 text-xs ${connected ? 'text-[var(--color-risk-green)]' : 'text-[var(--color-risk-red)]'}`}>
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-[var(--color-risk-green)]' : 'bg-[var(--color-risk-red)]'}`} />
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>

          {/* Step counter */}
          <span className="text-xs text-[var(--color-nexus-muted)] font-mono">
            STEP {state?.step ?? 0}/{state?.max_steps ?? 168}
          </span>

          {/* Controls */}
          <button onClick={handleReset} className="px-3 py-1.5 text-xs rounded-lg bg-[var(--color-nexus-border)] hover:bg-slate-700 transition-colors" title="Reset">
            Reset
          </button>
          <button onClick={() => handleStep(1)} className="px-3 py-1.5 text-xs rounded-lg bg-[var(--color-nexus-border)] hover:bg-slate-700 transition-colors">
            +1 Step
          </button>
          <button onClick={() => handleStep(10)} className="px-3 py-1.5 text-xs rounded-lg bg-[var(--color-nexus-border)] hover:bg-slate-700 transition-colors">
            +10
          </button>
          <button onClick={handleToggleRun} className={`px-3 py-1.5 text-xs rounded-lg transition-colors font-semibold ${simRunning ? 'bg-[var(--color-risk-red)] text-white' : 'bg-cyan-600 text-white hover:bg-cyan-500'}`}>
            {simRunning ? 'Stop' : 'Auto-Run'}
          </button>
          <button onClick={handleInjectHamburg} className="px-3 py-1.5 text-xs rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold transition-colors">
            Hamburg Storm
          </button>
        </div>
      </header>

      {/* ── Main Grid ────────────────────────────────── */}
      <main className="flex-1 grid grid-cols-[1fr_380px] grid-rows-[1fr_280px] gap-2 p-2 overflow-hidden" style={{ height: 'calc(100vh - 56px)' }}>

        {/* Map — top left */}
        <div className="glass-panel overflow-hidden animate-fade-in">
          <ControlTower state={state} risk={risk} onNodeClick={(id) => console.log('Node:', id)} />
        </div>

        {/* Right panels — stacked */}
        <div className="flex flex-col gap-2 overflow-hidden">
          <div className="glass-panel flex-1 overflow-auto animate-fade-in" style={{ animationDelay: '0.1s' }}>
            <CircuitBreakerPanel state={state} risk={risk} />
          </div>
          <div className="glass-panel flex-1 overflow-auto animate-fade-in" style={{ animationDelay: '0.2s' }}>
            <StockpileView state={state} />
          </div>
          <div className="glass-panel flex-1 overflow-hidden animate-fade-in" style={{ animationDelay: '0.3s' }}>
            <ParetoChart state={state} />
          </div>
        </div>

        {/* Agent Feed — bottom spanning full width */}
        <div className="glass-panel col-span-2 overflow-hidden animate-fade-in" style={{ animationDelay: '0.15s' }}>
          <AgentFeed events={events} connected={connected} lastTick={lastTick} />
        </div>
      </main>

      {/* Nudge Modal */}
      {nudge && <NudgeModal nudge={nudge} onAction={handleNudge} />}
    </div>
  );
}
