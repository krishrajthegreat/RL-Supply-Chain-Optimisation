import { type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  Brain,
  Orbit,
  BarChart3,
  Bell,
  Settings,
  FileText,
  Terminal,
  Cog,
} from 'lucide-react'
import { cn } from '@/lib/utils'

/* ── RL sidebar navigation ── */
const RL_NAV = [
  { label: 'Agent Training',    to: '/rl-optimizer/training',    icon: Brain },
  { label: 'Environment State', to: '/rl-optimizer',             icon: Orbit },
  { label: 'Policy Analytics',  to: '/rl-optimizer/policy',      icon: BarChart3 },
] as const

const RL_BOTTOM = [
  { label: 'Documentation', to: '/rl-optimizer/docs', icon: FileText },
  { label: 'System Logs',   to: '/rl-optimizer/logs', icon: Terminal },
] as const

/* ── Top bar tabs ── */
const TOP_TABS = ['TRAINING', 'INFERENCE', 'EXPLORATION'] as const

/* ──────────────────────────────────────────────────────────────
   RLLayout
   Full-width top navbar with tabs + narrow left sidebar + content
   Distinct visual identity from DashboardLayout
   ────────────────────────────────────────────────────────────── */
export default function RLLayout({ children }: { children: ReactNode }) {
  const location = useLocation()

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-bg">
      {/* ─── Top navbar (full-width) ─── */}
      <header className="flex h-12 shrink-0 items-center border-b border-border bg-bg px-5">
        {/* Brand */}
        <h1 className="font-display text-base font-bold tracking-wider text-neon mr-8">
          RL-SC_OPTIMIZER
        </h1>

        {/* Center tabs */}
        <nav className="flex items-center gap-6">
          {TOP_TABS.map((tab) => {
            // "EXPLORATION" is active for the main /rl-optimizer route
            const active = tab === 'EXPLORATION'
            return (
              <button
                key={tab}
                className={cn(
                  'relative pb-0.5 text-[12px] font-semibold tracking-[0.2em] transition-colors duration-150',
                  active
                    ? 'text-neon'
                    : 'text-muted hover:text-text'
                )}
              >
                {tab}
                {active && (
                  <span className="absolute -bottom-[9px] left-0 h-[2px] w-full bg-neon" />
                )}
              </button>
            )
          })}
        </nav>

        {/* Right actions */}
        <div className="ml-auto flex items-center gap-3">
          <button
            id="rl-btn-notifications"
            aria-label="Notifications"
            className="flex h-8 w-8 items-center justify-center rounded-sm text-muted transition-colors hover:text-neon"
          >
            <Bell size={16} />
          </button>
          <button
            id="rl-btn-settings"
            aria-label="Settings"
            className="flex h-8 w-8 items-center justify-center rounded-sm text-muted transition-colors hover:text-neon"
          >
            <Settings size={16} />
          </button>
          <div className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface">
            <span className="text-[10px] font-bold text-muted">RL</span>
          </div>
        </div>
      </header>

      {/* ─── Below the top bar: sidebar + content ─── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <aside className="flex w-[200px] shrink-0 flex-col border-r border-border bg-bg pt-5">
          {/* Node identity block */}
          <div className="px-4 pb-5">
            {/* Gear icon in neon box */}
            <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-md bg-neon">
              <Cog size={18} className="text-bg" />
            </div>
            <p className="text-[11px] font-bold tracking-widest text-text/80">
              NODE_RL_01
            </p>
            <p className="mt-0.5 text-[10px] tracking-widest text-muted">
              STATUS: OPTIMIZING
            </p>
          </div>

          {/* Main nav */}
          <nav className="flex-1 space-y-0.5 px-3">
            {RL_NAV.map(({ label, to, icon: Icon }) => {
              const active = location.pathname === to
              return (
                <NavLink
                  key={to}
                  to={to}
                  className={cn(
                    'group flex items-center gap-2.5 rounded-sm px-3 py-2 text-[12px] font-medium transition-colors duration-150',
                    active
                      ? 'border-l-[3px] border-neon bg-surface text-neon'
                      : 'border-l-[3px] border-transparent text-muted hover:text-neon/80'
                  )}
                >
                  <Icon
                    size={15}
                    className={cn(
                      'shrink-0 transition-colors duration-150',
                      active ? 'text-neon' : 'text-muted group-hover:text-neon/80'
                    )}
                  />
                  {label}
                </NavLink>
              )
            })}
          </nav>

          {/* Bottom links */}
          <div className="space-y-0.5 border-t border-border px-3 py-3">
            {RL_BOTTOM.map(({ label, to, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className="group flex items-center gap-2.5 rounded-sm px-3 py-2 text-[11px] text-muted transition-colors duration-150 hover:text-neon/80"
              >
                <Icon
                  size={14}
                  className="shrink-0 text-muted transition-colors group-hover:text-neon/80"
                />
                {label}
              </NavLink>
            ))}
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
