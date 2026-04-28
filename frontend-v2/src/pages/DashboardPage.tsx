import { useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import StatCard from '@/components/ui/StatCard'
import {
  Gauge,
  Network,
  AlertTriangle,
  Circle,
  Filter,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { cn } from '@/lib/utils'

/* ══════════════════════════════════════════════════════════
   CHART DATA — 12 data points for the throughput bar chart
   ══════════════════════════════════════════════════════════ */
const THROUGHPUT_DATA = [
  { name: 'Jan', volume: 72000 },
  { name: 'Feb', volume: 55000 },
  { name: 'Mar', volume: 91000 },
  { name: 'Apr', volume: 43000 },
  { name: 'May', volume: 68000 },
  { name: 'Jun', volume: 82000 },
  { name: 'Jul', volume: 95000 },
  { name: 'Aug', volume: 37000 },
  { name: 'Sep', volume: 78000 },
  { name: 'Oct', volume: 61000 },
  { name: 'Nov', volume: 85000 },
  { name: 'Dec', volume: 50000 },
]

/* ══════════════════════════════════════════════════════════
   BOTTLENECK DATA
   ══════════════════════════════════════════════════════════ */
type Severity = 'CRITICAL' | 'WARN'

interface Bottleneck {
  id: string
  name: string
  severity: Severity
  description: string
  impact: string
  action: string
}

const BOTTLENECKS: Bottleneck[] = [
  {
    id: 'sector-7g',
    name: 'SECTOR_7G',
    severity: 'CRITICAL',
    description: 'Projected capacity overload in T-minus 4 hours.',
    impact: 'Impact: High',
    action: 'Resolve →',
  },
  {
    id: 'hub-eu-west',
    name: 'HUB_EU_WEST',
    severity: 'WARN',
    description: 'Latency spike detected in customs clearance queue.',
    impact: 'Impact: Medium',
    action: 'Details →',
  },
  {
    id: 'route-a44',
    name: 'ROUTE_A44',
    severity: 'WARN',
    description: 'Weather pattern disrupting automated transit lanes.',
    impact: 'Impact: Medium',
    action: 'Details →',
  },
]

const TIME_FILTERS = ['1H', '24H', '7D'] as const

/* ══════════════════════════════════════════════════════════
   CUSTOM TOOLTIP
   ══════════════════════════════════════════════════════════ */
function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: { value: number }[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-sm border border-border bg-surface px-3 py-2 shadow-lg">
      <p className="text-[10px] tracking-widest text-muted">{label}</p>
      <p className="font-display text-sm font-bold text-neon">
        {payload[0].value.toLocaleString('en-US')}
      </p>
    </div>
  )
}

/* ══════════════════════════════════════════════════════════
   SEVERITY BADGE
   ══════════════════════════════════════════════════════════ */
function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm px-2 py-0.5 text-[10px] font-bold tracking-widest',
        severity === 'CRITICAL'
          ? 'bg-critical/20 text-critical animate-pulse-red'
          : 'bg-warn/20 text-warn'
      )}
    >
      {severity}
    </span>
  )
}

/* ══════════════════════════════════════════════════════════
   PAGE COMPONENT
   ══════════════════════════════════════════════════════════ */
export default function DashboardPage() {
  const [activeFilter, setActiveFilter] = useState<(typeof TIME_FILTERS)[number]>('24H')

  return (
    <DashboardLayout>
      {/* ─── Page header ─── */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-text">
            Performance Analytics
          </h2>
          <p className="mt-1 text-sm text-muted">
            Real-time supply chain throughput and risk assessment.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            id="btn-live-stream"
            className="rounded-sm border border-neon px-4 py-1.5 text-[11px] font-bold tracking-widest text-neon transition-colors hover:bg-neon/10"
          >
            LIVE DATA STREAM
          </button>
          <button
            id="btn-export"
            className="rounded-sm border border-border bg-surface px-4 py-1.5 text-[11px] font-bold tracking-widest text-muted transition-colors hover:text-text"
          >
            ↓ EXPORT
          </button>
        </div>
      </div>

      {/* ─── Stat cards grid ─── */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard
          title="Throughput Efficiency"
          value="94.2%"
          delta="↑2.1%  vs last 24h"
          deltaPositive
          icon={<Gauge size={16} />}
        />
        <StatCard
          title="Active Nodes"
          value="1,402"
          delta="↑12  newly registered"
          deltaPositive
          icon={<Network size={16} />}
        />
        <StatCard
          title="Predictive Risk Score"
          value="4.2"
          delta="↑0.8  elevated tension"
          deltaPositive={false}
          variant="warning"
          icon={<AlertTriangle size={16} />}
        />
        <StatCard
          title="Capacity Utilization"
          value="87%"
          icon={<Circle size={16} />}
        >
          {/* Animated progress bar */}
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-border/40">
            <div
              className="h-full rounded-full bg-neon animate-bar-fill"
              style={{ width: '87%' }}
            />
          </div>
        </StatCard>
      </div>

      {/* ─── Bottom two-column grid ─── */}
      <div className="grid grid-cols-[1.85fr_1fr] gap-4">
        {/* ── LEFT: Throughput chart ── */}
        <div className="rounded-sm border border-border bg-surface p-5">
          {/* Chart header */}
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-[12px] font-semibold tracking-[0.15em] uppercase text-muted">
              Throughput Volume vs Demand
            </h3>

            {/* Time filter pills */}
            <div className="flex items-center gap-0.5 rounded-sm border border-border p-0.5">
              {TIME_FILTERS.map((f) => (
                <button
                  key={f}
                  onClick={() => setActiveFilter(f)}
                  className={cn(
                    'rounded-sm px-3 py-1 text-[10px] font-bold tracking-widest transition-colors duration-150',
                    activeFilter === f
                      ? 'bg-neon text-bg'
                      : 'text-muted hover:text-text'
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {/* Recharts bar chart */}
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={THROUGHPUT_DATA}
                margin={{ top: 8, right: 8, bottom: 0, left: -10 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="oklch(20% 0.04 142)"
                  strokeOpacity={0.2}
                  vertical={false}
                />
                <XAxis
                  dataKey="name"
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 10, fill: 'oklch(55% 0.02 142)' }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 10, fill: 'oklch(55% 0.02 142)' }}
                  tickFormatter={(v: number) =>
                    v >= 1000 ? `${Math.round(v / 1000)}k` : String(v)
                  }
                />
                <Tooltip
                  content={<ChartTooltip />}
                  cursor={{ fill: 'oklch(85% 0.35 142 / 5%)' }}
                />
                <Bar
                  dataKey="volume"
                  fill="oklch(85% 0.35 142)"
                  radius={[2, 2, 0, 0]}
                  maxBarSize={28}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── RIGHT: Predictive Bottlenecks ── */}
        <div className="rounded-sm border border-border bg-surface p-5">
          {/* Panel header */}
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-[12px] font-semibold tracking-[0.15em] uppercase text-muted">
              Predictive Bottlenecks
            </h3>
            <button
              aria-label="Filter bottlenecks"
              className="text-muted transition-colors hover:text-neon"
            >
              <Filter size={14} />
            </button>
          </div>

          {/* List with vertical fade mask */}
          <div
            className="space-y-0 overflow-y-auto max-h-[260px]"
            style={{
              maskImage:
                'linear-gradient(to bottom, transparent, black 10%, black 90%, transparent)',
              WebkitMaskImage:
                'linear-gradient(to bottom, transparent, black 10%, black 90%, transparent)',
            }}
          >
            {BOTTLENECKS.map((b, i) => (
              <div
                key={b.id}
                className={cn(
                  'py-4 px-2 -mx-2 rounded-sm animate-fade-in transition-colors duration-150 hover:bg-surface',
                  i !== BOTTLENECKS.length - 1 && 'border-b border-border'
                )}
                style={{ animationDelay: `${i * 100}ms` }}
              >
                {/* Top row: dot + name + badge */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        'h-2 w-2 rounded-full shrink-0',
                        b.severity === 'CRITICAL' ? 'bg-critical' : 'bg-warn'
                      )}
                    />
                    <span className="text-[12px] font-bold tracking-widest text-neon">
                      {b.name}
                    </span>
                  </div>
                  <SeverityBadge severity={b.severity} />
                </div>

                {/* Description */}
                <p className="text-[11px] leading-relaxed text-muted mb-2 pl-4">
                  {b.description}
                </p>

                {/* Bottom row: impact + action */}
                <div className="flex items-center justify-between pl-4">
                  <span className="text-[10px] tracking-widest text-muted/70">
                    {b.impact}
                  </span>
                  <button className="text-[10px] font-semibold tracking-widest text-neon transition-colors hover:text-neon-dim">
                    {b.action}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
