import { useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { Truck, TrendingDown, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { cn } from '@/lib/utils'

/* ── Carrier data ── */
const CARRIERS = [
  { id: 'maersk',      name: 'Maersk',      initials: 'MAE', health: 0.87, otp: 84, capacity: 0.76, activeShipments: 3, costIndex: 78, carbonIndex: 72, blackout: false, trend: 'up',   note: 'Reliable performance. Hamburg exposure monitored.' },
  { id: 'cma_cgm',     name: 'CMA CGM',     initials: 'CMA', health: 0.82, otp: 79, capacity: 0.71, activeShipments: 2, costIndex: 72, carbonIndex: 68, blackout: false, trend: 'stable', note: 'Minor OTP dip vs Q2. Capacity stable.' },
  { id: 'msc',         name: 'MSC',         initials: 'MSC', health: 0.75, otp: 73, capacity: 0.88, activeShipments: 3, costIndex: 65, carbonIndex: 70, blackout: false, trend: 'down', note: 'Capacity at 88% — surge pricing risk. Monitor.' },
  { id: 'hapag_lloyd', name: 'Hapag-Lloyd', initials: 'HPL', health: 0.58, otp: 67, capacity: 0.62, activeShipments: 2, costIndex: 80, carbonIndex: 64, blackout: true,  trend: 'down', note: 'OTP dropped 12% vs Q2. Soft blackout raised by BROKER.' },
  { id: 'one',         name: 'ONE',         initials: 'ONE', health: 0.91, otp: 89, capacity: 0.55, activeShipments: 3, costIndex: 74, carbonIndex: 76, blackout: false, trend: 'up',   note: 'Top performer. Recommended for premium SLA tiers.' },
  { id: 'express',     name: 'Express (DHL/FedEx)', initials: 'EXP', health: 0.96, otp: 97, capacity: 0.42, activeShipments: 2, costIndex: 20, carbonIndex: 15, blackout: false, trend: 'stable', note: 'High cost. High carbon. Use only for critical SLA breaches.' },
]

/* ── BROKER decision log ── */
const BROKER_LOG = [
  { ts: '14:24Z', severity: 'critical', msg: 'Soft blackout raised on hapag_lloyd — OTP -12% in 24h' },
  { ts: '14:22Z', severity: 'warn',     msg: 'MSC capacity alert: 88% utilization — surge pricing imminent' },
  { ts: '14:18Z', severity: 'info',     msg: 'Carrier switch recommended: SHP-014 hapag_lloyd → maersk' },
  { ts: '14:09Z', severity: 'info',     msg: 'ONE rated top carrier for platinum SLA tier this week' },
  { ts: '13:55Z', severity: 'warn',     msg: 'CMA CGM OTP trending down — watching for 5-day pattern' },
  { ts: '13:40Z', severity: 'info',     msg: 'Express carrier pool: 58% capacity available for emergency use' },
  { ts: '13:22Z', severity: 'info',     msg: 'Maersk fleet rerouted 3 vessels from Hamburg — smart adaptation' },
]

/* ── Comparison chart data ── */
const CHART_DATA = CARRIERS.map(c => ({
  name: c.initials,
  OTP: c.otp,
  Cost: c.costIndex,
  Carbon: c.carbonIndex,
}))

/* ── Health gauge (arc) ── */
function HealthGauge({ value }: { value: number }) {
  const pct = value * 100
  const color = pct > 80 ? '#5ed29c' : pct > 60 ? '#f5a623' : '#ef4444'
  const barW = pct
  return (
    <div className="relative mt-2 mb-1">
      <div className="h-1.5 w-full rounded-full bg-border overflow-hidden">
        <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${barW}%`, background: color }} />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-[8px] text-muted">0</span>
        <span className="text-[8px] font-bold font-mono" style={{ color }}>{pct.toFixed(0)}%</span>
        <span className="text-[8px] text-muted">100</span>
      </div>
    </div>
  )
}

/* ── Carrier card ── */
function CarrierCard({ c, selected, onClick }: { c: typeof CARRIERS[0]; selected: boolean; onClick: () => void }) {
  const borderColor = c.blackout ? 'border-critical/30' : selected ? 'border-neon/40' : 'border-border'
  return (
    <button onClick={onClick} className={cn('bg-surface border rounded-lg p-4 text-left hover:border-neon/20 transition-all w-full', borderColor)}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={cn('h-8 w-8 rounded flex items-center justify-center text-[10px] font-bold', c.blackout ? 'bg-critical/15 text-critical' : 'bg-neon/10 text-neon')}>
            {c.initials}
          </div>
          <div>
            <p className="text-[12px] font-bold text-text">{c.name}</p>
            <div className="flex items-center gap-1 mt-0.5">
              {c.blackout ? (
                <span className="text-[8px] font-bold text-critical border border-critical/30 px-1.5 py-0.5 rounded">SOFT BLACKOUT</span>
              ) : (
                <span className="text-[8px] font-bold text-neon/60">{c.activeShipments} active shipments</span>
              )}
            </div>
          </div>
        </div>
        <div className="text-right">
          {c.trend === 'up' ? <TrendingUp size={14} className="text-neon" /> : c.trend === 'down' ? <TrendingDown size={14} className="text-critical" /> : <span className="text-[10px] text-muted">—</span>}
        </div>
      </div>

      <p className="text-[9px] text-muted/60 mb-1">Composite Health</p>
      <HealthGauge value={c.health} />

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2">
        <div className="flex justify-between text-[9px]"><span className="text-muted">OTP</span><span className={cn('font-mono font-bold', c.otp > 80 ? 'text-neon' : c.otp > 70 ? 'text-warn' : 'text-critical')}>{c.otp}%</span></div>
        <div className="flex justify-between text-[9px]"><span className="text-muted">Capacity</span><span className={cn('font-mono font-bold', c.capacity > 0.85 ? 'text-warn' : 'text-text')}>{Math.round(c.capacity * 100)}%</span></div>
      </div>
    </button>
  )
}

/* ══════ PAGE ══════ */
export default function FleetPage() {
  const [selectedCarrier, setSelectedCarrier] = useState<string | null>(null)
  const selected = CARRIERS.find(c => c.id === selectedCarrier)

  const healthyCount = CARRIERS.filter(c => c.health > 0.8 && !c.blackout).length
  const warningCount = CARRIERS.filter(c => c.health <= 0.8 && c.health > 0.6).length
  const blackoutCount = CARRIERS.filter(c => c.blackout).length
  const avgOtp = Math.round(CARRIERS.reduce((a, c) => a + c.otp, 0) / CARRIERS.length)

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Truck size={16} className="text-neon" />
            <h2 className="font-display text-2xl font-bold tracking-wider text-text">Fleet & Carriers</h2>
          </div>
          <p className="text-[11px] tracking-widest text-muted">BROKER Agent — Carrier health monitoring, OTP tracking & blackout management</p>
        </div>
      </div>

      {/* KPI bar */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: 'Healthy Carriers', value: healthyCount, color: 'text-neon', icon: <CheckCircle size={13} className="text-neon" /> },
          { label: 'Watchlist', value: warningCount, color: 'text-warn', icon: <AlertTriangle size={13} className="text-warn" /> },
          { label: 'Soft Blackout', value: blackoutCount, color: 'text-critical', icon: <AlertTriangle size={13} className="text-critical" /> },
          { label: 'Avg OTP', value: `${avgOtp}%`, color: avgOtp > 80 ? 'text-neon' : 'text-warn', icon: <TrendingUp size={13} className="text-neon" /> },
        ].map(k => (
          <div key={k.label} className="bg-surface border border-border rounded-lg p-4 flex items-start gap-3">
            {k.icon}
            <div>
              <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60">{k.label}</p>
              <p className={cn('font-mono text-2xl font-bold', k.color)}>{k.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Carrier grid */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {CARRIERS.map(c => (
          <CarrierCard
            key={c.id} c={c}
            selected={selectedCarrier === c.id}
            onClick={() => setSelectedCarrier(selectedCarrier === c.id ? null : c.id)}
          />
        ))}
      </div>

      {/* Detail + charts */}
      <div className="grid grid-cols-[1fr_300px] gap-4">
        {/* Comparison chart */}
        <div className="bg-surface border border-border rounded-lg p-4">
          <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-4">Carrier Performance Comparison</p>
          <div className="h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={CHART_DATA} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="oklch(20% 0.04 142)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 9, fill: 'oklch(55% 0.02 142)' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 8, fill: 'oklch(55% 0.02 142)' }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: 'oklch(11% 0.015 142)', border: '1px solid oklch(20% 0.04 142)', borderRadius: 4, fontSize: 10 }} />
                <Bar dataKey="OTP" fill="#5ed29c" radius={[2,2,0,0]} />
                <Bar dataKey="Cost" fill="rgba(245,166,35,0.7)" radius={[2,2,0,0]} />
                <Bar dataKey="Carbon" fill="rgba(94,210,156,0.35)" radius={[2,2,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center gap-4 mt-2">
            <div className="flex items-center gap-1.5"><div className="h-2 w-2 rounded-sm bg-neon" /><span className="text-[8px] text-muted">OTP Score</span></div>
            <div className="flex items-center gap-1.5"><div className="h-2 w-2 rounded-sm bg-warn/70" /><span className="text-[8px] text-muted">Cost Index</span></div>
            <div className="flex items-center gap-1.5"><div className="h-2 w-2 rounded-sm bg-neon/35" /><span className="text-[8px] text-muted">Carbon Index</span></div>
          </div>
          {selected && (
            <div className="mt-4 p-3 rounded border border-neon/15 bg-neon/3">
              <p className="text-[9px] font-bold text-neon tracking-widest mb-1">BROKER NOTE · {selected.name.toUpperCase()}</p>
              <p className="text-[10px] text-text/70">{selected.note}</p>
            </div>
          )}
        </div>

        {/* BROKER log */}
        <div className="bg-surface border border-border rounded-lg overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
            <Truck size={12} className="text-neon" />
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-text">BROKER Decision Log</span>
            <span className="h-1.5 w-1.5 rounded-full bg-neon animate-pulse ml-auto" />
          </div>
          <div className="overflow-y-auto">
            {BROKER_LOG.map((e, i) => (
              <div key={i} className="flex gap-2 px-4 py-2.5 border-b border-border/40 last:border-0 hover:bg-neon/2 transition-colors">
                <div className={cn('h-1.5 w-1.5 rounded-full mt-1.5 shrink-0', e.severity === 'critical' ? 'bg-critical' : e.severity === 'warn' ? 'bg-warn' : 'bg-neon/40')} />
                <div>
                  <p className="text-[8px] text-muted mb-0.5">{e.ts}</p>
                  <p className={cn('text-[10px] leading-relaxed', e.severity === 'critical' ? 'text-critical' : e.severity === 'warn' ? 'text-warn' : 'text-text/70')}>{e.msg}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
