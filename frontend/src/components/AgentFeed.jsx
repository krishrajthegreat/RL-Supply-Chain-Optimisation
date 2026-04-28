import { useRef, useEffect } from 'react';

const EVENT_ICONS = {
  sentinel_decision: '\u{1F6E1}',
  disruption_event: '\u26A0',
  disruption_resolved: '\u2705',
  simulation_tick: '\u23F1',
  network_health: '\u{1F3E5}',
  simulation_reset: '\u{1F504}',
  simulation_started: '\u25B6',
  simulation_stopped: '\u23F8',
  osint_scan_complete: '\u{1F4E1}',
  financial_scan_complete: '\u{1F4B0}',
  connected: '\u{1F517}',
  full_state: '\u{1F4CB}',
};

const EVENT_COLORS = {
  sentinel_decision: 'border-cyan-500/40',
  disruption_event: 'border-red-500/40',
  disruption_resolved: 'border-green-500/40',
  simulation_tick: 'border-slate-600/40',
  network_health: 'border-slate-600/40',
  simulation_reset: 'border-amber-500/40',
};

function formatTime(ts) {
  if (!ts) return '';
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function AgentFeed({ events, connected, lastTick }) {
  const listRef = useRef(null);

  /* Meaningful events only (filter out ticks and health for display) */
  const display = events.filter(e =>
    e.event !== 'simulation_tick' &&
    e.event !== 'network_health' &&
    e.event !== 'keepalive'
  ).slice(0, 50);

  return (
    <div className="flex flex-col h-full">
      {/* Title bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-nexus-border)] shrink-0">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--color-nexus-muted)]">
          Agent Feed
        </h2>
        <div className="flex items-center gap-4 text-xs text-[var(--color-nexus-muted)]">
          {lastTick && (
            <span className="font-mono">
              Step {lastTick.step}/{lastTick.max_steps} |
              Delivered: {lastTick.metrics?.delivered ?? '-'} |
              SLA Breach: {lastTick.metrics?.sla_breaches ?? '-'} |
              Disruptions: {lastTick.metrics?.active_disruptions ?? '-'}
            </span>
          )}
          <span className={`${connected ? 'text-[var(--color-risk-green)]' : 'text-[var(--color-risk-red)]'}`}>
            {display.length} events
          </span>
        </div>
      </div>

      {/* Event list */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-3 py-1 space-y-1">
        {display.length === 0 && (
          <div className="flex items-center justify-center h-full text-[var(--color-nexus-muted)] text-sm">
            Waiting for events... Step the simulation or start auto-run.
          </div>
        )}
        {display.map((ev, i) => (
          <FeedItem key={`${ev._seq ?? i}-${i}`} event={ev} index={i} />
        ))}
      </div>
    </div>
  );
}

function FeedItem({ event: ev, index }) {
  const icon = EVENT_ICONS[ev.event] ?? '\u2022';
  const borderClass = EVENT_COLORS[ev.event] ?? 'border-slate-700/40';
  const ts = formatTime(ev._ts);
  const data = ev.data ?? {};

  let title = ev.event?.replace(/_/g, ' ')?.toUpperCase() ?? 'EVENT';
  let detail = '';

  if (ev.event === 'sentinel_decision') {
    title = `SENTINEL ${data.action_type === 'risk_flag_red' ? 'RED' : 'AMBER'}`;
    detail = `${data.target}: risk ${((data.details?.risk_score ?? 0) * 100).toFixed(1)}% — ${(data.reasoning ?? '').slice(0, 120)}`;
  } else if (ev.event === 'disruption_event') {
    title = `DISRUPTION: ${data.type?.toUpperCase() ?? '?'}`;
    detail = data.description?.slice(0, 140) ?? `Target: ${data.target_node ?? data.target_carrier ?? '?'}`;
  } else if (ev.event === 'connected') {
    title = 'CONNECTED';
    detail = data.message ?? 'WebSocket connected';
  } else if (ev.event === 'simulation_reset') {
    title = 'SIMULATION RESET';
    detail = `Seed: ${data.seed}, Steps: ${data.max_steps}`;
  } else if (ev.event === 'simulation_started') {
    title = 'AUTO-SIM STARTED';
    detail = `Speed: ${data.speed}s/step`;
  } else if (ev.event === 'osint_scan_complete') {
    title = 'OSINT SCAN';
    detail = data.summary ?? `Signals: ${data.signals_found}`;
  } else if (ev.event === 'financial_scan_complete') {
    title = 'FINANCIAL SCAN';
    detail = `G:${data.green} A:${data.amber} R:${data.red}`;
  }

  return (
    <div className={`flex items-start gap-2 px-2 py-1.5 rounded-lg border ${borderClass} bg-[var(--color-nexus-bg)]/40 animate-slide-in text-xs`}
      style={{ animationDelay: `${index * 30}ms` }}>
      <span className="text-base mt-0.5 shrink-0 w-5 text-center">{icon}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[var(--color-nexus-text)] tracking-wide">{title}</span>
          <span className="text-[var(--color-nexus-muted)] font-mono text-[10px] ml-auto shrink-0">{ts}</span>
        </div>
        {detail && <p className="text-[var(--color-nexus-muted)] mt-0.5 leading-snug truncate">{detail}</p>}
      </div>
    </div>
  );
}
