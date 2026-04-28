import { useMemo, useState, useEffect } from 'react';
import * as api from '../utils/api';

const CHART_W = 340, CHART_H = 160;
const PAD = { top: 20, right: 20, bottom: 30, left: 40 };
const PW = CHART_W - PAD.left - PAD.right;
const PH = CHART_H - PAD.top - PAD.bottom;

const AXIS_MODES = ['cost_vs_carbon', 'cost_vs_time', 'carbon_vs_time'];
const AXIS_LABELS = {
  cost_vs_carbon: { x: 'Cost ($/TEU)', y: 'Carbon (kg/TEU)' },
  cost_vs_time: { x: 'Cost ($/TEU)', y: 'Transit (hrs)' },
  carbon_vs_time: { x: 'Carbon (kg/TEU)', y: 'Transit (hrs)' },
};

export default function ParetoChart({ state }) {
  const [mode, setMode] = useState(0);
  const [routes, setRoutes] = useState(null);

  /* Fetch 5 diverse routes on mount */
  useEffect(() => {
    Promise.all([
      api.getPaths('shanghai_port', 'frankfurt_dc', 5).catch(() => null),
      api.getPaths('singapore_port', 'newyork_dc', 5).catch(() => null),
      api.getPaths('la_port', 'london_dc', 5).catch(() => null),
    ]).then(results => {
      const all = [];
      for (const r of results) {
        if (r?.routes) all.push(...r.routes);
      }
      setRoutes(all);
    });
  }, [state?.step]);

  const axisMode = AXIS_MODES[mode];
  const labels = AXIS_LABELS[axisMode];

  /* Compute plot data */
  const plotData = useMemo(() => {
    if (!routes?.length) return [];
    return routes.map((r, i) => {
      const cost = r.total_cost ?? 0;
      const carbon = r.total_carbon_kg ?? 0;
      const time = r.total_transit_hours ?? 0;
      const grs = r.green_resilience_score ?? 0.5;
      let x, y;
      if (axisMode === 'cost_vs_carbon')  { x = cost; y = carbon; }
      if (axisMode === 'cost_vs_time')    { x = cost; y = time; }
      if (axisMode === 'carbon_vs_time')  { x = carbon; y = time; }
      return { x, y, grs, path: r.path?.join(' → ') ?? `Route ${i + 1}`, cost, carbon, time, idx: i };
    });
  }, [routes, axisMode]);

  /* Axis scales */
  const { xMin, xMax, yMin, yMax } = useMemo(() => {
    if (!plotData.length) return { xMin: 0, xMax: 1, yMin: 0, yMax: 1 };
    const xs = plotData.map(d => d.x);
    const ys = plotData.map(d => d.y);
    const pad = 0.1;
    const xRange = Math.max(1, Math.max(...xs) - Math.min(...xs));
    const yRange = Math.max(1, Math.max(...ys) - Math.min(...ys));
    return {
      xMin: Math.min(...xs) - xRange * pad,
      xMax: Math.max(...xs) + xRange * pad,
      yMin: Math.min(...ys) - yRange * pad,
      yMax: Math.max(...ys) + yRange * pad,
    };
  }, [plotData]);

  const sx = (v) => PAD.left + ((v - xMin) / (xMax - xMin)) * PW;
  const sy = (v) => PAD.top + PH - ((v - yMin) / (yMax - yMin)) * PH;

  /* Compute Pareto front */
  const paretoIndices = useMemo(() => {
    if (!plotData.length) return new Set();
    const sorted = [...plotData].sort((a, b) => a.x - b.x);
    const front = new Set();
    let minY = Infinity;
    for (const p of sorted) {
      if (p.y <= minY) { front.add(p.idx); minY = p.y; }
    }
    return front;
  }, [plotData]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-nexus-border)] shrink-0">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--color-nexus-muted)]">
          Pareto Optimisation
        </h2>
        <button onClick={() => setMode((mode + 1) % 3)}
          className="text-[10px] px-2 py-0.5 rounded bg-[var(--color-nexus-border)] text-[var(--color-nexus-muted)] hover:text-white transition-colors">
          {labels.x} vs {labels.y}
        </button>
      </div>

      <div className="flex-1 flex items-center justify-center px-2">
        {!plotData.length ? (
          <p className="text-xs text-[var(--color-nexus-muted)]">Loading routes...</p>
        ) : (
          <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} className="w-full h-full max-h-[140px]">
            {/* Grid lines */}
            {[0, 0.25, 0.5, 0.75, 1].map(t => {
              const x = PAD.left + t * PW;
              const y = PAD.top + t * PH;
              return (
                <g key={t}>
                  <line x1={PAD.left} y1={y} x2={PAD.left + PW} y2={y} stroke="#1e293b" strokeWidth="0.5" />
                  <line x1={x} y1={PAD.top} x2={x} y2={PAD.top + PH} stroke="#1e293b" strokeWidth="0.5" />
                </g>
              );
            })}

            {/* Pareto front line */}
            {(() => {
              const pts = plotData.filter(p => paretoIndices.has(p.idx)).sort((a, b) => a.x - b.x);
              if (pts.length < 2) return null;
              const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${sx(p.x)} ${sy(p.y)}`).join(' ');
              return <path d={d} fill="none" stroke="#22d3ee" strokeWidth="1.5" strokeDasharray="4 2" opacity="0.6" />;
            })()}

            {/* Data points */}
            {plotData.map((p, i) => {
              const isPareto = paretoIndices.has(p.idx);
              return (
                <g key={i}>
                  <circle
                    className="pareto-dot"
                    cx={sx(p.x)} cy={sy(p.y)}
                    r={isPareto ? 5 : 3.5}
                    fill={isPareto ? '#22d3ee' : '#64748b'}
                    stroke={isPareto ? '#22d3ee' : 'none'}
                    strokeWidth="1"
                    opacity={isPareto ? 1 : 0.6}
                  />
                  {/* GRS label for pareto points */}
                  {isPareto && (
                    <text x={sx(p.x)} y={sy(p.y) - 8} textAnchor="middle" fontSize="7" fill="#22d3ee" fontFamily="Inter">
                      GRS {(p.grs * 100).toFixed(0)}%
                    </text>
                  )}
                </g>
              );
            })}

            {/* Axis labels */}
            <text x={PAD.left + PW / 2} y={CHART_H - 4} textAnchor="middle" fontSize="8" fill="#64748b" fontFamily="Inter">
              {labels.x}
            </text>
            <text x={10} y={PAD.top + PH / 2} textAnchor="middle" fontSize="8" fill="#64748b" fontFamily="Inter"
              transform={`rotate(-90, 10, ${PAD.top + PH / 2})`}>
              {labels.y}
            </text>

            {/* Axis ticks */}
            <text x={PAD.left} y={CHART_H - 16} fontSize="7" fill="#475569" fontFamily="Inter">{Math.round(xMin)}</text>
            <text x={PAD.left + PW} y={CHART_H - 16} fontSize="7" fill="#475569" fontFamily="Inter" textAnchor="end">{Math.round(xMax)}</text>
            <text x={PAD.left - 4} y={PAD.top + 4} fontSize="7" fill="#475569" fontFamily="Inter" textAnchor="end">{Math.round(yMax)}</text>
            <text x={PAD.left - 4} y={PAD.top + PH} fontSize="7" fill="#475569" fontFamily="Inter" textAnchor="end">{Math.round(yMin)}</text>
          </svg>
        )}
      </div>
    </div>
  );
}
