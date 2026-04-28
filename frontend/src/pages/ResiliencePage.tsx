import { useState } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { INITIAL_NODES } from '@/lib/networkData'
import { Network, Shield, Package, Clock, ChevronRight, ArrowRight } from 'lucide-react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts'
import { cn } from '@/lib/utils'

/* ── GUARDIAN history per node ── */
const GUARDIAN_HISTORY: Record<string, string[]> = {
  hamburg_port: ['14:22Z Circuit OPENED — health 0.28 < threshold 0.30', '14:18Z Risk score escalated by SENTINEL: 0.42 → HIGH', '14:10Z Weather severity updated: 2.5 → 8.0'],
  rotterdam_port: ['12:05Z Circuit probed HALF-OPEN — health recovering', '11:40Z Health dipped to 0.71 — monitoring started', '10:22Z All clear — circuit CLOSED'],
  la_port: ['13:30Z Congestion alert raised — queue depth 18 (avg 8)', '13:00Z GUARDIAN threshold check: health 0.84 — OK'],
  mumbai_hub: ['14:00Z Monsoon season flag active — weather 3.0/10', '13:45Z Health score: 0.82 — WATCHLIST'],
}

/* ── STOCKPILE transfers ── */
const TRANSFERS = [
  { id: 'T-001', from: 'rotterdam_port', to: 'frankfurt_dc', units: 2400, sku: 'ELEC-SKU-882', trigger: 'Hamburg disruption — downstream DC starvation risk', stockoutBefore: 78, stockoutAfter: 12, status: 'active' },
  { id: 'T-002', from: 'tokyo_hub', to: 'seoul_hub', units: 850, sku: 'SEMI-SKU-441', trigger: 'Seoul buffer pre-positioning — SLA tier 1 protection', stockoutBefore: 35, stockoutAfter: 8, status: 'active' },
  { id: 'T-003', from: 'singapore_port', to: 'mumbai_hub', units: 1200, sku: 'PHARM-SKU-219', trigger: 'Monsoon season pre-positioning — 30-day forward hedge', stockoutBefore: 55, stockoutAfter: 14, status: 'pending' },
]

/* ── Recovery timeline ── */
const RECOVERY_DATA = [
  { event: 'LA Congestion', duration: 4.2, severity: 'warn', agents: 'GUARDIAN + NAVIGATOR' },
  { event: 'Mumbai Weather', duration: 6.8, severity: 'warn', agents: 'SENTINEL + STOCKPILE' },
  { event: 'Red Sea Lane', duration: 11.5, severity: 'critical', agents: 'ALL 6 AGENTS' },
  { event: 'Seoul Probe', duration: 2.1, severity: 'info', agents: 'GUARDIAN' },
  { event: 'Rotterdam Dip', duration: 3.4, severity: 'warn', agents: 'GUARDIAN + BROKER' },
]

/* ── Node circuit card ── */
function CircuitCard({ node, selected, onClick }: { node: typeof INITIAL_NODES[0]; selected: boolean; onClick: () => void }) {
  const cs = node.circuit_state
  const csColor = cs === 'open' ? 'text-critical' : cs === 'half_open' ? 'text-warn' : 'text-neon'
  const csBg = cs === 'open' ? 'bg-critical/5 border-critical/30' : cs === 'half_open' ? 'bg-warn/5 border-warn/30' : 'bg-surface border-border'
  const h = Math.round(node.health_score * 100)
  const barColor = node.health_score > 0.8 ? 'bg-neon' : node.health_score > 0.5 ? 'bg-warn' : 'bg-critical'

  return (
    <button onClick={onClick} className={cn('rounded-lg border p-3 text-left hover:border-neon/20 transition-all w-full', csBg, selected && 'ring-1 ring-neon/30')}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <p className="text-[10px] font-bold text-text leading-tight">
            {node.name.replace('Port of ', '').replace(' Distribution Center', '').replace(' Logistics Hub', '')}
          </p>
          <p className="text-[8px] text-muted uppercase">{node.type} · {node.country}</p>
        </div>
        <span className={cn('text-[8px] font-bold tracking-widest', csColor)}>
          {cs === 'closed' ? 'OK' : cs === 'half_open' ? 'PROBE' : 'OPEN'}
        </span>
      </div>
      <div className="h-1 w-full rounded-full bg-border overflow-hidden mb-1">
        <div className={cn('h-full rounded-full', barColor)} style={{ width: `${h}%` }} />
      </div>
      <div className="flex justify-between text-[8px]">
        <span className="text-muted">Health</span>
        <span className={cn('font-mono font-bold', csColor)}>{h}%</span>
      </div>
    </button>
  )
}

/* ══════ PAGE ══════ */
export default function ResiliencePage() {
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const node = INITIAL_NODES.find(n => n.id === selectedNode)

  const online = INITIAL_NODES.filter(n => n.circuit_state === 'closed').length
  const open = INITIAL_NODES.filter(n => n.circuit_state === 'open').length
  const avgRecovery = (RECOVERY_DATA.reduce((a, r) => a + r.duration, 0) / RECOVERY_DATA.length).toFixed(1)

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Network size={16} className="text-neon" />
            <h2 className="font-display text-2xl font-bold tracking-wider text-text">Network Resilience</h2>
          </div>
          <p className="text-[11px] tracking-widest text-muted">GUARDIAN · STOCKPILE — Circuit breaker states, inventory pre-positioning & recovery analysis</p>
        </div>
      </div>

      {/* KPI bar */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: 'Nodes Online', value: `${online}/15`, color: 'text-neon' },
          { label: 'Circuit Breakers Open', value: open, color: open > 0 ? 'text-critical' : 'text-neon' },
          { label: 'Inventory Transfers', value: TRANSFERS.filter(t => t.status === 'active').length, color: 'text-neon' },
          { label: 'Avg Recovery (h)', value: avgRecovery, color: 'text-text' },
        ].map(k => (
          <div key={k.label} className="bg-surface border border-border rounded-lg p-4">
            <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-1">{k.label}</p>
            <p className={cn('font-mono text-2xl font-bold', k.color)}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-[1fr_320px] gap-4 mb-4">

        {/* Circuit breaker board */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Shield size={13} className="text-neon" />
            <span className="text-[11px] font-bold tracking-[0.15em] uppercase text-text">GUARDIAN Circuit Breaker Status</span>
          </div>
          <div className="grid grid-cols-3 gap-2 mb-4">
            {INITIAL_NODES.map(n => (
              <CircuitCard key={n.id} node={n} selected={selectedNode === n.id} onClick={() => setSelectedNode(selectedNode === n.id ? null : n.id)} />
            ))}
          </div>

          {/* Node history panel */}
          {node && (
            <div className="bg-surface border border-border rounded-lg overflow-hidden animate-fade-in">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
                <div className="flex items-center gap-2">
                  <Shield size={12} className="text-neon" />
                  <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-text">GUARDIAN History — {node.name}</span>
                </div>
                <button onClick={() => setSelectedNode(null)} className="text-muted hover:text-text text-xs">×</button>
              </div>
              <div className="p-4 space-y-2">
                {(GUARDIAN_HISTORY[node.id] ?? ['No recent events for this node.']).map((e, i) => (
                  <div key={i} className="flex gap-2 text-[10px]">
                    <ChevronRight size={10} className="text-neon/40 shrink-0 mt-0.5" />
                    <p className="text-text/70">{e}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: STOCKPILE panel */}
        <div className="flex flex-col gap-4">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Package size={13} className="text-neon" />
              <span className="text-[11px] font-bold tracking-[0.15em] uppercase text-text">STOCKPILE — Pre-Positioning</span>
            </div>
            <div className="space-y-3">
              {TRANSFERS.map(t => (
                <div key={t.id} className={cn('bg-surface border rounded-lg p-3', t.status === 'active' ? 'border-neon/20' : 'border-border')}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[9px] font-bold text-neon">{t.id}</span>
                    <span className={cn('text-[8px] font-bold tracking-widest px-1.5 py-0.5 rounded border', t.status === 'active' ? 'border-neon/30 text-neon bg-neon/5' : 'border-border text-muted')}>
                      {t.status.toUpperCase()}
                    </span>
                  </div>
                  {/* Flow */}
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[9px] text-text font-bold">{t.from.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
                    <ArrowRight size={10} className="text-neon shrink-0" />
                    <span className="text-[9px] text-text font-bold">{t.to.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
                  </div>
                  <p className="text-[9px] text-muted mb-2">{t.units.toLocaleString()} units · {t.sku}</p>
                  {/* Stockout reduction */}
                  <div className="flex items-center gap-2 text-[9px]">
                    <span className="text-critical font-mono">{t.stockoutBefore}%</span>
                    <ArrowRight size={8} className="text-muted" />
                    <span className="text-neon font-mono">{t.stockoutAfter}%</span>
                    <span className="text-muted ml-1">stockout probability</span>
                  </div>
                  <p className="text-[8px] text-muted/60 mt-1 leading-relaxed">{t.trigger}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Recovery timeline */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <div className="flex items-center gap-2 mb-4">
          <Clock size={13} className="text-neon" />
          <span className="text-[11px] font-bold tracking-[0.15em] uppercase text-text">Disruption Recovery Timeline</span>
          <span className="text-[8px] text-muted ml-2">Hours from detection to resolution</span>
        </div>
        <div className="h-[140px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={RECOVERY_DATA} margin={{ top: 0, right: 16, bottom: 0, left: -20 }} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 8, fill: 'oklch(55% 0.02 142)' }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="event" tick={{ fontSize: 9, fill: 'oklch(55% 0.02 142)' }} axisLine={false} tickLine={false} width={90} />
              <Tooltip contentStyle={{ background: 'oklch(11% 0.015 142)', border: '1px solid oklch(20% 0.04 142)', borderRadius: 4, fontSize: 10 }}
                formatter={(v) => [`${v}h`, 'Recovery Time']} />
              <Bar dataKey="duration" radius={[0, 3, 3, 0]}>
                {RECOVERY_DATA.map((r, i) => (
                  <Cell key={i} fill={r.severity === 'critical' ? '#ef4444' : r.severity === 'warn' ? '#f5a623' : '#5ed29c'} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="grid grid-cols-5 gap-2 mt-2">
          {RECOVERY_DATA.map(r => (
            <div key={r.event} className="text-center">
              <p className="text-[8px] text-muted/60 truncate">{r.agents}</p>
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}
