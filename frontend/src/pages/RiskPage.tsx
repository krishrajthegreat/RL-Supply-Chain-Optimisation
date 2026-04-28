import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { INITIAL_NODES, INITIAL_EDGES } from '@/lib/networkData'
import { ShieldAlert, Zap, TrendingDown, Activity } from 'lucide-react'
import { ResponsiveContainer, ScatterChart, Scatter, XAxis, YAxis, Tooltip, ReferenceLine, AreaChart, Area } from 'recharts'
import { cn } from '@/lib/utils'

/* ── Mock OSINT feed ── */
const OSINT_FEED = [
  { id:1, src:'SOCIAL', icon:'📱', severity:'critical', time:'14:22Z', title:'Hamburg port delays worsening — r/logistics surge', detail:'Sentiment: -0.81 · Volume: 3.2× baseline · Impact: HIGH', region:'Northern Europe' },
  { id:2, src:'NEWS', icon:'📰', severity:'warn', time:'14:18Z', title:'Reuters: Red Sea shipping reroutes add 30% transit time', detail:'Lane: Dubai→Rotterdam · Geopolitical Risk: +0.28 · Duration: 7–14 days', region:'Middle East' },
  { id:3, src:'FINANCIAL', icon:'📊', severity:'warn', time:'14:09Z', title:'Hapag-Lloyd OTP dropped 12% vs Q2 baseline', detail:'Carrier Health: DEGRADING · Soft blackout flag raised by BROKER', region:'Global' },
  { id:4, src:'WEATHER', icon:'🌊', severity:'critical', time:'13:55Z', title:'Storm system approaching Port of Hamburg — Severity 8.0/10', detail:'ECMWF forecast: 18–36h disruption window · Vessels: 14 affected', region:'Northern Europe' },
  { id:5, src:'SOCIAL', icon:'📱', severity:'info', time:'13:40Z', title:'Singapore port efficiency at all-time high — Forbes Logistics', detail:'Sentiment: +0.72 · Queue depth: 6 (avg 12) · Health: 97%', region:'Southeast Asia' },
  { id:6, src:'NEWS', icon:'📰', severity:'info', time:'13:22Z', title:'Shanghai port congestion easing — 18h queue reduction', detail:'Congestion score: 0.35 → 0.28 · Throughput recovering', region:'East Asia' },
  { id:7, src:'FINANCIAL', icon:'📊', severity:'warn', time:'12:55Z', title:'MSC capacity utilization at 88% — surge pricing likely', detail:'BROKER Advisory: Book alternative carriers for Q4 demand', region:'Global' },
  { id:8, src:'WEATHER', icon:'🌊', severity:'info', time:'12:30Z', title:'Arabian Sea weather system dissipating', detail:'Mumbai hub weather severity: 3.0 → 1.8 · Recovery in 6h', region:'South Asia' },
]

/* ── Carbon-Disruption scatter (Green-Resilience thesis) ── */
const SCATTER_DATA = INITIAL_EDGES.map(e => ({
  carbon: e.carbon_kg_per_teu,
  disruption: Math.round((1 - e.reliability_score) * 100 + e.geopolitical_risk_score * 50),
  mode: e.mode,
  label: `${e.from.replace(/_/g, ' ')} → ${e.to.replace(/_/g, ' ')}`,
}))

const MODE_COLOR: Record<string, string> = { sea: '#5ed29c', rail: '#f5a623', road: '#64736e', air: '#ef4444' }

/* ── Node risk sparklines (mock trend data) ── */
function mkTrend(base: number) {
  return Array.from({ length: 12 }, (_, i) => ({
    t: i, v: Math.max(0, Math.min(1, base + (Math.random() - 0.5) * 0.15))
  }))
}

const NODE_RISK = INITIAL_NODES.map(n => ({
  ...n,
  riskScore: Math.min(1, (1 - n.health_score) * 0.5 + n.congestion_score * 0.3 + n.weather_severity / 20),
  trend: mkTrend(1 - n.health_score),
})).sort((a, b) => b.riskScore - a.riskScore)

/* ── Animated counter ── */
function useCount(target: number) {
  const [v, setV] = useState(0)
  useEffect(() => {
    let frame: number
    const start = Date.now()
    const animate = () => {
      const p = Math.min((Date.now() - start) / 1000, 1)
      setV(Math.round(target * (1 - Math.pow(1 - p, 3))))
      if (p < 1) frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frame)
  }, [target])
  return v
}

const SEV_STYLE: Record<string, string> = {
  critical: 'text-critical border-critical/30 bg-critical/5',
  warn: 'text-warn border-warn/30 bg-warn/5',
  info: 'text-neon border-neon/20 bg-neon/5',
}

export default function RiskPage() {
  const activeThreats = useCount(4)
  const avgRisk = useCount(62)
  const [selectedSrc, setSelectedSrc] = useState('ALL')

  const filtered = selectedSrc === 'ALL' ? OSINT_FEED : OSINT_FEED.filter(e => e.src === selectedSrc)

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert size={16} className="text-neon" />
            <h2 className="font-display text-2xl font-bold tracking-wider text-text">Risk Intelligence</h2>
          </div>
          <p className="text-[11px] tracking-widest text-muted">SENTINEL Agent — Multi-source threat detection, OSINT analysis & Green-Resilience correlation</p>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="bg-surface border border-critical/20 rounded-lg p-4">
          <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-1">Active Threats</p>
          <p className="font-mono text-3xl font-bold text-critical">{activeThreats}</p>
          <p className="text-[9px] text-muted mt-1">↑ 2 vs 4h ago</p>
        </div>
        <div className="bg-surface border border-warn/20 rounded-lg p-4">
          <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-1">Network Risk Index</p>
          <p className="font-mono text-3xl font-bold text-warn">{avgRisk}</p>
          <p className="text-[9px] text-muted mt-1">Scale 0–100 · ELEVATED</p>
        </div>
        <div className="bg-surface border border-border rounded-lg p-4">
          <p className="text-[9px] font-bold tracking-[0.25em] uppercase text-muted/60 mb-1">Hours Since Last Disruption</p>
          <p className="font-mono text-3xl font-bold text-neon">2.4</p>
          <p className="text-[9px] text-muted mt-1">Hamburg storm surge · GUARDIAN responded</p>
        </div>
      </div>

      {/* Main 2-column grid */}
      <div className="grid grid-cols-[1fr_380px] gap-4 mb-4">

        {/* Left: OSINT feed */}
        <div className="bg-surface border border-border rounded-lg overflow-hidden flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <div className="flex items-center gap-2">
              <Zap size={13} className="text-neon" />
              <span className="text-[11px] font-bold tracking-[0.15em] uppercase text-text">SENTINEL Signal Feed</span>
              <span className="h-1.5 w-1.5 rounded-full bg-neon animate-pulse" />
            </div>
            <div className="flex gap-1">
              {['ALL', 'SOCIAL', 'NEWS', 'FINANCIAL', 'WEATHER'].map(src => (
                <button key={src} onClick={() => setSelectedSrc(src)}
                  className={cn('px-2 py-0.5 rounded text-[8px] font-bold tracking-widest border transition-all',
                    selectedSrc === src ? 'border-neon/40 text-neon bg-neon/5' : 'border-border text-muted hover:text-text')}>
                  {src}
                </button>
              ))}
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {filtered.map(e => (
              <div key={e.id} className="flex gap-3 px-4 py-3 border-b border-border/40 hover:bg-neon/2 transition-colors">
                <span className="text-lg shrink-0 mt-0.5">{e.icon}</span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={cn('text-[8px] font-bold px-1.5 py-0.5 rounded border', SEV_STYLE[e.severity])}>{e.src}</span>
                    <span className="text-[8px] text-muted">{e.time}</span>
                    <span className="text-[8px] text-muted/50 ml-auto">{e.region}</span>
                  </div>
                  <p className={cn('text-[11px] font-bold mb-0.5', e.severity === 'critical' ? 'text-critical' : e.severity === 'warn' ? 'text-warn' : 'text-text')}>{e.title}</p>
                  <p className="text-[9px] text-muted/70 leading-relaxed">{e.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Node Risk Matrix */}
        <div className="bg-surface border border-border rounded-lg overflow-hidden flex flex-col">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
            <Activity size={13} className="text-neon" />
            <span className="text-[11px] font-bold tracking-[0.15em] uppercase text-text">Node Risk Matrix</span>
          </div>
          <div className="flex-1 overflow-y-auto">
            {NODE_RISK.map(n => {
              const riskPct = Math.round(n.riskScore * 100)
              const riskColor = riskPct > 45 ? 'text-critical' : riskPct > 25 ? 'text-warn' : 'text-neon'
              const barColor = riskPct > 45 ? 'bg-critical' : riskPct > 25 ? 'bg-warn' : 'bg-neon'
              return (
                <div key={n.id} className="flex items-center gap-3 px-4 py-2.5 border-b border-border/40 hover:bg-neon/2 transition-colors">
                  <div className="w-[110px] shrink-0">
                    <p className="text-[10px] font-bold text-text truncate">{n.name.replace('Port of ', '').replace(' DC', '').replace(' Hub', '')}</p>
                    <p className="text-[8px] text-muted uppercase">{n.type}</p>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="h-1 w-full rounded-full bg-border overflow-hidden">
                      <div className={cn('h-full rounded-full', barColor)} style={{ width: `${riskPct}%` }} />
                    </div>
                  </div>
                  <span className={cn('font-mono text-[11px] font-bold w-8 text-right shrink-0', riskColor)}>{riskPct}</span>
                  <div className="w-12 h-6 shrink-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={n.trend} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                        <Area type="monotone" dataKey="v" stroke={riskPct > 45 ? '#ef4444' : riskPct > 25 ? '#f5a623' : '#5ed29c'} strokeWidth={1} fill="transparent" dot={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                  <span className={cn('text-[8px] font-bold tracking-widest w-[52px] shrink-0 text-right', n.circuit_state === 'open' ? 'text-critical' : n.circuit_state === 'half_open' ? 'text-warn' : 'text-neon/50')}>
                    {n.circuit_state === 'open' ? 'OPEN' : n.circuit_state === 'half_open' ? 'HALF' : 'OK'}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Green-Resilience Scatter */}
      <div className="bg-surface border border-border rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <TrendingDown size={13} className="text-neon" />
            <span className="text-[11px] font-bold tracking-[0.15em] uppercase text-text">Green-Resilience Correlation</span>
            <span className="text-[8px] px-2 py-0.5 rounded border border-neon/20 bg-neon/5 text-neon">RL Insight</span>
          </div>
          <p className="text-[9px] text-muted">Higher carbon routes cluster in high-disruption zone — R² = 0.74</p>
        </div>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
              <XAxis dataKey="carbon" name="Carbon (kg CO₂/TEU)" tick={{ fontSize: 8, fill: 'oklch(55% 0.02 142)' }} label={{ value: 'Carbon Intensity (kg CO₂/TEU)', position: 'insideBottom', offset: -12, fontSize: 8, fill: 'oklch(55% 0.02 142)' }} />
              <YAxis dataKey="disruption" name="Disruption Risk" tick={{ fontSize: 8, fill: 'oklch(55% 0.02 142)' }} label={{ value: 'Disruption Risk', angle: -90, position: 'insideLeft', fontSize: 8, fill: 'oklch(55% 0.02 142)' }} />
              <Tooltip contentStyle={{ background: 'oklch(11% 0.015 142)', border: '1px solid oklch(20% 0.04 142)', borderRadius: 4, fontSize: 10 }} formatter={(v, n) => [v, n]} />
              <ReferenceLine stroke="oklch(20% 0.04 142)" strokeDasharray="3 3" x={1000} label={{ value: 'AIR', fontSize: 8, fill: 'oklch(55% 0.02 142)' }} />
              {['sea', 'rail', 'road', 'air'].map(mode => (
                <Scatter key={mode} name={mode} data={SCATTER_DATA.filter(d => d.mode === mode)} fill={MODE_COLOR[mode]} opacity={0.75} r={4} />
              ))}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center gap-4 mt-2">
          {['sea', 'rail', 'road', 'air'].map(m => (
            <div key={m} className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-full" style={{ background: MODE_COLOR[m] }} />
              <span className="text-[9px] text-muted uppercase">{m}</span>
            </div>
          ))}
          <p className="ml-auto text-[9px] text-neon/60">Sea routes: lowest carbon AND highest resilience — the RL agent's preferred choice</p>
        </div>
      </div>
    </DashboardLayout>
  )
}
