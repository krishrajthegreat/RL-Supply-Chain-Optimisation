import { useMemo } from 'react';
import { NODE_COORDS } from '../utils/constants';

const NODE_ORDER = [
  'hamburg_port', 'rotterdam_port', 'shanghai_port', 'la_port', 'singapore_port',
  'frankfurt_dc', 'london_dc', 'paris_dc', 'newyork_dc', 'chicago_dc',
  'dubai_hub', 'mumbai_hub', 'tokyo_hub', 'seoul_hub', 'sydney_dc',
];

export default function CircuitBreakerPanel({ state, risk }) {
  const nodes = useMemo(() => {
    if (!state?.network?.nodes) return [];
    const nodeMap = {};
    for (const n of state.network.nodes) nodeMap[n.id] = n;

    const riskMap = {};
    if (risk?.nodes) for (const r of risk.nodes) riskMap[r.node_id] = r;

    return NODE_ORDER.map(id => ({
      id,
      label: NODE_COORDS[id]?.label ?? id,
      type: NODE_COORDS[id]?.type ?? 'dc',
      health: nodeMap[id]?.health_score ?? 1,
      circuit: nodeMap[id]?.circuit_state ?? 'closed',
      risk: riskMap[id]?.risk_score ?? 0,
      status: riskMap[id]?.status ?? 'GREEN',
      throughput: nodeMap[id]?.throughput_ratio ?? 1,
    }));
  }, [state, risk]);

  const openCount = nodes.filter(n => n.circuit === 'open').length;
  const halfCount = nodes.filter(n => n.circuit === 'half_open').length;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-nexus-border)] shrink-0">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--color-nexus-muted)]">
          Circuit Breakers
        </h2>
        <div className="flex gap-2 text-[10px]">
          {openCount > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 font-semibold">{openCount} OPEN</span>
          )}
          {halfCount > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 font-semibold">{halfCount} HALF</span>
          )}
          {openCount === 0 && halfCount === 0 && (
            <span className="px-1.5 py-0.5 rounded bg-green-500/20 text-green-400 font-semibold">ALL CLOSED</span>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        {nodes.map(n => (
          <div key={n.id} className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-white/[0.03] transition-colors text-xs">
            {/* LED */}
            <span className={`led led-${n.circuit === 'half_open' ? 'half-open' : n.circuit}`} />

            {/* Name */}
            <span className="w-[90px] truncate font-medium text-[var(--color-nexus-text)]">{n.label}</span>

            {/* Type badge */}
            <span className="text-[9px] uppercase tracking-widest text-[var(--color-nexus-muted)] w-7">{n.type}</span>

            {/* Health bar */}
            <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${n.health * 100}%`,
                  background: n.health > 0.7 ? '#34d399' : n.health > 0.4 ? '#fbbf24' : '#f87171',
                }} />
            </div>

            {/* Health % */}
            <span className="w-9 text-right font-mono text-[10px]"
              style={{ color: n.health > 0.7 ? '#34d399' : n.health > 0.4 ? '#fbbf24' : '#f87171' }}>
              {(n.health * 100).toFixed(0)}%
            </span>

            {/* Risk */}
            <span className="w-9 text-right font-mono text-[10px]"
              style={{ color: n.risk > 0.55 ? (n.risk > 0.75 ? '#f87171' : '#fbbf24') : '#64748b' }}>
              {n.risk > 0.01 ? `${(n.risk * 100).toFixed(0)}%` : '-'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
