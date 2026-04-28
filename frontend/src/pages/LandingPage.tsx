import { useEffect, useState } from 'react'
import { ArrowRight, Menu, X, Zap, Shield, Network, TrendingUp, Radio, Users } from 'lucide-react'
import { Globe } from '@/components/ui/cobe-globe'

// ─── Supply-chain node markers ────────────────────────────────────────────────
const GLOBE_MARKERS = [
  { id: "hamburg",   location: [53.5753, 10.0153]   as [number, number], label: "Hamburg" },
  { id: "rotterdam", location: [51.9244, 4.4777]    as [number, number], label: "Rotterdam" },
  { id: "dubai",     location: [25.2048, 55.2708]   as [number, number], label: "Dubai" },
  { id: "singapore", location: [1.3521,  103.8198]  as [number, number], label: "Singapore" },
  { id: "shanghai",  location: [31.2304, 121.4737]  as [number, number], label: "Shanghai" },
  { id: "la",        location: [33.7295, -118.2625] as [number, number], label: "Los Angeles" },
  { id: "nyc",       location: [40.7128, -74.006]   as [number, number], label: "New York" },
  { id: "mumbai",    location: [19.0760, 72.8777]   as [number, number], label: "Mumbai" },
  { id: "joburg",    location: [-26.2041, 28.0473]  as [number, number], label: "Johannesburg" },
  { id: "saopaulo",  location: [-23.5505, -46.6333] as [number, number], label: "São Paulo" },
]

const GLOBE_ARCS = [
  { id: "sh-rot",  from: [31.2304,  121.4737] as [number, number], to: [51.9244,   4.4777]  as [number, number] },
  { id: "sh-la",   from: [31.2304,  121.4737] as [number, number], to: [33.7295, -118.2625] as [number, number] },
  { id: "dub-rot", from: [25.2048,   55.2708] as [number, number], to: [51.9244,   4.4777]  as [number, number] },
  { id: "mum-dub", from: [19.0760,   72.8777] as [number, number], to: [25.2048,  55.2708]  as [number, number] },
  { id: "sin-dub", from: [1.3521,   103.8198] as [number, number], to: [25.2048,  55.2708]  as [number, number] },
  { id: "nyc-rot", from: [40.7128,  -74.006]  as [number, number], to: [51.9244,   4.4777]  as [number, number] },
  { id: "sp-nyc",  from: [-23.5505, -46.6333] as [number, number], to: [40.7128,  -74.006]  as [number, number] },
  { id: "job-dub", from: [-26.2041,  28.0473] as [number, number], to: [25.2048,  55.2708]  as [number, number] },
]

// ─── Vertical grid lines ──────────────────────────────────────────────────────
function GridLines() {
  return (
    <div className="absolute inset-0 pointer-events-none hidden lg:block">
      {[25, 50, 75].map((pct) => (
        <div
          key={pct}
          className="absolute top-0 bottom-0 w-px"
          style={{ left: `${pct}%`, background: 'rgba(255,255,255,0.04)' }}
        />
      ))}
    </div>
  )
}

// ─── Ambient background glow ──────────────────────────────────────────────────
function BackgroundGlow() {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      {/* Top-right ambient — behind the globe */}
      <div
        className="absolute"
        style={{
          right: '-5%',
          top: '-10%',
          width: '65%',
          height: '65%',
          background: 'radial-gradient(ellipse at center, rgba(94,210,156,0.07) 0%, transparent 70%)',
        }}
      />
      {/* Left ambient — behind the headline */}
      <div
        className="absolute"
        style={{
          left: '-10%',
          top: '20%',
          width: '50%',
          height: '50%',
          background: 'radial-gradient(ellipse at center, rgba(94,210,156,0.04) 0%, transparent 70%)',
        }}
      />
    </div>
  )
}

// ─── Navigation ──────────────────────────────────────────────────────────────
const NAV_LINKS = ['SENTINEL', 'NAVIGATOR', 'GUARDIAN', 'STOCKPILE', 'ABOUT']

function Navigation({ menuOpen, setMenuOpen }: { menuOpen: boolean; setMenuOpen: (v: boolean) => void }) {
  return (
    <>
      <header className="absolute top-0 left-0 right-0 z-50 flex items-center justify-between px-6 lg:px-12 py-5">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="relative w-7 h-7">
            <svg viewBox="0 0 32 32" fill="none" className="w-full h-full">
              <rect x="1" y="1" width="30" height="30" rx="3" stroke="#5ed29c" strokeWidth="1.5" />
              <path d="M8 16 L14 10 L20 16 L14 22 Z" stroke="#5ed29c" strokeWidth="1.5" fill="none" />
              <circle cx="16" cy="16" r="2" fill="#5ed29c" />
              <line x1="20" y1="16" x2="26" y2="16" stroke="#5ed29c" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
          <span className="text-white font-bold tracking-[0.18em] text-[13px] uppercase" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
            NEXUS
          </span>
        </div>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-7">
          {NAV_LINKS.map((link) => (
            <a
              key={link}
              href="#"
              className="text-white/50 hover:text-[#5ed29c] text-[11px] font-mono tracking-[0.15em] transition-colors duration-200"
            >
              {link}
            </a>
          ))}
          <a
            href="/dashboard"
            className="text-[10px] font-mono font-bold tracking-widest uppercase px-4 py-2 rounded-full border border-[#5ed29c]/40 text-[#5ed29c] hover:bg-[#5ed29c] hover:text-[#070b0a] transition-all duration-200"
          >
            Control Tower →
          </a>
        </nav>

        {/* Mobile hamburger */}
        <button
          id="mobile-menu-btn"
          className="md:hidden text-white/70 hover:text-[#5ed29c] transition-colors"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle menu"
        >
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {/* Mobile full-screen overlay */}
      {menuOpen && (
        <div className="fixed inset-0 z-40 flex flex-col items-center justify-center gap-8 md:hidden" style={{ background: 'rgba(7,11,10,0.97)' }}>
          {NAV_LINKS.map((link) => (
            <a
              key={link}
              href="#"
              className="text-2xl font-mono tracking-widest text-white/60 hover:text-[#5ed29c] transition-colors"
              onClick={() => setMenuOpen(false)}
            >
              {link}
            </a>
          ))}
          <a
            href="/dashboard"
            className="mt-4 text-sm font-mono font-bold tracking-widest uppercase px-8 py-3 rounded-full bg-[#5ed29c] text-[#070b0a]"
            onClick={() => setMenuOpen(false)}
          >
            Control Tower
          </a>
        </div>
      )}
    </>
  )
}

// ─── Agent pills ──────────────────────────────────────────────────────────────
const AGENT_PILLS = [
  { icon: Shield,    label: 'SENTINEL',  desc: 'Risk Detection' },
  { icon: Network,   label: 'NAVIGATOR', desc: 'Dynamic Routing' },
  { icon: Zap,       label: 'GUARDIAN',  desc: 'Circuit Breaker' },
  { icon: TrendingUp,label: 'STOCKPILE', desc: 'Pre-Positioning' },
  { icon: Radio,     label: 'BROKER',    desc: 'Carrier Intel' },
  { icon: Users,     label: 'HERALD',    desc: 'Stakeholder Comms' },
]

// ─── Agent Cards Section ──────────────────────────────────────────────────────
const AGENT_DATA = [
  {
    id: 'SENTINEL',
    color: '#5ed29c',
    icon: '◈',
    role: 'Risk & Disruption Intelligence',
    desc: 'Scores every node, lane, and supplier for disruption probability up to 72 hours ahead — using dark signal OSINT and Gemini NLP.',
    badge: 'Early Warning',
    metric: '8h ahead of official alerts',
  },
  {
    id: 'NAVIGATOR',
    color: '#5ed29c',
    icon: '◉',
    role: 'Dynamic Routing Agent',
    desc: 'Pareto-optimal routing across time, cost, carbon footprint, and geopolitical risk simultaneously.',
    badge: 'Multi-Objective',
    metric: '4 objectives optimized live',
  },
  {
    id: 'GUARDIAN',
    color: '#f59e0b',
    icon: '◆',
    role: 'Circuit Breaker Agent',
    desc: "Isolates degrading infrastructure nodes before cascading failures propagate. Inspired by Netflix's Hystrix pattern.",
    badge: 'Cascade Prevention',
    metric: '2nd & 3rd order effects modeled',
  },
  {
    id: 'STOCKPILE',
    color: '#5ed29c',
    icon: '◇',
    role: 'Inventory Pre-Positioning',
    desc: 'Moves inventory before disruptions materialize. Triggers only when expected disruption cost exceeds transfer cost.',
    badge: 'Proactive',
    metric: '78% → 12% stockout probability',
  },
  {
    id: 'BROKER',
    color: '#60a5fa',
    icon: '◎',
    role: 'Carrier Intelligence Agent',
    desc: 'Maintains live health scores for every carrier — reliability, capacity, financial health — with Black-Scholes freight hedging.',
    badge: 'Financial Risk',
    metric: 'Dynamic blackout detection',
  },
  {
    id: 'HERALD',
    color: '#a78bfa',
    icon: '◐',
    role: 'Stakeholder Communication',
    desc: 'Right message, right person, right time. Behavioral nudge engine reduces operator override errors with psychology-aware framing.',
    badge: 'Behavioral AI',
    metric: '81% operator alignment rate',
  },
]

function AgentCard({ agent, index }: { agent: typeof AGENT_DATA[0]; index: number }) {
  return (
    <div
      className="group relative p-5 rounded-xl border border-white/8 hover:border-white/18 transition-all duration-300 cursor-default"
      style={{ background: 'rgba(255,255,255,0.02)', transitionDelay: `${index * 40}ms` }}
    >
      <div className="flex items-start justify-between mb-3">
        <span className="text-xl" style={{ color: agent.color }}>{agent.icon}</span>
        <span
          className="text-[8px] font-mono uppercase tracking-widest px-2 py-1 rounded-full border"
          style={{ color: agent.color, borderColor: `${agent.color}30`, background: `${agent.color}08` }}
        >
          {agent.badge}
        </span>
      </div>
      <div className="text-[10px] font-mono tracking-[0.2em] uppercase mb-1" style={{ color: agent.color }}>
        {agent.id}
      </div>
      <h3 className="text-sm font-semibold text-white/85 mb-2 leading-snug" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
        {agent.role}
      </h3>
      <p className="text-[11px] font-mono text-white/40 leading-relaxed mb-3">{agent.desc}</p>
      <div className="pt-3 border-t border-white/6">
        <span className="text-[9px] font-mono text-white/30 uppercase tracking-widest">↳ {agent.metric}</span>
      </div>
      <div
        className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{ boxShadow: `inset 0 0 28px ${agent.color}08` }}
      />
    </div>
  )
}

// ─── Main Landing Page ────────────────────────────────────────────────────────
export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setLoaded(true), 80)
    return () => clearTimeout(t)
  }, [])

  return (
    <div
      className="relative min-h-screen w-full overflow-x-hidden"
      style={{ background: '#070b0a', fontFamily: "'JetBrains Mono', monospace" }}
    >

      {/* Background layers */}
      <BackgroundGlow />
      <GridLines />

      {/* Nav */}
      <Navigation menuOpen={menuOpen} setMenuOpen={setMenuOpen} />

      {/* ── HERO ─────────────────────────────────────────────────────────── */}
      <main className="relative z-10 min-h-screen flex items-center">
        <div className="w-full pl-6 pr-4 lg:pl-12 lg:pr-12 pt-20 pb-12">
          <div className="flex flex-col lg:flex-row items-center gap-12 lg:gap-0">

            {/* Left: headline + copy + CTAs */}
            <div className="flex-1">

              {/* Eyebrow */}
              <div
                className="transition-all duration-700"
                style={{ opacity: loaded ? 1 : 0, transform: loaded ? 'none' : 'translateY(12px)' }}
              >
                <span
                  className="text-[10px] font-bold uppercase tracking-[0.28em]"
                  style={{ color: '#5ed29c' }}
                >
                  ◆ Proactive Supply Chain Intelligence
                </span>
              </div>

              {/* Main headline */}
              <div
                className="mt-5 transition-all duration-700 delay-100"
                style={{ opacity: loaded ? 1 : 0, transform: loaded ? 'none' : 'translateY(16px)' }}
              >
                <h1
                  className="font-black uppercase leading-[0.9] tracking-tight"
                  style={{
                    fontFamily: "'Syne', sans-serif",
                    fontSize: 'clamp(44px, 6.5vw, 80px)',
                    color: 'rgba(255,255,255,0.96)',
                  }}
                >
                  THE NERVOUS
                  <br />
                  SYSTEM FOR
                  <br />
                  GLOBAL TRADE
                  <span style={{ color: '#5ed29c' }}>.</span>
                </h1>
              </div>

              {/* Description */}
              <div
                className="mt-6 transition-all duration-700 delay-200"
                style={{ opacity: loaded ? 1 : 0, transform: loaded ? 'none' : 'translateY(12px)' }}
              >
                <p className="text-[13px] leading-relaxed max-w-md" style={{ color: 'rgba(255,255,255,0.52)' }}>
                  Six cooperative AI agents — SENTINEL, NAVIGATOR, GUARDIAN,
                  STOCKPILE, BROKER &amp; HERALD — predict, isolate, reroute, and
                  communicate around disruptions{' '}
                  <span style={{ color: 'rgba(255,255,255,0.82)' }}>before they cascade.</span>
                  {' '}Built on HAPPO multi-agent reinforcement learning and Google Cloud.
                </p>
              </div>

              {/* CTAs */}
              <div
                className="mt-8 flex flex-wrap items-center gap-4 transition-all duration-700 delay-300"
                style={{ opacity: loaded ? 1 : 0, transform: loaded ? 'none' : 'translateY(10px)' }}
              >
                <a
                  href="/dashboard"
                  id="cta-control-tower"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-full font-bold text-[11px] uppercase tracking-widest transition-all duration-200 hover:scale-105"
                  style={{
                    background: '#5ed29c',
                    color: '#070b0a',
                    boxShadow: '0 0 0 rgba(94,210,156,0)',
                    transition: 'transform 0.2s, box-shadow 0.3s',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 0 24px rgba(94,210,156,0.4)')}
                  onMouseLeave={e => (e.currentTarget.style.boxShadow = '0 0 0 rgba(94,210,156,0)')}
                >
                  Launch Control Tower <ArrowRight size={12} />
                </a>
                <a
                  href="#agents"
                  id="cta-agents"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-full font-bold text-[11px] uppercase tracking-widest border border-white/18 text-white/60 hover:border-[#5ed29c]/45 hover:text-[#5ed29c] transition-all duration-200"
                >
                  Meet the Agents
                </a>
              </div>

              {/* Agent pills */}
              <div
                className="flex flex-wrap gap-2 mt-8 transition-all duration-700 delay-400"
                style={{ opacity: loaded ? 1 : 0, transform: loaded ? 'none' : 'translateY(8px)' }}
              >
                {AGENT_PILLS.map(({ icon: Icon, label, desc }) => (
                  <div
                    key={label}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-white/8 hover:border-[#5ed29c]/35 transition-colors duration-300"
                    style={{ background: 'rgba(94,210,156,0.03)' }}
                  >
                    <Icon size={9} className="text-[#5ed29c]" />
                    <span className="text-[9px] font-mono text-white/45 uppercase tracking-widest">{label}</span>
                    <span className="text-[9px] font-mono text-white/25">·</span>
                    <span className="text-[9px] font-mono text-white/30">{desc}</span>
                  </div>
                ))}
              </div>

              {/* Stats row */}
              <div
                className="flex flex-wrap gap-8 mt-8 pt-7 border-t transition-all duration-700 delay-500"
                style={{
                  borderColor: 'rgba(255,255,255,0.07)',
                  opacity: loaded ? 1 : 0,
                  transform: loaded ? 'none' : 'translateY(8px)',
                }}
              >
                {[
                  { v: '6',   l: 'AI Agents' },
                  { v: '72h', l: 'Prediction Window' },
                  { v: '0',   l: 'SLA Breaches' },
                  { v: '12T', l: 'CO₂ Saved (kg eq.)' },
                ].map(({ v, l }) => (
                  <div key={l}>
                    <div className="text-xl font-bold" style={{ color: '#5ed29c' }}>{v}</div>
                    <div className="text-[9px] font-mono text-white/35 uppercase tracking-widest mt-0.5">{l}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: Globe */}
            <div
              className="relative flex-shrink-0 w-full lg:w-[52%] xl:w-[54%] flex items-center justify-center transition-all duration-1000 delay-200"
              style={{ opacity: loaded ? 1 : 0 }}
            >
              {/* Glow behind globe */}
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background: 'radial-gradient(ellipse at center, rgba(94,210,156,0.1) 0%, transparent 65%)',
                }}
              />

              {/* Outer ring */}
              <div
                className="absolute rounded-full border pointer-events-none"
                style={{
                  inset: '-2%',
                  borderColor: 'rgba(94,210,156,0.08)',
                }}
              />

              {/* Live status badge */}
              <div
                className="absolute top-4 right-4 z-20 flex items-center gap-1.5 px-3 py-1.5 rounded-full border"
                style={{ background: 'rgba(7,11,10,0.8)', borderColor: 'rgba(94,210,156,0.2)', backdropFilter: 'blur(8px)' }}
              >
                <div className="w-1.5 h-1.5 rounded-full bg-[#5ed29c] animate-pulse" />
                <span className="text-[9px] font-mono text-[#5ed29c]/70 uppercase tracking-widest">Live Network</span>
              </div>

              {/* Shipment count badge */}
              <div
                className="absolute bottom-4 left-4 z-20 px-3 py-1.5 rounded-full border"
                style={{ background: 'rgba(7,11,10,0.8)', borderColor: 'rgba(255,255,255,0.08)', backdropFilter: 'blur(8px)' }}
              >
                <span className="text-[9px] font-mono text-white/40 uppercase tracking-widest">30 Active Shipments</span>
              </div>

              <Globe
                markers={GLOBE_MARKERS}
                arcs={GLOBE_ARCS}
                className="w-full max-w-[540px] lg:max-w-none"
                dark={1}
                mapBrightness={5}
                baseColor={[0.04, 0.07, 0.05]}
                markerColor={[0.37, 0.82, 0.61]}
                arcColor={[0.37, 0.82, 0.61]}
                glowColor={[0.12, 0.3, 0.2]}
                speed={0.002}
                theta={0.25}
                diffuse={1.1}
                arcHeight={0.32}
                arcWidth={0.9}
                markerSize={0.032}
              />
            </div>
          </div>
        </div>
      </main>

      {/* ── AGENTS SECTION ───────────────────────────────────────────────── */}
      <section
        id="agents"
        className="relative z-10 py-24 px-6 lg:px-12 xl:px-16 border-t"
        style={{ background: 'rgba(7,11,10,0.98)', borderColor: 'rgba(255,255,255,0.05)' }}
      >
        <div className="max-w-screen-xl mx-auto">
          <div className="mb-14">
            <span className="text-[10px] font-mono tracking-[0.3em] uppercase" style={{ color: 'rgba(94,210,156,0.65)' }}>
              The Architecture
            </span>
            <h2
              className="mt-3 font-black uppercase tracking-tight"
              style={{
                fontFamily: "'Syne', sans-serif",
                fontSize: 'clamp(32px, 4vw, 52px)',
                color: 'rgba(255,255,255,0.92)',
              }}
            >
              Six Specialized Agents<span style={{ color: '#5ed29c' }}>.</span>
            </h2>
            <p className="mt-3 text-[12px] font-mono text-white/45 max-w-lg leading-relaxed">
              Centralized Training, Decentralized Execution (CTDE). Each agent governs a distinct
              decision domain. Together they form a self-healing supply chain intelligence system.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {AGENT_DATA.map((agent, i) => (
              <AgentCard key={agent.id} agent={agent} index={i} />
            ))}
          </div>
        </div>
      </section>

      {/* ── FOOTER STRIP ─────────────────────────────────────────────────── */}
      <section
        className="relative z-10 py-16 px-6 lg:px-12 xl:px-16 border-t"
        style={{ borderColor: 'rgba(255,255,255,0.05)' }}
      >
        <div className="max-w-screen-xl mx-auto flex flex-col lg:flex-row items-start lg:items-center justify-between gap-10">
          <div>
            <span className="text-[10px] font-mono tracking-[0.3em] uppercase" style={{ color: 'rgba(94,210,156,0.65)' }}>
              Mission
            </span>
            <h3
              className="mt-3 font-black uppercase tracking-tight"
              style={{ fontFamily: "'Syne', sans-serif", fontSize: 'clamp(26px, 3vw, 38px)', color: 'rgba(255,255,255,0.9)' }}
            >
              Resilience is Sustainability<span style={{ color: '#5ed29c' }}>.</span>
            </h3>
            <p className="mt-3 text-[12px] font-mono text-white/45 max-w-lg leading-relaxed">
              The greenest shipping routes are also the most resilient. NEXUS proves this
              with data and encodes it into every routing decision — aligning SDGs 9, 11, 13 &amp; 17.
            </p>
          </div>
          <div className="flex flex-col items-start lg:items-end gap-3">
            <a
              href="/dashboard"
              className="inline-flex items-center gap-2 px-7 py-3.5 rounded-full font-bold text-[11px] uppercase tracking-widest transition-all duration-200 hover:scale-105"
              style={{ background: '#5ed29c', color: '#070b0a', fontFamily: "'JetBrains Mono', monospace" }}
              onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 0 28px rgba(94,210,156,0.38)')}
              onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
            >
              Enter the Control Tower <ArrowRight size={12} />
            </a>
            <p className="text-[9px] font-mono text-white/20 tracking-widest">
              HAPPO · PettingZoo · Cloud Run · Firebase · Gemini API · Google Maps
            </p>
            <p className="text-[9px] font-mono tracking-widest" style={{ color: 'rgba(94,210,156,0.35)' }}>
              Google Solutions Challenge 2026 · UN SDG 9 · 11 · 13 · 17
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}
