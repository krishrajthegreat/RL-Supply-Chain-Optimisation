import { useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import StatCard from '@/components/ui/StatCard'
import {
  Package,
  AlertTriangle,
  DollarSign,
  TrendingUp,
  Filter,
  Navigation,
  ArrowRight,
  Shield,
  Truck,
  BarChart2,
  Clock,
} from 'lucide-react'
import {
  AreaChart,
  Area,
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
   CHART DATA
   ══════════════════════════════════════════════════════════ */

// SENTINEL — 24h risk score timeline
const RISK_TIMELINE = [
  { t: '12AM', risk: 38 },
  { t: '2AM',  risk: 35 },
  { t: '4AM',  risk: 42 },
  { t: '6AM',  risk: 58 },
  { t: '8AM',  risk: 72 },
  { t: '10AM', risk: 65 },
  { t: '12PM', risk: 54 },
  { t: '2PM',  risk: 49 },
  { t: '4PM',  risk: 61 },
  { t: '6PM',  risk: 55 },
  { t: '8PM',  risk: 48 },
  { t: '10PM', risk: 44 },
]

// BROKER — carrier health scores
const CARRIER_HEALTH = [
  { name: 'Maersk',  score: 91 },
  { name: 'MSC',     score: 78 },
  { name: 'CMA CGM', score: 84 },
  { name: 'Evergreen',score: 62 },
  { name: 'Hapag',   score: 88 },
]

/* ══════════════════════════════════════════════════════════
   GUARDIAN ALERTS
   ══════════════════════════════════════════════════════════ */
type AlertSeverity = 'HIGH' | 'MEDIUM' | 'LOW'

interface GuardianAlert {
  id: string
  type: string
  severity: AlertSeverity
  desc: string
  affected: number
  agent: string
}

const GUARDIAN_ALERTS: GuardianAlert[] = [
  {
    id: 'a1',
    type: 'Port Congestion',
    severity: 'HIGH',
    desc: 'Shanghai port throughput down 34% — 8 active shipments rerouting.',
    affected: 8,
    agent: 'GUARDIAN',
  },
  {
    id: 'a2',
    type: 'Severe Weather Warning',
    severity: 'HIGH',
    desc: 'Typhoon track intersects Rotterdam–Dubai lane. T-minus 14h.',
    affected: 5,
    agent: 'SENTINEL',
  },
  {
    id: 'a3',
    type: 'Carrier Blackout',
    severity: 'MEDIUM',
    desc: 'Evergreen capacity suspended on Trans-Pacific eastbound.',
    affected: 4,
    agent: 'BROKER',
  },
  {
    id: 'a4',
    type: 'Customs Delay',
    severity: 'MEDIUM',
    desc: 'HUB_EU_WEST clearance latency +6h due to documentation backlog.',
    affected: 3,
    agent: 'GUARDIAN',
  },
]

/* ══════════════════════════════════════════════════════════
   STOCKPILE PRE-POSITION SIGNALS
   ══════════════════════════════════════════════════════════ */
const PREPOSITION_SIGNALS = [
  { node: 'Singapore Hub',    action: 'Pre-position +420 units', confidence: 88, urgency: 'HIGH' },
  { node: 'Dubai Gateway',    action: 'Pre-position +180 units', confidence: 74, urgency: 'MEDIUM' },
  { node: 'Hamburg Port',     action: 'Hold — monitor 6h',       confidence: 61, urgency: 'LOW' },
]

/* ══════════════════════════════════════════════════════════
   SHARED HELPERS
   ══════════════════════════════════════════════════════════ */
const NEON = '#5ed29c'
const MUTED_TICK = 'rgba(94,210,156,0.35)'

function PanelHeader({ label, agent, children }: { label: string; agent?: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex items-center gap-2">
        <h3 className="text-[11px] font-bold tracking-[0.18em] uppercase text-muted">{label}</h3>
        {agent && (
          <span className="text-[9px] font-bold tracking-widest uppercase px-1.5 py-0.5 rounded border border-neon/25 text-neon/60">
            {agent}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}

function AlertBadge({ severity }: { severity: AlertSeverity }) {
  const styles: Record<AlertSeverity, string> = {
    HIGH:   'bg-critical/15 text-critical border-critical/30',
    MEDIUM: 'bg-warn/15 text-warn border-warn/30',
    LOW:    'bg-neon/10 text-neon border-neon/20',
  }
  return (
    <span className={cn('text-[9px] font-bold tracking-widest uppercase px-2 py-0.5 rounded border', styles[severity])}>
      {severity}
    </span>
  )
}

function UrgencyDot({ urgency }: { urgency: string }) {
  const color = urgency === 'HIGH' ? 'bg-critical' : urgency === 'MEDIUM' ? 'bg-warn' : 'bg-neon/50'
  return <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', color)} />
}

function RiskTooltip({ active, payload, label }: { active?: boolean; payload?: {value:number}[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-border bg-bg px-3 py-2 shadow-xl text-[10px]">
      <p className="text-muted tracking-widest">{label}</p>
      <p className="font-bold text-neon mt-0.5">Risk: {payload[0].value}</p>
    </div>
  )
}

function BarTooltipCarrier({ active, payload, label }: { active?: boolean; payload?: {value:number}[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-border bg-bg px-3 py-2 shadow-xl text-[10px]">
      <p className="text-muted tracking-widest">{label}</p>
      <p className="font-bold text-neon mt-0.5">Score: {payload[0].value}</p>
    </div>
  )
}

const TIME_FILTERS = ['6H', '24H', '7D'] as const

/* ══════════════════════════════════════════════════════════
   PAGE
   ══════════════════════════════════════════════════════════ */
export default function DashboardPage() {
  const [riskFilter, setRiskFilter] = useState<(typeof TIME_FILTERS)[number]>('24H')

  return (
    <DashboardLayout>
      {/* ─── Page header ─── */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-text">Control Tower</h2>
          <p className="mt-1 text-[11px] tracking-wide text-muted">
            Live situational awareness · 6 agents active · last sync 2s ago
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            id="btn-live-stream"
            className="flex items-center gap-2 rounded-full border border-neon/40 px-4 py-1.5 text-[10px] font-bold tracking-widest text-neon transition-all hover:bg-neon/8"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-neon animate-pulse" />
            LIVE
          </button>
          <button
            id="btn-export"
            className="rounded-full border border-border px-4 py-1.5 text-[10px] font-bold tracking-widest text-muted transition-colors hover:text-text"
          >
            ↓ EXPORT
          </button>
        </div>
      </div>

      {/* ─── Row 1: Stat cards ─── */}
      <div className="grid grid-cols-4 gap-4 mb-5">
        <StatCard
          title="Active Shipments"
          value="1,402"
          delta="↑12 vs yesterday"
          deltaPositive
          icon={<Package size={15} />}
        />
        <StatCard
          title="SENTINEL Threat Score"
          value="4.2"
          delta="↑0.8 elevated tension"
          deltaPositive={false}
          variant="warning"
          icon={<AlertTriangle size={15} />}
        />
        <StatCard
          title="Value At Risk"
          value="$2.1M"
          delta="↑$0.4M vs yesterday"
          deltaPositive={false}
          icon={<DollarSign size={15} />}
        />
        <StatCard
          title="On-Time Rate"
          value="94.2%"
          delta="↑2.1% vs last 24h"
          deltaPositive
          icon={<TrendingUp size={15} />}
        >
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-border/40">
            <div className="h-full rounded-full bg-neon animate-bar-fill" style={{ width: '94.2%' }} />
          </div>
        </StatCard>
      </div>

      {/* ─── Row 2: Risk Timeline + Guardian Alerts ─── */}
      <div className="grid grid-cols-[1.4fr_1fr] gap-4 mb-4">

        {/* SENTINEL Risk Timeline */}
        <div className="rounded-md border border-border bg-surface p-5">
          <PanelHeader label="Risk Timeline" agent="SENTINEL">
            <div className="flex items-center gap-0.5 rounded-md border border-border p-0.5">
              {TIME_FILTERS.map((f) => (
                <button
                  key={f}
                  onClick={() => setRiskFilter(f)}
                  className={cn(
                    'rounded px-3 py-1 text-[9px] font-bold tracking-widest transition-colors duration-150',
                    riskFilter === f ? 'bg-neon text-bg' : 'text-muted hover:text-text'
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </PanelHeader>

          {/* Current risk callout */}
          <div className="flex items-baseline gap-3 mb-3">
            <span className="text-2xl font-bold font-mono text-text">65</span>
            <span className="text-[10px] text-muted tracking-wide">Current Risk Score</span>
            <span className="ml-auto text-[10px] font-bold text-critical">↑ Elevated</span>
          </div>

          <div className="h-[180px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={RISK_TIMELINE} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
                <defs>
                  <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={NEON} stopOpacity={0.25} />
                    <stop offset="100%" stopColor={NEON} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="2 4" stroke={MUTED_TICK} strokeOpacity={0.3} vertical={false} />
                <XAxis dataKey="t" axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: MUTED_TICK }} />
                <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: MUTED_TICK }} />
                <Tooltip content={<RiskTooltip />} />
                <Area
                  type="monotone"
                  dataKey="risk"
                  stroke={NEON}
                  strokeWidth={2}
                  fill="url(#riskGrad)"
                  dot={false}
                  activeDot={{ r: 4, fill: NEON, stroke: '#070b0a', strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* GUARDIAN Active Alerts */}
        <div className="rounded-md border border-border bg-surface p-5">
          <PanelHeader label="Active Alerts" agent="GUARDIAN">
            <button className="text-muted hover:text-neon transition-colors">
              <Filter size={13} />
            </button>
          </PanelHeader>

          <div className="space-y-0">
            {GUARDIAN_ALERTS.map((a, i) => (
              <div
                key={a.id}
                className={cn(
                  'py-3 animate-fade-in',
                  i !== GUARDIAN_ALERTS.length - 1 && 'border-b border-border'
                )}
                style={{ animationDelay: `${i * 80}ms` }}
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2">
                    <UrgencyDot urgency={a.severity} />
                    <span className="text-[11px] font-bold text-text tracking-wide">{a.type}</span>
                  </div>
                  <AlertBadge severity={a.severity} />
                </div>
                <p className="text-[10px] text-muted leading-relaxed pl-3.5 mb-1">{a.desc}</p>
                <div className="flex items-center justify-between pl-3.5">
                  <span className="text-[9px] tracking-widest text-muted/60 uppercase">{a.agent} · {a.affected} shipments</span>
                  <button className="text-[9px] font-bold text-neon hover:text-neon/70 tracking-widest transition-colors">
                    Resolve →
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ─── Row 3: Navigator Recommendation + Stockpile Signals + Broker Carrier Health ─── */}
      <div className="grid grid-cols-3 gap-4">

        {/* NAVIGATOR Recommended Action */}
        <div className="rounded-md border border-neon/20 bg-surface p-5" style={{ boxShadow: '0 0 24px rgba(94,210,156,0.04)' }}>
          {/* Impact badge */}
          <div className="flex items-center justify-between mb-3">
            <span className="text-[9px] font-bold tracking-widest uppercase px-2.5 py-1 rounded-full bg-neon text-bg">
              High Impact
            </span>
            <span className="text-[9px] text-muted tracking-widest uppercase flex items-center gap-1">
              <Navigation size={10} className="text-neon" />
              NAVIGATOR
            </span>
          </div>

          <p className="text-[10px] text-muted tracking-widest uppercase mb-0.5">Recommended Action</p>
          <h3 className="font-display text-lg font-bold text-text mb-1">Reroute</h3>
          <p className="text-[11px] text-muted leading-relaxed mb-4">
            Reroute SHP-900 via Indian Ocean corridor to reduce risk from{' '}
            <span className="text-critical font-bold">100</span>{' → '}
            <span className="text-neon font-bold">75</span>
          </p>

          {/* Metrics */}
          <div className="space-y-2 border-t border-border pt-3 mb-4">
            {[
              { icon: Shield,  label: 'Risk Score',   value: '100 → 75', valueClass: 'text-neon' },
              { icon: Clock,   label: 'ETA Impact',    value: '+4 hrs',   valueClass: 'text-warn' },
              { icon: DollarSign, label: 'Cost Impact', value: '+$1,350', valueClass: 'text-warn' },
            ].map(({ icon: Icon, label, value, valueClass }) => (
              <div key={label} className="flex items-center justify-between text-[10px]">
                <span className="flex items-center gap-1.5 text-muted">
                  <Icon size={10} className="text-muted/60" />
                  {label}
                </span>
                <span className={cn('font-bold tracking-wide', valueClass)}>{value}</span>
              </div>
            ))}
            <div className="flex items-center justify-between text-[10px]">
              <span className="text-muted">Confidence</span>
              <div className="flex items-center gap-2">
                <div className="h-1 w-16 rounded-full bg-border overflow-hidden">
                  <div className="h-full rounded-full bg-neon" style={{ width: '78%' }} />
                </div>
                <span className="font-bold text-neon">78%</span>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button className="flex-1 rounded-md border border-border py-2 text-[10px] font-bold tracking-widest text-muted hover:border-neon/30 hover:text-text transition-all">
              View Options
            </button>
            <button className="flex-1 rounded-md bg-neon py-2 text-[10px] font-bold tracking-widest text-bg hover:opacity-90 transition-opacity flex items-center justify-center gap-1.5">
              Lock In <ArrowRight size={10} />
            </button>
          </div>
        </div>

        {/* STOCKPILE Pre-Position Signals */}
        <div className="rounded-md border border-border bg-surface p-5">
          <PanelHeader label="Pre-Position Signals" agent="STOCKPILE" />

          <div className="space-y-3">
            {PREPOSITION_SIGNALS.map((s, i) => (
              <div
                key={s.node}
                className={cn(
                  'rounded-md border p-3 animate-fade-in transition-all hover:border-neon/25',
                  s.urgency === 'HIGH' ? 'border-critical/20 bg-critical/3' : 'border-border bg-bg/40'
                )}
                style={{ animationDelay: `${i * 100}ms` }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[11px] font-bold text-text">{s.node}</span>
                  <span className={cn(
                    'text-[8px] font-bold tracking-widest uppercase px-1.5 py-0.5 rounded border',
                    s.urgency === 'HIGH' ? 'text-critical border-critical/30 bg-critical/10' :
                    s.urgency === 'MEDIUM' ? 'text-warn border-warn/30 bg-warn/10' :
                    'text-muted border-border'
                  )}>
                    {s.urgency}
                  </span>
                </div>
                <p className="text-[10px] text-muted mb-2">{s.action}</p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1 rounded-full bg-border overflow-hidden">
                    <div
                      className={cn('h-full rounded-full', s.confidence > 80 ? 'bg-neon' : s.confidence > 65 ? 'bg-warn' : 'bg-muted')}
                      style={{ width: `${s.confidence}%` }}
                    />
                  </div>
                  <span className="text-[9px] font-bold text-muted shrink-0">{s.confidence}%</span>
                </div>
              </div>
            ))}
          </div>

          <button className="mt-4 w-full rounded-md border border-border py-2 text-[10px] font-bold tracking-widest text-muted hover:border-neon/30 hover:text-neon transition-all">
            View All Signals →
          </button>
        </div>

        {/* BROKER Carrier Health */}
        <div className="rounded-md border border-border bg-surface p-5">
          <PanelHeader label="Carrier Health Scores" agent="BROKER">
            <span className="flex items-center gap-1 text-[9px] text-muted tracking-widest">
              <Truck size={10} />
              5 carriers
            </span>
          </PanelHeader>

          <div className="h-[160px] w-full mb-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={CARRIER_HEALTH} margin={{ top: 4, right: 0, bottom: 0, left: -20 }} barSize={16}>
                <CartesianGrid strokeDasharray="2 4" stroke={MUTED_TICK} strokeOpacity={0.3} vertical={false} />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 8, fill: MUTED_TICK }} />
                <YAxis domain={[0, 100]} axisLine={false} tickLine={false} tick={{ fontSize: 8, fill: MUTED_TICK }} />
                <Tooltip content={<BarTooltipCarrier />} />
                <Bar
                  dataKey="score"
                  radius={[3, 3, 0, 0]}
                  fill={NEON}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-2 border-t border-border pt-3">
            {CARRIER_HEALTH.map((c) => (
              <div key={c.name} className="flex items-center justify-between text-[10px]">
                <span className="text-muted">{c.name}</span>
                <div className="flex items-center gap-2">
                  <div className="h-1 w-20 rounded-full bg-border overflow-hidden">
                    <div
                      className={cn('h-full rounded-full', c.score >= 80 ? 'bg-neon' : c.score >= 65 ? 'bg-warn' : 'bg-critical')}
                      style={{ width: `${c.score}%` }}
                    />
                  </div>
                  <span className={cn('font-bold w-6 text-right', c.score >= 80 ? 'text-neon' : c.score >= 65 ? 'text-warn' : 'text-critical')}>
                    {c.score}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <button className="mt-4 w-full rounded-md border border-border py-2 text-[10px] font-bold tracking-widest text-muted hover:border-neon/30 hover:text-neon transition-all flex items-center justify-center gap-1.5">
            <BarChart2 size={10} />
            Full Carrier Report →
          </button>
        </div>
      </div>

      {/* ─── Row 4: Throughput + Herald ─── */}
      <div className="grid grid-cols-[1.6fr_1fr] gap-4 mt-4">

        {/* Throughput bar chart (kept from original) */}
        <div className="rounded-md border border-border bg-surface p-5">
          <PanelHeader label="Throughput Volume · 12 Months" />
          <div className="h-[180px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={[
                  { name: 'Jan', volume: 72000 }, { name: 'Feb', volume: 55000 },
                  { name: 'Mar', volume: 91000 }, { name: 'Apr', volume: 43000 },
                  { name: 'May', volume: 68000 }, { name: 'Jun', volume: 82000 },
                  { name: 'Jul', volume: 95000 }, { name: 'Aug', volume: 37000 },
                  { name: 'Sep', volume: 78000 }, { name: 'Oct', volume: 61000 },
                  { name: 'Nov', volume: 85000 }, { name: 'Dec', volume: 50000 },
                ]}
                margin={{ top: 4, right: 4, bottom: 0, left: -10 }}
              >
                <CartesianGrid strokeDasharray="2 4" stroke={MUTED_TICK} strokeOpacity={0.25} vertical={false} />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: MUTED_TICK }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 9, fill: MUTED_TICK }}
                  tickFormatter={(v: number) => v >= 1000 ? `${Math.round(v / 1000)}k` : String(v)} />
                <Tooltip content={<BarTooltipCarrier />} />
                <Bar dataKey="volume" fill={NEON} radius={[2, 2, 0, 0]} maxBarSize={24} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* HERALD — Stakeholder Communication Status */}
        <div className="rounded-md border border-border bg-surface p-5">
          <PanelHeader label="Comms Status" agent="HERALD" />

          <div className="space-y-3">
            {[
              { party: 'Procurement Team',    msg: 'Singapore pre-position alert sent', status: 'DELIVERED', time: '2m ago' },
              { party: 'Logistics Ops',       msg: 'SHP-900 reroute notification',       status: 'READ',      time: '5m ago' },
              { party: 'Finance Controller',  msg: 'Cost impact report: +$1,350',        status: 'PENDING',   time: '8m ago' },
              { party: 'Executive Briefing',  msg: 'Weekly risk digest queued',           status: 'SCHEDULED', time: '1h ago' },
            ].map((c, i) => (
              <div key={i} className="flex items-start justify-between gap-3 py-2.5 border-b border-border last:border-0">
                <div className="min-w-0">
                  <p className="text-[11px] font-bold text-text truncate">{c.party}</p>
                  <p className="text-[10px] text-muted truncate mt-0.5">{c.msg}</p>
                </div>
                <div className="shrink-0 text-right">
                  <span className={cn(
                    'text-[8px] font-bold tracking-widest uppercase',
                    c.status === 'DELIVERED' ? 'text-neon' :
                    c.status === 'READ' ? 'text-neon/60' :
                    c.status === 'PENDING' ? 'text-warn' : 'text-muted'
                  )}>
                    {c.status}
                  </span>
                  <p className="text-[9px] text-muted/50 mt-0.5">{c.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

    </DashboardLayout>
  )
}
