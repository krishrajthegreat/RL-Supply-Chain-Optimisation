import { useEffect, useRef, useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Rss, AlertTriangle, MapPin } from 'lucide-react'
import { cn } from '@/lib/utils'

/* ═══════════════════════════════════════════════════════════════
   SIMPLIFIED WORLD MAP SVG PATHS
   Rough continent outlines for an equirectangular-ish projection.
   ViewBox: 0 0 1000 500
   ═══════════════════════════════════════════════════════════════ */
const CONTINENTS = [
  // North America
  'M 80 80 L 120 60 L 190 55 L 230 70 L 250 90 L 240 120 L 260 140 L 250 170 L 230 200 L 200 210 L 180 240 L 160 230 L 140 210 L 100 190 L 80 160 L 60 130 L 70 100 Z',
  // South America
  'M 200 280 L 220 260 L 250 270 L 270 300 L 280 340 L 290 370 L 280 400 L 260 430 L 240 440 L 220 420 L 210 390 L 200 350 L 190 310 Z',
  // Europe
  'M 440 70 L 470 55 L 510 60 L 530 80 L 520 110 L 540 130 L 520 150 L 490 160 L 460 150 L 440 130 L 430 100 Z',
  // Africa
  'M 440 190 L 470 180 L 510 190 L 540 220 L 550 260 L 560 300 L 550 350 L 530 380 L 500 390 L 470 380 L 450 340 L 440 300 L 430 250 L 435 220 Z',
  // Asia
  'M 540 60 L 580 50 L 640 40 L 700 50 L 760 60 L 810 80 L 830 110 L 820 140 L 790 160 L 750 170 L 710 180 L 670 190 L 630 180 L 600 170 L 570 150 L 550 120 L 540 90 Z',
  // South-East Asia / Indonesia
  'M 730 230 L 760 220 L 790 230 L 810 250 L 800 270 L 770 280 L 740 270 L 730 250 Z',
  // Australia
  'M 780 330 L 820 310 L 870 320 L 900 340 L 910 370 L 890 400 L 850 410 L 810 400 L 790 370 L 780 350 Z',
  // Middle East
  'M 560 160 L 590 150 L 620 170 L 610 200 L 580 210 L 555 200 L 550 180 Z',
  // Japan / Korean peninsula
  'M 830 100 L 845 90 L 855 100 L 850 130 L 840 140 L 830 120 Z',
  // Greenland
  'M 280 30 L 310 20 L 340 30 L 340 60 L 320 70 L 290 60 L 280 45 Z',
  // UK / Ireland
  'M 430 80 L 440 70 L 450 75 L 448 90 L 435 95 L 428 88 Z',
]

/* ═══════════════════════════════════════════════════════════════
   MAP NODES
   ═══════════════════════════════════════════════════════════════ */
interface MapNode {
  id: string
  label: string
  x: number
  y: number
  r: number
}

const NODES: MapNode[] = [
  { id: 'na-west',   label: 'NA_WEST',     x: 140, y: 150, r: 8 },
  { id: 'rotterdam', label: 'ROTTERDAM',    x: 475, y: 120, r: 8 },
  { id: 'dubai',     label: 'DUBAI',        x: 595, y: 200, r: 6 },
  { id: 'east-asia', label: 'EAST_ASIA',    x: 830, y: 110, r: 8 },
]

/* ═══════════════════════════════════════════════════════════════
   ROUTE ARCS (quadratic bezier)
   ═══════════════════════════════════════════════════════════════ */
interface RouteArc {
  from: string
  to: string
  d: string
  dashed: boolean
}

const ROUTES: RouteArc[] = [
  {
    from: 'na-west', to: 'rotterdam',
    d: 'M 140 150 Q 310 40 475 120',
    dashed: false,
  },
  {
    from: 'rotterdam', to: 'dubai',
    d: 'M 475 120 Q 530 100 595 200',
    dashed: true,
  },
  {
    from: 'dubai', to: 'east-asia',
    d: 'M 595 200 Q 720 140 830 110',
    dashed: false,
  },
  {
    from: 'na-west', to: 'east-asia',
    d: 'M 140 150 Q 500 -40 830 110',
    dashed: true,
  },
]

/* ═══════════════════════════════════════════════════════════════
   LIVE INTELLIGENCE DATA
   ═══════════════════════════════════════════════════════════════ */
const INTEL_ENTRIES = [
  { time: '13:45Z', text: 'Port of Rotterdam offloading efficiency up 12% against baseline.' },
  { time: '13:30Z', text: 'Security protocol Gamma initiated for high-value convoy Charlie.' },
  { time: '14:02Z', text: "Vessel 'Aegis-7' cleared Panama Canal transit. Proceeding to sector 4." },
  { time: '14:15Z', text: 'Anomalous weather pattern detected in North Atlantic corridor.' },
  { time: '14:22Z', text: 'Automated reroute completed for SHP-4412 via Cape of Good Hope.' },
  { time: '14:30Z', text: 'Cargo manifest verification completed for terminal B7-EAST.' },
]

/* ═══════════════════════════════════════════════════════════════
   ANIMATED PROGRESS BAR (risk index)
   ═══════════════════════════════════════════════════════════════ */
function RiskBar({ label, percent, color }: { label: string; percent: number; color: 'neon' | 'critical' }) {
  const barRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 300)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-[10px] tracking-widest text-muted">{label}</span>
        <span className="text-[10px] font-bold text-text">{percent}%</span>
      </div>
      <div className="h-1 w-full overflow-hidden rounded-full bg-border/40">
        <div
          ref={barRef}
          className={cn(
            'h-full rounded-full transition-all duration-1000 ease-out',
            color === 'neon' ? 'bg-neon' : 'bg-critical'
          )}
          style={{ width: visible ? `${percent}%` : '0%' }}
        />
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════
   SVG MAP NODE COMPONENT
   Inner solid circle + outer pulsing ring
   ═══════════════════════════════════════════════════════════════ */
function SvgNode({ x, y, r }: { x: number; y: number; r: number }) {
  return (
    <g>
      {/* Outer pulsing ring */}
      <circle
        cx={x}
        cy={y}
        r={r}
        fill="none"
        stroke="oklch(85% 0.35 142)"
        strokeWidth={1.5}
        opacity={0.6}
        style={{
          transformOrigin: `${x}px ${y}px`,
          animation: 'node-ping 2.5s ease-in-out infinite',
        }}
      />
      {/* Glow ring (static, dim) */}
      <circle
        cx={x}
        cy={y}
        r={r + 3}
        fill="none"
        stroke="oklch(85% 0.35 142 / 15%)"
        strokeWidth={4}
      />
      {/* Inner solid */}
      <circle
        cx={x}
        cy={y}
        r={r * 0.5}
        fill="oklch(85% 0.35 142)"
      />
    </g>
  )
}

/* ═══════════════════════════════════════════════════════════════
   PAGE COMPONENT
   ═══════════════════════════════════════════════════════════════ */
export default function GlobalMapPage() {
  return (
    <DashboardLayout>
      <div className="relative flex flex-col h-full -m-6">
        {/* ─── World map panel ─── */}
        <div
          className="relative flex-1 min-h-0 overflow-hidden"
          style={{ background: 'oklch(8% 0.03 180)' }}
        >
          <svg
            viewBox="0 0 1000 500"
            preserveAspectRatio="xMidYMid slice"
            className="absolute inset-0 h-full w-full"
          >
            <defs>
              {/* Dot-grid pattern overlay */}
              <pattern
                id="dot-grid"
                x={0}
                y={0}
                width={20}
                height={20}
                patternUnits="userSpaceOnUse"
              >
                <circle cx={10} cy={10} r={0.6} fill="oklch(85% 0.35 142 / 8%)" />
              </pattern>

              {/* Neon glow filter for routes */}
              <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur in="SourceGraphic" stdDeviation="2" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Continent shapes */}
            {CONTINENTS.map((d, i) => (
              <path
                key={i}
                d={d}
                fill="oklch(12% 0.04 180)"
                stroke="oklch(20% 0.06 180)"
                strokeWidth={0.8}
                opacity={0.9}
              />
            ))}

            {/* Dot-grid overlay */}
            <rect width="100%" height="100%" fill="url(#dot-grid)" />

            {/* Route arcs */}
            {ROUTES.map((route, i) => (
              <path
                key={i}
                d={route.d}
                fill="none"
                stroke="oklch(85% 0.35 142)"
                strokeWidth={1.5}
                strokeDasharray={route.dashed ? '6 4' : undefined}
                strokeLinecap="round"
                opacity={0.7}
                filter="url(#neon-glow)"
                style={route.dashed ? {
                  animation: 'route-dash 25s linear infinite',
                } : undefined}
              />
            ))}

            {/* Map nodes */}
            {NODES.map((node) => (
              <SvgNode key={node.id} x={node.x} y={node.y} r={node.r} />
            ))}
          </svg>
        </div>

        {/* ─── Bottom info cards (overlaid, 3 columns) ─── */}
        <div className="relative z-10 -mt-8 grid grid-cols-3 gap-4 px-6 pb-6">

          {/* ── Card 1: Live Intelligence ── */}
          <div className="rounded-sm border border-border bg-surface/95 backdrop-blur-sm p-4 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Rss size={14} className="text-neon" />
                <h3 className="text-[11px] font-semibold tracking-[0.15em] uppercase text-text">
                  Live Intelligence
                </h3>
              </div>
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-pulse-glow rounded-full bg-neon" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-neon" />
              </span>
            </div>

            {/* Scrollable log entries with vertical fade */}
            <div
              className="max-h-[160px] overflow-y-auto space-y-0 pr-1"
              style={{
                maskImage: 'linear-gradient(to bottom, transparent, black 15%, black 85%, transparent)',
                WebkitMaskImage: 'linear-gradient(to bottom, transparent, black 15%, black 85%, transparent)',
              }}
            >
              {INTEL_ENTRIES.map((entry, i) => (
                <div
                  key={i}
                  className="border-l-2 border-neon/40 py-2.5 pl-3"
                >
                  <span className="text-[10px] font-bold tracking-widest text-neon">
                    {entry.time}
                  </span>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-text/80">
                    {entry.text}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* ── Card 2: Global Risk Index ── */}
          <div className="rounded-sm border border-border bg-surface/95 backdrop-blur-sm p-4 animate-fade-in" style={{ animationDelay: '100ms' }}>
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle size={14} className="text-warn" />
              <h3 className="text-[11px] font-semibold tracking-[0.15em] uppercase text-text">
                Global Risk Index
              </h3>
            </div>

            {/* Status */}
            <p className="text-[9px] tracking-[0.2em] uppercase text-muted mb-1">
              Current Status
            </p>
            <div className="flex items-baseline gap-4 mb-3">
              <span className="font-display text-3xl font-bold tracking-wider text-neon">
                NOMINAL
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="font-display text-lg font-bold text-text">1.24</span>
                <span className="text-[10px] text-neon-dim">↓ 0.03 vs 24h</span>
              </div>
            </div>

            {/* Risk bars */}
            <div className="space-y-2.5">
              <RiskBar label="Supply Chain Integrity" percent={98} color="neon" />
              <RiskBar label="Geopolitical Disruption" percent={12} color="critical" />
            </div>
          </div>

          {/* ── Card 3: Active Hotspots ── */}
          <div className="rounded-sm border border-border bg-surface/95 backdrop-blur-sm p-4 animate-fade-in" style={{ animationDelay: '200ms' }}>
            {/* Header */}
            <div className="flex items-center gap-2 mb-3">
              <MapPin size={14} className="text-critical" />
              <h3 className="text-[11px] font-semibold tracking-[0.15em] uppercase text-text">
                Active Hotspots
              </h3>
            </div>

            {/* Hotspot 1 */}
            <div className="border-b border-border pb-3 mb-3">
              <p className="text-[11px] leading-relaxed text-muted mb-2">
                High vessel congestion detected. Estimated delay +14 hours for incoming convoys.
              </p>
              <div className="flex items-center justify-between">
                <span className="text-[9px] font-bold tracking-[0.2em] uppercase text-muted/70">
                  Impact: High
                </span>
                <button className="text-[10px] font-semibold tracking-widest text-neon transition-colors hover:text-neon-dim">
                  VIEW DETAILS &gt;
                </button>
              </div>
            </div>

            {/* Hotspot 2 */}
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-warn shrink-0" />
                <span className="text-[12px] font-bold text-text">
                  Port of Shanghai
                </span>
                <span className="ml-auto inline-flex items-center rounded-sm border border-warn px-2 py-0.5 text-[9px] font-bold tracking-widest text-warn">
                  WARNING
                </span>
              </div>
              <p className="text-[11px] leading-relaxed text-muted mb-2 pl-3.5">
                Automated crane system maintenance affecting terminals 3 and 4. Throughput -5%.
              </p>
              <div className="flex items-center justify-between pl-3.5">
                <span className="text-[9px] font-bold tracking-[0.2em] uppercase text-muted/70">
                  Impact: Low
                </span>
                <button className="text-[10px] font-semibold tracking-widest text-neon transition-colors hover:text-neon-dim">
                  VIEW DETAILS &gt;
                </button>
              </div>
            </div>
          </div>

        </div>
      </div>
    </DashboardLayout>
  )
}
