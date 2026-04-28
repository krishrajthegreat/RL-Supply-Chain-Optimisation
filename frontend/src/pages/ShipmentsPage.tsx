import { useState, useMemo } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { INITIAL_SHIPMENTS, INITIAL_NODES, type Shipment, type NetworkNode } from '@/lib/networkData'
import { PackageSearch, ChevronDown, ChevronUp, DollarSign, Leaf, Clock, Filter, TrendingUp } from 'lucide-react'
import { cn } from '@/lib/utils'

/* ── Helpers ── */

function computeRisk(s: Shipment, nodes: NetworkNode[]): number {
  const routeNodes = s.route_planned.map(id => nodes.find(n => n.id === id)).filter(Boolean) as NetworkNode[]
  const avgHealth = routeNodes.length ? routeNodes.reduce((a, n) => a + n.health_score, 0) / routeNodes.length : 0.9
  const minReliability = 0.88 // approximate from edges
  const slaHours = s.sla_deadline_hours
  const slaPressure = slaHours < 100 ? 0.7 : slaHours < 300 ? 0.35 : 0.1
  return Math.min(1, (1 - avgHealth) * 0.4 + (1 - minReliability) * 0.3 + slaPressure * 0.3)
}

function computeCost(s: Shipment): number {
  const edgeCosts: Record<string, number> = {
    'shanghai_port-singapore_port': 650, 'singapore_port-rotterdam_port': 2200,
    'rotterdam_port-frankfurt_dc': 350, 'shanghai_port-hamburg_port': 2950,
    'rotterdam_port-newyork_dc': 1400, 'newyork_dc-chicago_dc': 620,
    'shanghai_port-la_port': 3200, 'singapore_port-dubai_hub': 890,
    'dubai_hub-rotterdam_port': 1900, 'rotterdam_port-london_dc': 420,
    'tokyo_hub-la_port': 2600, 'la_port-newyork_dc': 1800,
    'seoul_hub-shanghai_port': 380, 'hamburg_port-rotterdam_port': 280,
    'dubai_hub-london_dc': 8800, 'mumbai_hub-dubai_hub': 520,
    'dubai_hub-frankfurt_dc': 8500, 'rotterdam_port-paris_dc': 380,
    'hamburg_port-paris_dc': 410,
  }
  let total = 0
  for (let i = 0; i < s.route_planned.length - 1; i++) {
    const key = `${s.route_planned[i]}-${s.route_planned[i + 1]}`
    const rev = `${s.route_planned[i + 1]}-${s.route_planned[i]}`
    total += (edgeCosts[key] ?? edgeCosts[rev] ?? 900) * (s.weight_tonnes / 10)
  }
  return Math.round(total)
}

function computeCarbon(s: Shipment): number {
  const base: Record<string, number> = {
    maersk: 420, cma_cgm: 410, msc: 430, hapag_lloyd: 400,
    one: 415, dhl: 4300, fedex: 4200, ups: 380,
  }
  return Math.round((base[s.current_carrier] ?? 420) * s.weight_tonnes / 10)
}

const STATUS_STYLE: Record<string, string> = {
  in_transit: 'text-neon border-neon/30 bg-neon/5',
  loading: 'text-muted border-border bg-surface',
  delivered: 'text-neon-dim border-neon/15 bg-neon/3',
  delayed: 'text-warn border-warn/30 bg-warn/5',
  blocked: 'text-critical border-critical/30 bg-critical/5',
}

const TIER_LABEL: Record<number, string> = { 1: 'PLATINUM', 2: 'GOLD', 3: 'SILVER' }
const TIER_COLOR: Record<number, string> = { 1: 'text-neon', 2: 'text-warn', 3: 'text-muted' }

/* ── Risk Badge ── */
function RiskBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = pct > 60 ? 'text-critical border-critical/30 bg-critical/5'
    : pct > 35 ? 'text-warn border-warn/30 bg-warn/5'
    : 'text-neon border-neon/20 bg-neon/5'
  return (
    <span className={cn('font-mono text-[10px] font-bold px-2 py-0.5 rounded border', color)}>
      {pct}
    </span>
  )
}

/* ── Route Timeline ── */
function RouteTimeline({ shipment }: { shipment: Shipment }) {
  const currentIdx = shipment.route_planned.indexOf(shipment.current_node)
  return (
    <div className="flex flex-col gap-0">
      {shipment.route_planned.map((node, i) => {
        const done = i < currentIdx
        const active = i === currentIdx
        const label = node.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
        return (
          <div key={node} className="flex items-start gap-3">
            <div className="flex flex-col items-center">
              <div className={cn('h-3 w-3 rounded-full border-2 mt-0.5 shrink-0', done ? 'bg-neon border-neon' : active ? 'bg-neon/30 border-neon animate-pulse' : 'bg-transparent border-border')} />
              {i < shipment.route_planned.length - 1 && <div className={cn('w-px flex-1 min-h-[20px]', done ? 'bg-neon/40' : 'bg-border')} />}
            </div>
            <div className="pb-3">
              <p className={cn('text-[11px] font-bold', active ? 'text-neon' : done ? 'text-text/60' : 'text-muted/40')}>{label}</p>
              {active && <p className="text-[9px] text-neon/60 tracking-widest">CURRENT POSITION</p>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/* ── Expanded Detail ── */
function ShipmentDetail({ s, nodes }: { s: Shipment; nodes: NetworkNode[] }) {
  const cost = computeCost(s)
  const carbon = computeCarbon(s)
  const risk = computeRisk(s, nodes)
  const riskPct = Math.round(risk * 100)
  const riskLabel = riskPct > 60 ? 'HIGH' : riskPct > 35 ? 'MEDIUM' : 'LOW'
  const riskColor = riskPct > 60 ? 'text-critical' : riskPct > 35 ? 'text-warn' : 'text-neon'

  return (
    <div className="grid grid-cols-3 gap-4 p-4 border-t border-border bg-bg">
      {/* Route timeline */}
      <div>
        <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-3">Route Timeline</p>
        <RouteTimeline shipment={s} />
      </div>

      {/* Cost breakdown */}
      <div className="border-l border-border pl-4">
        <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-3">Cost Breakdown</p>
        <div className="space-y-2">
          <div className="flex justify-between text-[11px]">
            <span className="text-muted flex items-center gap-1"><DollarSign size={10} />Freight Cost</span>
            <span className="font-mono font-bold text-text">${cost.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-muted flex items-center gap-1"><Leaf size={10} />Carbon (kg CO₂)</span>
            <span className="font-mono font-bold text-neon">{carbon.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-muted flex items-center gap-1"><TrendingUp size={10} />Cargo Value</span>
            <span className="font-mono font-bold text-text">${s.value_usd.toLocaleString()}</span>
          </div>
          <div className="h-px bg-border my-2" />
          <div className="flex justify-between text-[11px]">
            <span className="text-muted">Cost/Value ratio</span>
            <span className="font-mono font-bold text-text">{((cost / s.value_usd) * 100).toFixed(1)}%</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-muted">Carrier</span>
            <span className="font-mono font-bold text-text uppercase">{s.current_carrier.replace(/_/g, ' ')}</span>
          </div>
        </div>
      </div>

      {/* Risk assessment */}
      <div className="border-l border-border pl-4">
        <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-3">Risk Assessment</p>
        <div className="mb-3">
          <div className="flex items-center gap-2 mb-1">
            <span className={cn('font-display text-3xl font-bold', riskColor)}>{riskPct}</span>
            <div>
              <p className={cn('text-[10px] font-bold tracking-widest', riskColor)}>{riskLabel} RISK</p>
              <p className="text-[9px] text-muted">SENTINEL Score</p>
            </div>
          </div>
          <div className="h-1.5 w-full rounded-full bg-border overflow-hidden">
            <div className={cn('h-full rounded-full', riskPct > 60 ? 'bg-critical' : riskPct > 35 ? 'bg-warn' : 'bg-neon')} style={{ width: `${riskPct}%` }} />
          </div>
        </div>
        <div className="space-y-1.5">
          <div className="flex justify-between text-[10px]"><span className="text-muted">Node Health Factor</span><span className="font-mono text-text">{Math.round((1 - risk) * 100)}%</span></div>
          <div className="flex justify-between text-[10px]"><span className="text-muted">SLA Remaining</span><span className="font-mono text-text">{s.sla_deadline_hours}h</span></div>
          <div className="flex justify-between text-[10px]"><span className="text-muted">Priority Tier</span><span className={cn('font-bold tracking-widest text-[10px]', TIER_COLOR[s.priority_tier])}>{TIER_LABEL[s.priority_tier]}</span></div>
        </div>
        {riskPct > 35 && (
          <div className="mt-3 px-2 py-1.5 rounded border border-warn/20 bg-warn/5">
            <p className="text-[9px] text-warn font-bold tracking-widest mb-0.5">NAVIGATOR ADVISORY</p>
            <p className="text-[9px] text-warn/70">Alternative route via Rotterdam reduces risk by ~{Math.round(riskPct * 0.35)}pts</p>
          </div>
        )}
      </div>
    </div>
  )
}

/* ══════ PAGE ══════ */
export default function ShipmentsPage() {
  const nodes = INITIAL_NODES
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [sortKey, setSortKey] = useState<'risk' | 'value' | 'sla'>('risk')

  const enriched = useMemo(() => INITIAL_SHIPMENTS.map(s => ({
    ...s,
    risk: computeRisk(s, nodes),
    cost: computeCost(s),
    carbon: computeCarbon(s),
  })), [nodes])

  const displayed = useMemo(() => enriched
    .filter(s => filterStatus === 'all' || s.status === filterStatus)
    .sort((a, b) => sortKey === 'risk' ? b.risk - a.risk : sortKey === 'value' ? b.value_usd - a.value_usd : a.sla_deadline_hours - b.sla_deadline_hours),
    [enriched, filterStatus, sortKey])

  const totalValue = enriched.reduce((a, s) => a + s.value_usd, 0)
  const atRisk = enriched.filter(s => s.risk > 0.35).length
  const inTransit = enriched.filter(s => s.status === 'in_transit').length

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <PackageSearch size={16} className="text-neon" />
            <h2 className="font-display text-2xl font-bold tracking-wider text-text">Shipment Tracker</h2>
          </div>
          <p className="text-[11px] tracking-widest text-muted">NAVIGATOR · HERALD — Real-time cargo intelligence across 30 active shipments</p>
        </div>
      </div>

      {/* KPI bar */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        {[
          { label: 'Total Shipments', value: enriched.length, color: 'text-text' },
          { label: 'In Transit', value: inTransit, color: 'text-neon' },
          { label: 'At Risk', value: atRisk, color: atRisk > 0 ? 'text-critical' : 'text-neon' },
          { label: 'Loading', value: enriched.filter(s => s.status === 'loading').length, color: 'text-muted' },
          { label: 'Total Value', value: `$${(totalValue / 1e6).toFixed(1)}M`, color: 'text-neon' },
        ].map(k => (
          <div key={k.label} className="bg-surface border border-border rounded-lg p-4">
            <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-1">{k.label}</p>
            <p className={cn('font-mono text-2xl font-bold', k.color)}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex items-center gap-1.5">
          <Filter size={12} className="text-muted" />
          <span className="text-[10px] text-muted tracking-widest">STATUS:</span>
        </div>
        {['all', 'in_transit', 'loading'].map(s => (
          <button key={s} onClick={() => setFilterStatus(s)}
            className={cn('px-3 py-1 rounded text-[10px] font-bold tracking-widest border transition-all',
              filterStatus === s ? 'border-neon/40 text-neon bg-neon/5' : 'border-border text-muted hover:border-border hover:text-text')}>
            {s.replace('_', ' ').toUpperCase()}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1.5">
          <Clock size={12} className="text-muted" />
          <span className="text-[10px] text-muted tracking-widest">SORT:</span>
          {(['risk', 'value', 'sla'] as const).map(k => (
            <button key={k} onClick={() => setSortKey(k)}
              className={cn('px-3 py-1 rounded text-[10px] font-bold tracking-widest border transition-all',
                sortKey === k ? 'border-neon/40 text-neon bg-neon/5' : 'border-border text-muted hover:text-text')}>
              {k.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="bg-surface border border-border rounded-lg overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-[90px_1fr_110px_90px_100px_80px_70px_28px] gap-2 px-4 py-2.5 border-b border-border bg-bg/40">
          {['ID', 'Route', 'Cargo', 'Value', 'Carrier', 'Status', 'Risk', ''].map(h => (
            <p key={h} className="text-[8px] font-bold tracking-[0.25em] uppercase text-muted/50">{h}</p>
          ))}
        </div>

        {/* Table rows */}
        {displayed.map(s => {
          const expanded = expandedId === s.shipment_id
          return (
            <div key={s.shipment_id} className="border-b border-border/50 last:border-0">
              <button
                onClick={() => setExpandedId(expanded ? null : s.shipment_id)}
                className="w-full grid grid-cols-[90px_1fr_110px_90px_100px_80px_70px_28px] gap-2 px-4 py-3 hover:bg-neon/3 transition-colors text-left items-center"
              >
                <span className="font-mono text-[11px] font-bold text-neon">{s.shipment_id}</span>
                <span className="text-[11px] text-text truncate">
                  {s.origin.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())} →{' '}
                  <span className="text-muted">{s.destination.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
                </span>
                <span className="text-[10px] text-muted truncate">{s.cargo_type.replace(/_/g, ' ')}</span>
                <span className="font-mono text-[11px] text-text">${(s.value_usd / 1000).toFixed(0)}K</span>
                <span className="font-mono text-[10px] text-muted uppercase">{s.current_carrier.replace(/_/g, ' ')}</span>
                <span className={cn('text-[9px] font-bold px-2 py-0.5 rounded border w-fit', STATUS_STYLE[s.status] ?? STATUS_STYLE.in_transit)}>
                  {s.status.replace('_', ' ')}
                </span>
                <RiskBadge score={s.risk} />
                {expanded ? <ChevronUp size={12} className="text-muted" /> : <ChevronDown size={12} className="text-muted" />}
              </button>
              {expanded && <ShipmentDetail s={s} nodes={nodes} />}
            </div>
          )
        })}
      </div>
    </DashboardLayout>
  )
}
