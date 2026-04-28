import { useMemo } from 'react';
import { NODE_COORDS } from '../utils/constants';

const NODE_IDS = [
  'shanghai_port', 'rotterdam_port', 'hamburg_port', 'singapore_port', 'la_port',
  'frankfurt_dc', 'london_dc', 'paris_dc', 'newyork_dc', 'chicago_dc',
  'dubai_hub', 'mumbai_hub', 'tokyo_hub', 'seoul_hub', 'sydney_dc',
];

export default function StockpileView({ state }) {
  const items = useMemo(() => {
    if (!state?.inventory_levels || !state?.risk_scores) return [];
    return NODE_IDS.map(id => ({
      id,
      label: NODE_COORDS[id]?.label ?? id,
      type: NODE_COORDS[id]?.type ?? 'dc',
      inventory: state.inventory_levels[id] ?? 0,
      risk: state.risk_scores[id] ?? 0,
      needsPrePosition: (state.risk_scores[id] ?? 0) > 0.4 && (state.inventory_levels[id] ?? 0) < 0.5,
    }));
  }, [state]);

  const atRisk = items.filter(i => i.needsPrePosition).length;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-nexus-border)] shrink-0">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--color-nexus-muted)]">
          Inventory Stockpile
        </h2>
        {atRisk > 0 && (
          <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 text-[10px] font-semibold">
            {atRisk} NEED PRE-POSITION
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2">
        <div className="grid grid-cols-5 gap-1.5">
          {items.map(item => (
            <StockCell key={item.id} item={item} />
          ))}
        </div>
      </div>
    </div>
  );
}

function StockCell({ item }) {
  const fillH = Math.max(4, item.inventory * 100);
  const barColor = item.needsPrePosition
    ? '#f87171'
    : item.inventory > 0.6 ? '#34d399' : '#fbbf24';

  return (
    <div className={`relative flex flex-col items-center p-1 rounded-lg transition-colors ${item.needsPrePosition ? 'bg-red-500/5 ring-1 ring-red-500/20' : 'hover:bg-white/[0.02]'}`}
      title={`${item.label}: ${(item.inventory * 100).toFixed(0)}% inventory, ${(item.risk * 100).toFixed(0)}% risk`}>
      {/* Bar */}
      <div className="w-full h-10 bg-slate-800/60 rounded-sm overflow-hidden flex items-end">
        <div className="w-full rounded-sm transition-all duration-700"
          style={{ height: `${fillH}%`, background: barColor, opacity: 0.85 }} />
      </div>
      {/* Label */}
      <span className="text-[8px] mt-1 text-[var(--color-nexus-muted)] truncate w-full text-center leading-tight">
        {item.label}
      </span>
      <span className="text-[9px] font-mono" style={{ color: barColor }}>
        {(item.inventory * 100).toFixed(0)}%
      </span>
      {/* Pre-position indicator */}
      {item.needsPrePosition && (
        <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-red-500 rounded-full animate-ping" />
      )}
    </div>
  );
}
