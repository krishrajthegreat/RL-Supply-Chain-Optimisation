import { type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Globe,
  Ship,
  Package,
  Settings,
  Search,
  Bell,
  Radio,
} from 'lucide-react'
import { cn } from '@/lib/utils'

/* ── Navigation definition ── */
const NAV_ITEMS = [
  { label: 'Dashboard',        to: '/dashboard',        icon: LayoutDashboard },
  { label: 'Global Map',       to: '/global-map',       icon: Globe },
  { label: 'Fleet Analytics',  to: '/fleet-analytics',  icon: Ship },
  { label: 'Cargo Operations', to: '/cargo-operations', icon: Package },
  { label: 'System Settings',  to: '/system-settings',  icon: Settings },
] as const

/* ──────────────────────────────────────────────────────────────
   DashboardLayout
   Fixed sidebar (250 px) + top navbar + scrollable content area
   ────────────────────────────────────────────────────────────── */
export default function DashboardLayout({ children }: { children: ReactNode }) {
  const location = useLocation()

  return (
    <div className="flex h-dvh overflow-hidden bg-bg">
      {/* ─── Sidebar ─── */}
      <aside className="flex w-[250px] shrink-0 flex-col border-r border-border bg-bg">
        {/* Brand block */}
        <div className="px-5 pt-5 pb-4">
          <h1 className="font-display text-lg font-bold tracking-wider text-neon">
            CYBER LOGISTICS
          </h1>
        </div>

        {/* Command header */}
        <div className="px-5 pb-6">
          <p className="text-xs font-bold tracking-widest text-text/80">
            COMMAND_OPS
          </p>
          <p className="mt-0.5 text-[10px] tracking-widest text-muted">
            SYS_SECURE_ENCRYPTED
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
                  'group flex items-center gap-3 rounded-sm px-3 py-2.5 text-[13px] font-medium transition-colors duration-150',
                  active
                    ? 'border-l-[3px] border-neon bg-surface text-neon'
                    : 'border-l-[3px] border-transparent text-muted hover:text-neon/80'
                )}
              >
                <Icon
                  size={16}
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

        {/* Bottom status */}
        <div className="flex items-center gap-2 border-t border-border px-5 py-4">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-pulse-glow rounded-full bg-neon" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-neon" />
          </span>
          <span className="text-[11px] tracking-widest text-muted">
            NODE_STATUS: ONLINE
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
              size={14}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted"
            />
            <input
              id="search-systems"
              type="text"
              placeholder="Search systems..."
              className="h-8 w-full rounded-sm border border-border bg-surface pl-8 pr-3 text-xs text-text placeholder:text-muted focus:border-neon-dim focus:outline-none"
            />
          </div>

          <div className="ml-auto flex items-center gap-3">
            {/* Bell icon */}
            <button
              id="btn-notifications"
              aria-label="Notifications"
              className="flex h-8 w-8 items-center justify-center rounded-sm text-muted transition-colors hover:text-neon"
            >
              <Bell size={16} />
            </button>

            {/* Broadcast/signal icon */}
            <button
              id="btn-broadcast"
              aria-label="Broadcast"
              className="flex h-8 w-8 items-center justify-center rounded-sm text-muted transition-colors hover:text-neon"
            >
              <Radio size={16} />
            </button>

            {/* System ready pill */}
            <div className="flex items-center gap-1.5 rounded-sm border border-neon px-3 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-neon" />
              <span className="text-[11px] font-bold tracking-widest text-neon">
                SYSTEM_READY
              </span>
            </div>

            {/* Avatar placeholder */}
            <div className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface">
              <span className="text-[10px] font-bold text-muted">SU</span>
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
