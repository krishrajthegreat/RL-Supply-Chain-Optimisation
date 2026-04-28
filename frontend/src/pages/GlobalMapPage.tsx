import { useMemo } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { useSimulation } from '@/hooks/useSimulation'
import { type NetworkNode, type NetworkEdge, type AgentEvent, type RerouteAnalysis, AGENT_COLORS, getNodeCoords } from '@/lib/networkData'
import { ScatterplotLayer, ArcLayer, TextLayer } from '@deck.gl/layers'
import { DeckGL } from '@deck.gl/react'
import { Map } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { cn } from '@/lib/utils'
import { Zap, RotateCcw, CloudLightning, Ship, AlertTriangle, Navigation, Shield, Truck, Megaphone, Package, X, Leaf } from 'lucide-react'

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const INITIAL_VIEW = { longitude: 40, latitude: 28, zoom: 2.2, pitch: 15, bearing: 0 }
const NEON: [number,number,number] = [94, 210, 156]
const WARN: [number,number,number] = [245, 166, 35]
const CRIT: [number,number,number] = [239, 68, 68]


function healthColor(h: number, cs: string): [number,number,number,number] {
  if (cs === 'open') return [...CRIT, 220]
  if (cs === 'half_open') return [...WARN, 200]
  if (h > 0.8) return [...NEON, 200]
  if (h > 0.5) return [...WARN, 200]
  return [...CRIT, 220]
}

function modeColor(m: string): [number,number,number,number] {
  if (m === 'sea') return [94,210,156,100]
  if (m === 'rail') return [245,166,35,120]
  if (m === 'air') return [239,68,68,140]
  return [100,115,110,80]
}

const AGENT_ICONS: Record<string, typeof Zap> = {
  SENTINEL: Zap, GUARDIAN: Shield, NAVIGATOR: Navigation, STOCKPILE: Package, BROKER: Truck, HERALD: Megaphone,
}

/* ═══════════════════════════════════════════════════════════ */

export default function GlobalMapPage() {
  const sim = useSimulation()
  const coords = useMemo(() => getNodeCoords(sim.nodes), [sim.nodes])

  const layers = useMemo(() => {
    const nodeLayer = new ScatterplotLayer<NetworkNode>({
      id: 'nodes',
      data: sim.nodes,
      getPosition: d => [d.lng, d.lat],
      getRadius: d => Math.max(d.throughput_capacity / 60, 18),
      getFillColor: d => healthColor(d.health_score, d.circuit_state),
      radiusUnits: 'pixels' as const,
      radiusMinPixels: 6,
      radiusMaxPixels: 40,
      pickable: true,
      onClick: (info: any) => { if (info.object) sim.setSelectedNode(info.object.id) },
      transitions: { getFillColor: 600, getRadius: 600 },
    })

    const glowLayer = new ScatterplotLayer<NetworkNode>({
      id: 'node-glow',
      data: sim.nodes.filter(n => n.circuit_state === 'open'),
      getPosition: d => [d.lng, d.lat],
      getRadius: 55,
      getFillColor: [239, 68, 68, 40],
      radiusUnits: 'pixels' as const,
      radiusMinPixels: 30,
    })

    const edgeLayer = new ArcLayer<NetworkEdge>({
      id: 'edges',
      data: sim.edges,
      getSourcePosition: d => coords[d.from] || [0,0],
      getTargetPosition: d => coords[d.to] || [0,0],
      getSourceColor: d => modeColor(d.mode),
      getTargetColor: d => modeColor(d.mode),
      getWidth: 2,
      greatCircle: true,
      pickable: true,
    })

    const shipLayer = new ScatterplotLayer({
      id: 'shipments',
      data: sim.shipments.map(s => {
        const c = coords[s.current_node]
        return c ? { ...s, pos: c } : null
      }).filter(Boolean),
      getPosition: (d: any) => d.pos,
      getRadius: 5,
      getFillColor: [255, 255, 255, 200],
      radiusUnits: 'pixels' as const,
      radiusMinPixels: 3,
      radiusMaxPixels: 8,
      pickable: true,
    })

    const labelLayer = new TextLayer<NetworkNode>({
      id: 'labels',
      data: sim.nodes,
      getPosition: d => [d.lng, d.lat],
      getText: d => d.name.replace('Port of ', '').replace(' Distribution Center', ' DC').replace(' Logistics Hub', ''),
      getSize: 11,
      getColor: [200, 215, 210, 180],
      getPixelOffset: [0, -22],
      fontFamily: 'JetBrains Mono',
      fontWeight: 700,
      outlineWidth: 2,
      outlineColor: [7, 11, 10, 200],
      billboard: false,
    })

    // Reroute arcs: old route (red dashed feel via thin) + new route (green thick)
    const rerouteArcs: any[] = []
    if (sim.activeReroute) {
      const r = sim.activeReroute
      // Old route - red
      for (let i = 0; i < r.original_route.length - 1; i++) {
        const f = coords[r.original_route[i]], t = coords[r.original_route[i+1]]
        if (f && t) rerouteArcs.push({ src: f, tgt: t, color: [...CRIT, 180] })
      }
      // New route - green
      const sel = r.options.find(o => o.selected)
      if (sel) {
        for (let i = 0; i < sel.route.length - 1; i++) {
          const f = coords[sel.route[i]], t = coords[sel.route[i+1]]
          if (f && t) rerouteArcs.push({ src: f, tgt: t, color: [...NEON, 255] })
        }
      }
    }
    const rerouteLayer = new ArcLayer({
      id: 'reroute',
      data: rerouteArcs,
      getSourcePosition: (d: any) => d.src,
      getTargetPosition: (d: any) => d.tgt,
      getSourceColor: (d: any) => d.color,
      getTargetColor: (d: any) => d.color,
      getWidth: 4,
      greatCircle: true,
    })

    return [edgeLayer, glowLayer, nodeLayer, shipLayer, labelLayer, rerouteLayer]
  }, [sim.nodes, sim.edges, sim.shipments, sim.activeReroute, coords, sim.setSelectedNode])

  const selNode = sim.nodes.find(n => n.id === sim.selectedNode)

  return (
    <DashboardLayout>
      <div className="relative flex flex-col h-full -m-6">
        {/* Map */}
        <div className="relative flex-1 min-h-0" style={{ background: '#070b0a' }}>
          <DeckGL initialViewState={INITIAL_VIEW} controller={true} layers={layers} style={{ position: 'absolute', top: '0', left: '0', right: '0', bottom: '0' }}>
            <Map mapStyle={MAP_STYLE} />
          </DeckGL>

          {/* ── Disruption Panel (top-left) ── */}
          <div className="absolute top-4 left-4 z-20 w-[220px]" style={{ background: 'rgba(7,11,10,0.88)', border: '1px solid rgba(94,210,156,0.12)', borderRadius: 8, backdropFilter: 'blur(12px)' }}>
            <div className="px-3 py-2.5 border-b" style={{ borderColor: 'rgba(94,210,156,0.1)' }}>
              <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-neon/70">Scenario Injection</p>
            </div>
            <div className="p-2 space-y-1.5">
              <ScenarioBtn icon={CloudLightning} label="Hamburg Storm Surge" color="critical" onClick={sim.injectHamburgStorm} disabled={sim.disruptionActive} />
              <ScenarioBtn icon={Ship} label="Shanghai Port Closure" color="warn" onClick={sim.injectShanghaiClosure} disabled={sim.disruptionActive} />
              <ScenarioBtn icon={AlertTriangle} label="Red Sea Geopolitical" color="warn" onClick={sim.injectRedSea} disabled={sim.disruptionActive} />
              <button onClick={sim.resetSimulation} className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-[10px] font-bold tracking-widest text-muted hover:text-text border border-border hover:border-neon/20 transition-all">
                <RotateCcw size={12} /> RESET NETWORK
              </button>
            </div>
          </div>

          {/* ── Agent Feed (top-right) ── */}
          <div className="absolute top-4 right-4 z-20 w-[300px] max-h-[420px] flex flex-col" style={{ background: 'rgba(7,11,10,0.88)', border: '1px solid rgba(94,210,156,0.12)', borderRadius: 8, backdropFilter: 'blur(12px)' }}>
            <div className="px-3 py-2.5 border-b shrink-0" style={{ borderColor: 'rgba(94,210,156,0.1)' }}>
              <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-neon/70">Agent Activity Feed</p>
            </div>
            <div className="flex-1 overflow-y-auto p-2" style={{ maskImage: 'linear-gradient(to bottom, black 90%, transparent)', WebkitMaskImage: 'linear-gradient(to bottom, black 90%, transparent)' }}>
              {sim.events.length === 0 && (
                <p className="text-[10px] text-muted/50 text-center py-6">Inject a scenario to see agents respond</p>
              )}
              {sim.events.map(e => <EventRow key={e.id} event={e} />)}
            </div>
          </div>

          {/* ── Metrics Bar (bottom) ── */}
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 flex items-center gap-6 px-5 py-2.5" style={{ background: 'rgba(7,11,10,0.88)', border: '1px solid rgba(94,210,156,0.12)', borderRadius: 99, backdropFilter: 'blur(12px)' }}>
            <Metric label="Shipments" value={sim.metrics.totalShipments} />
            <Metric label="At Risk" value={sim.metrics.atRisk} warn={sim.metrics.atRisk > 0} />
            <Metric label="Circuit Opens" value={sim.metrics.circuitOpens} warn={sim.metrics.circuitOpens > 0} />
            <Metric label="Reroutes" value={sim.metrics.reroutes} />
            <div className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-neon animate-pulse" />
              <span className="text-[9px] font-bold tracking-widest text-neon uppercase">Live</span>
            </div>
          </div>

          {/* ── Node Detail Popup ── */}
          {selNode && <NodePopup node={selNode} onClose={() => sim.setSelectedNode(null)} />}
        </div>

        {/* ── Pareto Reroute Panel (slides up from bottom) ── */}
        {sim.activeReroute && <ParetoPanel analysis={sim.activeReroute} onDismiss={sim.dismissReroute} />}
      </div>
    </DashboardLayout>
  )
}

/* ── Sub-components ── */

function ScenarioBtn({ icon: Icon, label, color, onClick, disabled }: { icon: any; label: string; color: string; onClick: () => void; disabled: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'w-full flex items-center gap-2 px-3 py-2 rounded-md text-[10px] font-bold tracking-wide transition-all border',
        disabled ? 'opacity-40 cursor-not-allowed border-border text-muted'
          : color === 'critical' ? 'border-critical/30 text-critical hover:bg-critical/10 hover:border-critical/50'
          : 'border-warn/30 text-warn hover:bg-warn/10 hover:border-warn/50'
      )}
    >
      <Icon size={13} /> {label}
    </button>
  )
}

function EventRow({ event: e }: { event: AgentEvent }) {
  const Icon = AGENT_ICONS[e.agent] || Zap
  const color = AGENT_COLORS[e.agent] || '#5ed29c'
  return (
    <div className="flex gap-2 py-1.5 border-b border-border/30 last:border-0 animate-fade-in">
      <div className="shrink-0 mt-0.5"><Icon size={11} style={{ color }} /></div>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] font-bold tracking-[0.2em] uppercase" style={{ color }}>{e.agent}</span>
          <span className="text-[8px] text-muted/40">{e.timestamp}</span>
        </div>
        <p className={cn('text-[10px] leading-relaxed', e.severity === 'critical' ? 'text-critical' : e.severity === 'warn' ? 'text-warn' : 'text-text/70')}>
          {e.message}
        </p>
      </div>
    </div>
  )
}

function Metric({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div className="text-center">
      <p className={cn('text-sm font-bold font-mono', warn ? 'text-critical' : 'text-text')}>{value}</p>
      <p className="text-[8px] tracking-widest text-muted uppercase">{label}</p>
    </div>
  )
}

function NodePopup({ node, onClose }: { node: NetworkNode; onClose: () => void }) {
  const h = node.health_score
  const hColor = node.circuit_state === 'open' ? 'text-critical' : h > 0.8 ? 'text-neon' : h > 0.5 ? 'text-warn' : 'text-critical'
  const csLabel = node.circuit_state === 'closed' ? 'CLOSED' : node.circuit_state === 'open' ? 'OPEN' : 'HALF-OPEN'
  const csColor = node.circuit_state === 'closed' ? 'text-neon' : node.circuit_state === 'open' ? 'text-critical' : 'text-warn'
  return (
    <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 w-[280px]" style={{ background: 'rgba(7,11,10,0.92)', border: '1px solid rgba(94,210,156,0.15)', borderRadius: 8, backdropFilter: 'blur(16px)' }}>
      <div className="flex items-center justify-between px-3 py-2 border-b" style={{ borderColor: 'rgba(94,210,156,0.1)' }}>
        <span className="text-[11px] font-bold text-text">{node.name}</span>
        <button onClick={onClose} className="text-muted hover:text-text"><X size={13} /></button>
      </div>
      <div className="p-3 space-y-2">
        <div className="flex justify-between text-[10px]"><span className="text-muted">Health Score</span><span className={cn('font-bold font-mono', hColor)}>{(h * 100).toFixed(0)}%</span></div>
        <div className="h-1 w-full rounded-full bg-border overflow-hidden"><div className={cn('h-full rounded-full', h > 0.8 ? 'bg-neon' : h > 0.5 ? 'bg-warn' : 'bg-critical')} style={{ width: `${h * 100}%` }} /></div>
        <div className="flex justify-between text-[10px]"><span className="text-muted">Circuit State</span><span className={cn('font-bold tracking-widest', csColor)}>{csLabel}</span></div>
        <div className="flex justify-between text-[10px]"><span className="text-muted">Type</span><span className="text-text uppercase tracking-widest">{node.type}</span></div>
        <div className="flex justify-between text-[10px]"><span className="text-muted">Throughput</span><span className="text-text font-mono">{node.throughput_capacity.toLocaleString()} TEU</span></div>
        <div className="flex justify-between text-[10px]"><span className="text-muted">Queue Depth</span><span className="text-text font-mono">{node.current_queue_depth}</span></div>
        <div className="flex justify-between text-[10px]"><span className="text-muted">Congestion</span><span className="text-text font-mono">{(node.congestion_score * 100).toFixed(0)}%</span></div>
        <div className="flex justify-between text-[10px]"><span className="text-muted">Weather</span><span className="text-text font-mono">{node.weather_severity.toFixed(1)}/10</span></div>
      </div>
    </div>
  )
}

function ParetoPanel({ analysis: a, onDismiss }: { analysis: RerouteAnalysis; onDismiss: () => void }) {

  return (
    <div className="border-t border-neon/15 animate-slide-up" style={{ background: 'rgba(7,11,10,0.95)', backdropFilter: 'blur(16px)' }}>
      <div className="max-w-5xl mx-auto p-5">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Navigation size={16} className="text-neon" />
            <div>
              <h3 className="text-[13px] font-bold text-text flex items-center gap-2">
                NAVIGATOR — Reroute Analysis
                <span className="text-[8px] tracking-widest uppercase px-2 py-0.5 rounded-full bg-neon/15 text-neon border border-neon/20">RL Decision</span>
              </h3>
              <p className="text-[10px] text-muted mt-0.5">
                {a.shipment_id} · {a.cargo_type.replace(/_/g, ' ')} · {a.origin.replace(/_/g, ' ')} → {a.destination.replace(/_/g, ' ')}
              </p>
            </div>
          </div>
          <button onClick={onDismiss} className="text-muted hover:text-text transition-colors"><X size={16} /></button>
        </div>

        {/* Blocked route */}
        <div className="mb-4 px-3 py-2 rounded-md border border-critical/20 bg-critical/5">
          <div className="flex items-center gap-2 text-[10px]">
            <AlertTriangle size={11} className="text-critical" />
            <span className="font-bold text-critical tracking-widest">BLOCKED ROUTE</span>
          </div>
          <p className="text-[10px] text-muted mt-1">{a.original_route.map(n => n.replace(/_/g, ' ')).join(' → ')}</p>
          <p className="text-[9px] text-critical/70 mt-0.5">Node <span className="font-bold">{a.blocked_node.replace(/_/g, ' ')}</span> — circuit OPEN by GUARDIAN</p>
        </div>

        {/* Route options */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          {a.options.map(opt => (
            <div key={opt.label} className={cn('rounded-md border p-3 transition-all', opt.selected ? 'border-neon/40 bg-neon/5' : 'border-border bg-bg/40')}>
              <div className="flex items-center justify-between mb-2">
                <span className={cn('text-[11px] font-bold', opt.selected ? 'text-neon' : 'text-muted')}>{opt.label}</span>
                {opt.selected && <span className="text-[8px] font-bold tracking-widest uppercase px-1.5 py-0.5 rounded bg-neon text-bg">RL-SELECTED</span>}
              </div>
              <p className="text-[9px] text-muted/70 mb-3 leading-relaxed">{opt.route.map(n => n.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())).join(' → ')}</p>
              <div className="space-y-1.5">
                <MetricRow icon="⏱" label="Transit" value={`${opt.transit_hours}h`} best={opt.transit_hours <= Math.min(...a.options.map(o => o.transit_hours))} />
                <MetricRow icon="💰" label="Cost" value={`$${opt.cost_usd.toLocaleString()}`} best={opt.cost_usd <= Math.min(...a.options.map(o => o.cost_usd))} />
                <MetricRow icon="🌿" label="Carbon" value={`${opt.carbon_kg.toLocaleString()} kg`} best={opt.carbon_kg <= Math.min(...a.options.map(o => o.carbon_kg))} />
                <MetricRow icon="⚡" label="Reliability" value={`${(opt.reliability * 100).toFixed(0)}%`} best={opt.reliability >= Math.max(...a.options.map(o => o.reliability))} />
                <div className="flex items-center justify-between text-[9px] pt-1 border-t border-border/50">
                  <span className="flex items-center gap-1"><Leaf size={9} className="text-neon/60" />Green-Resilience</span>
                  <div className="flex items-center gap-1.5">
                    <div className="h-1 w-12 rounded-full bg-border overflow-hidden"><div className="h-full rounded-full bg-neon" style={{ width: `${opt.green_resilience * 100}%` }} /></div>
                    <span className={cn('font-bold font-mono', opt.green_resilience > 0.6 ? 'text-neon' : opt.green_resilience > 0.3 ? 'text-warn' : 'text-critical')}>{(opt.green_resilience * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* RL Rationale */}
        <div className="flex items-start gap-3 px-3 py-2.5 rounded-md border border-neon/15 bg-neon/3">
          <Zap size={14} className="text-neon shrink-0 mt-0.5" />
          <div>
            <p className="text-[10px] font-bold text-neon tracking-widest uppercase mb-1">RL Agent Rationale</p>
            <p className="text-[10px] text-text/70 leading-relaxed">{a.rationale}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function MetricRow({ icon, label, value, best }: { icon: string; label: string; value: string; best: boolean }) {
  return (
    <div className="flex items-center justify-between text-[9px]">
      <span className="text-muted">{icon} {label}</span>
      <span className={cn('font-bold font-mono', best ? 'text-neon' : 'text-text/60')}>{value}{best && ' ✓'}</span>
    </div>
  )
}
