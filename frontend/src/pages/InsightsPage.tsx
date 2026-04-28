import { useEffect, useRef, useMemo, useState } from 'react'
import * as d3 from 'd3-geo'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { INITIAL_NODES } from '@/lib/networkData'
import { LineChart as LineChartIcon, Globe2, Leaf, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'

/* ── Country → Nodes mapping ── */
const COUNTRY_NODES: Record<string, string[]> = {
  CN: ['shanghai_port'], NL: ['rotterdam_port'], DE: ['hamburg_port','frankfurt_dc'],
  SG: ['singapore_port'], US: ['la_port','newyork_dc','chicago_dc'], GB: ['london_dc'],
  FR: ['paris_dc'], AE: ['dubai_hub'], IN: ['mumbai_hub'], JP: ['tokyo_hub'],
  KR: ['seoul_hub'], AU: ['sydney_dc'],
}

function countryRisk(countryCode: string): number {
  const nodeIds = COUNTRY_NODES[countryCode]
  if (!nodeIds) return -1
  const nodes = INITIAL_NODES.filter(n => nodeIds.includes(n.id))
  if (!nodes.length) return -1
  const avgHealth = nodes.reduce((a, n) => a + n.health_score, 0) / nodes.length
  return 1 - avgHealth
}

/* ── Region risk table data ── */
const REGIONS = [
  { region: 'Northern Europe', nodes: ['rotterdam_port','hamburg_port','frankfurt_dc','london_dc','paris_dc'], disruptions: 1 },
  { region: 'East Asia', nodes: ['shanghai_port','tokyo_hub','seoul_hub'], disruptions: 0 },
  { region: 'Southeast Asia', nodes: ['singapore_port'], disruptions: 0 },
  { region: 'Middle East', nodes: ['dubai_hub'], disruptions: 0 },
  { region: 'North America', nodes: ['la_port','newyork_dc','chicago_dc'], disruptions: 0 },
  { region: 'South Asia', nodes: ['mumbai_hub'], disruptions: 0 },
  { region: 'Oceania', nodes: ['sydney_dc'], disruptions: 0 },
].map(r => ({
  ...r,
  avgHealth: INITIAL_NODES.filter(n => r.nodes.includes(n.id)).reduce((a, n) => a + n.health_score, 0) / r.nodes.length,
  shipmentsAffected: r.disruptions > 0 ? 4 : 0,
})).sort((a, b) => a.avgHealth - b.avgHealth)

/* ── Top threats ── */
const TOP_THREATS = [
  { id: 'T-001', title: 'Hamburg Storm Surge', severity: 'critical', region: 'Northern Europe', impact: 'HIGH', agents: 4 },
  { id: 'T-002', title: 'Red Sea Lane Geopolitical Risk', severity: 'warn', region: 'Middle East', impact: 'MEDIUM', agents: 2 },
  { id: 'T-003', title: 'Mumbai Monsoon Season', severity: 'warn', region: 'South Asia', impact: 'MEDIUM', agents: 1 },
  { id: 'T-004', title: 'LA Port Congestion', severity: 'warn', region: 'North America', impact: 'LOW', agents: 1 },
  { id: 'T-005', title: 'Shanghai Throughput Recovery', severity: 'info', region: 'East Asia', impact: 'MONITOR', agents: 0 },
]

/* ── D3 Geo Choropleth Map ── */
const WORLD_URL = 'https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json'

function WorldMap({ selectedCountry, onSelect }: { selectedCountry: string | null; onSelect: (c: string | null) => void }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [geoData, setGeoData] = useState<any>(null)

  useEffect(() => {
    fetch(WORLD_URL)
      .then(r => r.json())
      .then(topo => {
        // inline topojson feature extraction (avoid topojson import for compat)
        // inline topojson feature extraction done below
        setGeoData(topo)
      })
      .catch(() => setGeoData(null))
  }, [])

  useEffect(() => {
    if (!svgRef.current || !geoData) return
    const svg = svgRef.current
    const W = svg.clientWidth || 700
    const H = svg.clientHeight || 360

    // We dynamically import topojson-client
    import('topojson-client').then(({ feature }) => {
      const geojson = feature(geoData, geoData.objects.countries) as any
      const projection = d3.geoNaturalEarth1()
        .scale(W / 6.2)
        .translate([W / 2, H / 2])
      const pathGen = d3.geoPath().projection(projection)

      // Country code lookup (numeric ISO → alpha-2) — partial list for our nodes
      const numericToAlpha2: Record<number, string> = {
        156: 'CN', 528: 'NL', 276: 'DE', 702: 'SG', 840: 'US', 826: 'GB',
        250: 'FR', 784: 'AE', 356: 'IN', 392: 'JP', 410: 'KR', 36: 'AU',
      }

      // Clear previous
      while (svg.firstChild) svg.removeChild(svg.firstChild)

      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g')
      svg.appendChild(g)

      for (const feat of geojson.features) {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
        const alpha2 = numericToAlpha2[Number(feat.id)]
        const risk = alpha2 ? countryRisk(alpha2) : -1
        const isSelected = alpha2 === selectedCountry

        let fill = 'rgba(20,30,25,0.7)'
        if (risk >= 0) {
          if (risk > 0.2) fill = `rgba(239,68,68,${0.3 + risk * 0.4})`
          else if (risk > 0.1) fill = `rgba(245,166,35,${0.3 + risk * 0.5})`
          else fill = `rgba(94,210,156,${0.25 + risk * 0.3})`
        }
        if (isSelected) fill = 'rgba(94,210,156,0.45)'

        path.setAttribute('d', pathGen(feat) || '')
        path.setAttribute('fill', fill)
        path.setAttribute('stroke', isSelected ? '#5ed29c' : 'rgba(94,210,156,0.1)')
        path.setAttribute('stroke-width', isSelected ? '1.5' : '0.5')
        path.style.cursor = alpha2 && COUNTRY_NODES[alpha2] ? 'pointer' : 'default'
        path.style.transition = 'fill 0.3s'

        if (alpha2 && COUNTRY_NODES[alpha2]) {
          path.addEventListener('mouseenter', () => {
            path.setAttribute('fill', 'rgba(94,210,156,0.3)')
          })
          path.addEventListener('mouseleave', () => {
            path.setAttribute('fill', isSelected ? 'rgba(94,210,156,0.45)' : fill)
          })
          path.addEventListener('click', () => onSelect(alpha2 === selectedCountry ? null : alpha2))
        }

        g.appendChild(path)
      }

      // Draw node dots
      for (const node of INITIAL_NODES) {
        const [x, y] = projection([node.lng, node.lat]) ?? [0, 0]
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
        const r = node.circuit_state === 'open' ? 6 : 4
        const color = node.circuit_state === 'open' ? '#ef4444' : node.health_score > 0.8 ? '#5ed29c' : node.health_score > 0.5 ? '#f5a623' : '#ef4444'
        circle.setAttribute('cx', String(x))
        circle.setAttribute('cy', String(y))
        circle.setAttribute('r', String(r))
        circle.setAttribute('fill', color)
        circle.setAttribute('fill-opacity', '0.9')
        circle.setAttribute('stroke', '#070b0a')
        circle.setAttribute('stroke-width', '1')
        g.appendChild(circle)
      }
    })
  }, [geoData, selectedCountry, onSelect])

  return (
    <div className="relative w-full h-full">
      {!geoData && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center">
            <div className="h-6 w-6 border-2 border-neon border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-[10px] text-muted">Loading geo data...</p>
          </div>
        </div>
      )}
      <svg ref={svgRef} className="w-full h-full" />
      {/* Legend */}
      <div className="absolute bottom-3 left-3 flex items-center gap-3">
        {[
          { color: 'bg-neon', label: 'Low Risk' },
          { color: 'bg-warn', label: 'Medium' },
          { color: 'bg-critical', label: 'High Risk' },
        ].map(l => (
          <div key={l.label} className="flex items-center gap-1.5">
            <div className={cn('h-2 w-2 rounded-full', l.color)} />
            <span className="text-[8px] text-muted">{l.label}</span>
          </div>
        ))}
        <span className="text-[8px] text-muted/50 ml-2">● = Network Node</span>
      </div>
    </div>
  )
}

/* ══════ PAGE ══════ */
export default function InsightsPage() {
  const [selectedCountry, setSelectedCountry] = useState<string | null>(null)
  const avgHealth = useMemo(() => INITIAL_NODES.reduce((a, n) => a + n.health_score, 0) / INITIAL_NODES.length, [INITIAL_NODES.length])
  const totalRisk = INITIAL_NODES.filter(n => n.health_score < 0.6).length

  const ALPHA2_NAME: Record<string, string> = {
    CN:'China', NL:'Netherlands', DE:'Germany', SG:'Singapore', US:'United States',
    GB:'United Kingdom', FR:'France', AE:'UAE', IN:'India', JP:'Japan', KR:'South Korea', AU:'Australia',
  }

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <LineChartIcon size={16} className="text-neon" />
            <h2 className="font-display text-2xl font-bold tracking-wider text-text">Executive Insights</h2>
          </div>
          <p className="text-[11px] tracking-widest text-muted">C-Suite Overview — Global risk posture, network health & RL simulation projections</p>
        </div>
        {selectedCountry && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-neon/20 bg-neon/5">
            <Globe2 size={11} className="text-neon" />
            <span className="text-[10px] font-bold text-neon">{ALPHA2_NAME[selectedCountry] ?? selectedCountry}</span>
            <button onClick={() => setSelectedCountry(null)} className="text-neon/50 hover:text-neon text-xs">×</button>
          </div>
        )}
      </div>

      {/* Top KPI row */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <div className="bg-surface border border-border rounded-lg p-4">
          <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-1">Network Health Index</p>
          <p className="font-mono text-3xl font-bold text-neon">{Math.round(avgHealth * 100)}</p>
          <p className="text-[9px] text-muted mt-1">↑ 2.1pts vs 24h ago</p>
        </div>
        <div className="bg-surface border border-border rounded-lg p-4">
          <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-1">Nodes at Risk</p>
          <p className={cn('font-mono text-3xl font-bold', totalRisk > 0 ? 'text-critical' : 'text-neon')}>{totalRisk}</p>
          <p className="text-[9px] text-muted mt-1">of 15 total network nodes</p>
        </div>
        <div className="bg-surface border border-border rounded-lg p-4">
          <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-1">SLA Compliance</p>
          <p className="font-mono text-3xl font-bold text-neon">98.2%</p>
          <p className="text-[9px] text-muted mt-1">0 breaches last 72h</p>
        </div>
        <div className="bg-surface border border-neon/15 rounded-lg p-4">
          <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-1 flex items-center gap-1"><Leaf size={9} />Green-Resilience Score</p>
          <p className="font-mono text-3xl font-bold text-neon">74</p>
          <p className="text-[9px] text-muted mt-1">Carbon × Resilience correlation</p>
        </div>
      </div>

      {/* Main layout: map + right panels */}
      <div className="grid grid-cols-[1fr_320px] gap-4">

        {/* Map */}
        <div className="bg-surface border border-border rounded-lg overflow-hidden" style={{ height: 420 }}>
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border shrink-0">
            <Globe2 size={12} className="text-neon" />
            <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-text">Global Risk Choropleth</span>
            <span className="text-[8px] text-muted ml-auto">Powered by D3 Natural Earth · Click region to filter</span>
          </div>
          <div className="flex-1 relative" style={{ height: 380 }}>
            <WorldMap selectedCountry={selectedCountry} onSelect={setSelectedCountry} />
          </div>
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-4">

          {/* Regional Risk Table */}
          <div className="bg-surface border border-border rounded-lg overflow-hidden">
            <div className="px-4 py-2.5 border-b border-border">
              <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-text">Regional Risk Breakdown</span>
            </div>
            <div>
              {REGIONS.map(r => {
                const health = r.avgHealth
                const riskPct = Math.round((1 - health) * 100)
                const color = riskPct > 20 ? 'bg-critical' : riskPct > 12 ? 'bg-warn' : 'bg-neon'
                const textColor = riskPct > 20 ? 'text-critical' : riskPct > 12 ? 'text-warn' : 'text-neon'
                return (
                  <div key={r.region} className="flex items-center gap-3 px-4 py-2.5 border-b border-border/40 hover:bg-neon/2 transition-colors">
                    <div className="flex-1 min-w-0">
                      <p className="text-[10px] font-bold text-text truncate">{r.region}</p>
                      <p className="text-[8px] text-muted">{r.nodes.length} node{r.nodes.length > 1 ? 's' : ''}{r.disruptions > 0 ? ` · ${r.disruptions} disruption` : ''}</p>
                    </div>
                    <div className="w-16">
                      <div className="h-1 w-full rounded-full bg-border overflow-hidden">
                        <div className={cn('h-full rounded-full', color)} style={{ width: `${riskPct}%` }} />
                      </div>
                    </div>
                    <span className={cn('font-mono text-[10px] font-bold w-6 text-right', textColor)}>{riskPct}</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Top Threats */}
          <div className="bg-surface border border-border rounded-lg overflow-hidden">
            <div className="px-4 py-2.5 border-b border-border">
              <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-text">Top Threats</span>
            </div>
            <div>
              {TOP_THREATS.map(t => (
                <div key={t.id} className="flex items-start gap-2 px-4 py-2.5 border-b border-border/40 last:border-0">
                  <AlertTriangle size={11} className={cn('shrink-0 mt-0.5', t.severity === 'critical' ? 'text-critical' : t.severity === 'warn' ? 'text-warn' : 'text-neon/40')} />
                  <div className="min-w-0 flex-1">
                    <p className={cn('text-[10px] font-bold', t.severity === 'critical' ? 'text-critical' : t.severity === 'warn' ? 'text-warn' : 'text-text/60')}>{t.title}</p>
                    <p className="text-[8px] text-muted">{t.region} · Impact: {t.impact}</p>
                  </div>
                  {t.agents > 0 && (
                    <span className="text-[8px] font-bold text-neon/60 shrink-0">{t.agents} agents</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
