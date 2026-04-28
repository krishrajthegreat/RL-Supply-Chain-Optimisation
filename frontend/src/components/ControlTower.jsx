import { useMemo, useState } from 'react';
import { NODE_COORDS, EDGE_PAIRS, toSVG, riskColor, riskStatus } from '../utils/constants';

const W = 1000, H = 520;

export default function ControlTower({ state, risk, onNodeClick }) {
  const [hovered, setHovered] = useState(null);

  /* Pre-compute SVG positions for all nodes */
  const positions = useMemo(() => {
    const map = {};
    for (const [id, c] of Object.entries(NODE_COORDS)) {
      map[id] = toSVG(c.lat, c.lng, W, H);
    }
    return map;
  }, []);

  /* Build risk score lookup */
  const riskScores = useMemo(() => {
    if (!risk?.nodes) return {};
    const m = {};
    for (const n of risk.nodes) m[n.node_id] = n.risk_score;
    return m;
  }, [risk]);

  /* Active disruptions per node */
  const disruptedNodes = useMemo(() => {
    const s = new Set();
    if (state?.active_disruptions) {
      for (const d of state.active_disruptions) {
        if (d.target_node) s.add(d.target_node);
      }
    }
    return s;
  }, [state]);

  /* Circuit states */
  const circuits = useMemo(() => {
    if (!state?.network?.nodes) return {};
    const m = {};
    for (const n of state.network.nodes) m[n.id] = n.circuit_state;
    return m;
  }, [state]);

  const tooltipNode = hovered ? NODE_COORDS[hovered] : null;
  const tooltipPos = hovered ? positions[hovered] : null;
  const tooltipRisk = hovered ? (riskScores[hovered] ?? 0) : 0;

  return (
    <div className="relative w-full h-full flex flex-col">
      {/* Title bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--color-nexus-border)]">
        <h2 className="text-sm font-semibold tracking-wide uppercase text-[var(--color-nexus-muted)]">
          Global Network
        </h2>
        <div className="flex gap-3 text-[10px] text-[var(--color-nexus-muted)]">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[var(--color-risk-green)]" /> GREEN</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[var(--color-risk-amber)]" /> AMBER</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[var(--color-risk-red)]" /> RED</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm border border-[var(--color-nexus-muted)]" /> Circuit</span>
        </div>
      </div>

      {/* SVG Map */}
      <svg viewBox={`0 0 ${W} ${H}`} className="flex-1 w-full" style={{ background: 'radial-gradient(ellipse at 50% 40%, #0f172a 0%, #020617 100%)' }}>
        {/* Background grid */}
        <defs>
          <pattern id="grid" width="50" height="50" patternUnits="userSpaceOnUse">
            <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#1e293b" strokeWidth="0.3" />
          </pattern>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <rect width={W} height={H} fill="url(#grid)" />

        {/* Edges */}
        {EDGE_PAIRS.map(([a, b], i) => {
          const pa = positions[a], pb = positions[b];
          if (!pa || !pb) return null;
          const anyDisrupted = disruptedNodes.has(a) || disruptedNodes.has(b);
          return (
            <line key={i} x1={pa.x} y1={pa.y} x2={pb.x} y2={pb.y}
              stroke={anyDisrupted ? '#f8717144' : '#334155'}
              strokeWidth={anyDisrupted ? 1.2 : 0.6}
              strokeDasharray={anyDisrupted ? '4 3' : 'none'}
            />
          );
        })}

        {/* Nodes */}
        {Object.entries(NODE_COORDS).map(([id, coord]) => {
          const pos = positions[id];
          const score = riskScores[id] ?? 0;
          const status = riskStatus(score);
          const color = riskColor(score);
          const disrupted = disruptedNodes.has(id);
          const circuit = circuits[id] ?? 'closed';
          const r = hovered === id ? 10 : disrupted ? 8 : 6;

          return (
            <g key={id}
              onMouseEnter={() => setHovered(id)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => onNodeClick?.(id)}
              style={{ cursor: 'pointer' }}>
              {/* Outer glow ring */}
              {(disrupted || status !== 'green') && (
                <circle cx={pos.x} cy={pos.y} r={r + 6} fill="none"
                  stroke={color} strokeWidth="1" opacity="0.3"
                  className={`node-${status}`} />
              )}
              {/* Main dot */}
              <circle cx={pos.x} cy={pos.y} r={r} fill={color} filter="url(#glow)" opacity={0.95} />
              {/* Circuit breaker ring */}
              {circuit !== 'closed' && (
                <circle cx={pos.x} cy={pos.y} r={r + 3} fill="none"
                  stroke={circuit === 'open' ? '#f87171' : '#fbbf24'}
                  strokeWidth="2" strokeDasharray="3 2" />
              )}
              {/* Label */}
              <text x={pos.x} y={pos.y - r - 5} textAnchor="middle"
                fontSize="9" fill="#94a3b8" fontFamily="Inter, sans-serif"
                fontWeight={disrupted ? '600' : '400'}
                style={{ pointerEvents: 'none', fill: disrupted ? '#e2e8f0' : '#94a3b8' }}>
                {coord.label}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {hovered && tooltipNode && tooltipPos && (
        <div className="absolute glass-panel px-3 py-2 text-xs pointer-events-none z-10 min-w-[160px]"
          style={{ left: `${(tooltipPos.x / W) * 100}%`, top: `${(tooltipPos.y / H) * 100 - 12}%`, transform: 'translate(-50%, -100%)' }}>
          <div className="font-semibold text-white">{tooltipNode.label}</div>
          <div className="text-[var(--color-nexus-muted)]">Type: {tooltipNode.type}</div>
          <div className="flex items-center gap-2 mt-1">
            <span>Risk:</span>
            <span className="font-mono font-bold" style={{ color: riskColor(tooltipRisk) }}>
              {(tooltipRisk * 100).toFixed(1)}%
            </span>
          </div>
          {disruptedNodes.has(hovered) && (
            <div className="text-[var(--color-risk-red)] mt-0.5 font-semibold">DISRUPTED</div>
          )}
          {circuits[hovered] !== 'closed' && (
            <div className="text-[var(--color-risk-amber)] mt-0.5">Circuit: {circuits[hovered]?.toUpperCase()}</div>
          )}
        </div>
      )}
    </div>
  );
}
