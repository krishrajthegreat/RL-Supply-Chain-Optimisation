import { type ReactNode } from 'react'
import { NavLink, Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Globe,
  PackageSearch,
  ShieldAlert,
  LineChart,
  Truck,
  Network,
  BrainCircuit,
  Search,
  Bell,
  Radio,
} from 'lucide-react'
import { cn } from '@/lib/utils'

/* ── Navigation definition ── */
const NAV_ITEMS = [
  { label: 'Dashboard',          to: '/dashboard',   icon: LayoutDashboard },
  { label: 'Global Map',         to: '/global-map',  icon: Globe },
  { label: 'RL Optimizer',       to: '/rl-optimizer',icon: BrainCircuit },
  { label: 'Shipment Tracker',   to: '/shipments',   icon: PackageSearch },
  { label: 'Risk Intelligence',  to: '/risk',        icon: ShieldAlert },
  { label: 'Executive Insights', to: '/insights',    icon: LineChart },
  { label: 'Fleet & Carriers',   to: '/fleet',       icon: Truck },
  { label: 'Network Resilience', to: '/resilience',  icon: Network },
] as const

/* ──────────────────────────────────────────────────────────────
   DashboardLayout
   Fixed sidebar (240 px) + top navbar + scrollable content area
   ────────────────────────────────────────────────────────────── */
export default function DashboardLayout({ children }: { children: ReactNode }) {
  const location = useLocation()

  return (
    <div className="flex h-dvh overflow-hidden bg-bg">
      {/* ─── Sidebar ─── */}
      <aside className="flex w-[240px] shrink-0 flex-col border-r border-border bg-bg">

        {/* Brand block — matches landing page logo */}
        <Link to="/" className="flex items-center gap-3 px-5 pt-6 pb-5 border-b border-border hover:bg-white/5 transition-colors">
          <div className="relative w-6 h-6 shrink-0">
            <svg viewBox="0 0 32 32" fill="none" className="w-full h-full">
              <rect x="1" y="1" width="30" height="30" rx="3" stroke="oklch(85% 0.35 142)" strokeWidth="1.5" />
              <path d="M8 16 L14 10 L20 16 L14 22 Z" stroke="oklch(85% 0.35 142)" strokeWidth="1.5" fill="none" />
              <circle cx="16" cy="16" r="2" fill="oklch(85% 0.35 142)" />
              <line x1="20" y1="16" x2="26" y2="16" stroke="oklch(85% 0.35 142)" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <h1 className="font-display text-[13px] font-bold tracking-[0.18em] text-neon uppercase leading-none">
              NEXUS
            </h1>
            <p className="text-[7.5px] tracking-[0.05em] text-muted uppercase mt-1 leading-tight">
              Proactive Supply<br/>Chain Intelligence
            </p>
          </div>
        </Link>

        {/* Section label */}
        <div className="px-5 pt-5 pb-2">
          <p className="text-[9px] font-bold tracking-[0.28em] uppercase text-muted/50">
            Navigation
          </p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-0.5 px-3">
          {NAV_ITEMS.map(({ label, to, icon: Icon }) => {
            const active = location.pathname === to
            return (
              <NavLink
                key={to}
                to={to}
                className={cn(
                  'group flex items-center gap-3 rounded-md px-3 py-2.5 text-[12px] font-medium tracking-wide transition-all duration-150',
                  active
                    ? 'bg-neon/8 text-neon border border-neon/20'
                    : 'border border-transparent text-muted hover:text-neon/80 hover:bg-neon/4'
                )}
              >
                <Icon
                  size={14}
                  className={cn(
                    'shrink-0 transition-colors duration-150',
                    active ? 'text-neon' : 'text-muted group-hover:text-neon/80'
                  )}
                />
                {label}
                {active && (
                  <span className="ml-auto h-1 w-1 rounded-full bg-neon" />
                )}
              </NavLink>
            )
          })}
        </nav>

        {/* Section label — agents */}
        <div className="px-5 pt-4 pb-2">
          <p className="text-[9px] font-bold tracking-[0.28em] uppercase text-muted/50">
            Active Agents
          </p>
        </div>

        {/* Agent status pills */}
        <div className="px-4 pb-4 space-y-1">
          {[
            { id: 'SENTINEL', color: 'text-neon' },
            { id: 'NAVIGATOR', color: 'text-neon' },
            { id: 'GUARDIAN', color: 'text-warn' },
          ].map(({ id, color }) => (
            <div
              key={id}
              className="flex items-center justify-between px-3 py-1.5 rounded-md border border-border/60"
              style={{ background: 'rgba(255,255,255,0.01)' }}
            >
              <span className={`text-[10px] font-bold tracking-[0.18em] ${color}`}>{id}</span>
              <span className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-neon animate-pulse" />
                <span className="text-[9px] tracking-widest text-muted">LIVE</span>
              </span>
            </div>
          ))}
        </div>

        {/* Bottom node status */}
        <div className="flex items-center gap-2 border-t border-border px-5 py-4">
          <span className="relative flex h-2 w-2 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-pulse-glow rounded-full bg-neon" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-neon" />
          </span>
          <span className="text-[10px] tracking-[0.16em] text-muted uppercase">
            System Online
          </span>
        </div>
      </aside>

      {/* ─── Right column ─── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top navbar */}
        <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-bg px-6">
          {/* Search */}
          <div className="relative flex-1 max-w-xs">
            <Search
              size={13}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
            />
            <input
              id="search-systems"
              type="text"
              placeholder="Search systems..."
              className="h-8 w-full rounded-md border border-border bg-surface pl-8 pr-3 text-[11px] tracking-wide text-text placeholder:text-muted focus:border-neon/40 focus:outline-none transition-colors"
            />
          </div>

          <div className="ml-auto flex items-center gap-3">
            {/* Notifications */}
            <button
              id="btn-notifications"
              aria-label="Notifications"
              className="flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-muted transition-all hover:text-neon hover:border-border"
            >
              <Bell size={15} />
            </button>

            {/* Broadcast */}
            <button
              id="btn-broadcast"
              aria-label="Broadcast"
              className="flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-muted transition-all hover:text-neon hover:border-border"
            >
              <Radio size={15} />
            </button>

            {/* System ready pill — matches landing page CTA style */}
            <div className="flex items-center gap-1.5 rounded-full border border-neon/35 px-3 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-neon animate-pulse" />
              <span className="text-[10px] font-bold tracking-[0.18em] uppercase text-neon">
                All Systems Go
              </span>
            </div>

            {/* Avatar */}
            <div className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface hover:border-neon/30 transition-colors">
              <span className="text-[10px] font-bold tracking-wider text-muted">SU</span>
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
