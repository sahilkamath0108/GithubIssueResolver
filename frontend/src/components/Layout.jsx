import { Link, useLocation } from 'react-router-dom'
import {
  Bot,
  Database,
  LayoutDashboard,
  ListTodo,
  PlusCircle,
  Settings,
} from 'lucide-react'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/submit', label: 'Resolve Issue', icon: PlusCircle },
  { to: '/tasks', label: 'Tasks', icon: ListTodo },
  { to: '/index', label: 'Index Repo', icon: Database },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Layout({ children, healthOk }) {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-grid">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(99,102,241,0.12),transparent_50%)]" />

      <div className="relative mx-auto flex min-h-screen max-w-7xl">
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-[var(--color-border)] bg-[#0a0d12]/80 p-5 backdrop-blur-xl lg:flex">
          <Link to="/" className="mb-8 flex items-center gap-3 px-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 shadow-lg shadow-indigo-900/40">
              <Bot className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">Issue Resolver</p>
              <p className="text-xs text-[var(--color-muted)]">Multi-agent workflow</p>
            </div>
          </Link>

          <nav className="flex flex-1 flex-col gap-1">
            {NAV.map(({ to, label, icon: Icon }) => {
              const active = location.pathname === to
              return (
                <Link
                  key={to}
                  to={to}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                    active
                      ? 'bg-indigo-600/20 text-indigo-200 ring-1 ring-indigo-500/30'
                      : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              )
            })}
          </nav>

          <div className="mt-auto rounded-lg border border-[var(--color-border)] bg-[#12161f] p-3">
            <div className="flex items-center gap-2 text-xs">
              <span
                className={`h-2 w-2 rounded-full ${healthOk ? 'bg-emerald-400' : 'bg-red-400 animate-pulse-dot'}`}
              />
              <span className="text-[var(--color-muted)]">
                API {healthOk ? 'connected' : 'offline'}
              </span>
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--color-border)] bg-[#0c0f14]/90 px-4 py-3 backdrop-blur-xl lg:hidden">
            <Link to="/" className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-indigo-400" />
              <span className="font-semibold text-white">Issue Resolver</span>
            </Link>
            <span
              className={`h-2 w-2 rounded-full ${healthOk ? 'bg-emerald-400' : 'bg-red-400'}`}
            />
          </header>

          <nav className="flex gap-1 overflow-x-auto border-b border-[var(--color-border)] px-4 py-2 lg:hidden">
            {NAV.map(({ to, label }) => (
              <Link
                key={to}
                to={to}
                className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium ${
                  location.pathname === to
                    ? 'bg-indigo-600/25 text-indigo-200'
                    : 'text-slate-500'
                }`}
              >
                {label}
              </Link>
            ))}
          </nav>

          <main className="flex-1 p-4 pb-10 md:p-8">{children}</main>
        </div>
      </div>
    </div>
  )
}
