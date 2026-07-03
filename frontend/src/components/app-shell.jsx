import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Bot,
  Database,
  Github,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Settings,
  SquarePen,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { checkHealth, fetchAuthStatus, listTasks, logout, startGitHubLogin } from '@/api/client'
import { useAuthStore } from '@/store/auth'
import { ThemeToggle } from '@/components/theme-toggle'
import { Button, buttonVariants } from '@/components/ui/button'

const nav = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/submit', label: 'Submit Issue', icon: SquarePen },
  { href: '/tasks', label: 'Tasks', icon: ListChecks },
  { href: '/repositories', label: 'Repositories', icon: Database },
  { href: '/settings', label: 'Settings', icon: Settings },
]

function isActive(pathname, href) {
  if (href === '/') return pathname === '/'
  return pathname === href || pathname.startsWith(`${href}/`)
}

function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <Bot className="size-5" />
      </span>
      <div className="flex flex-col leading-none">
        <span className="text-sm font-semibold tracking-tight">Issue Resolver</span>
        <span className="text-[11px] text-muted-foreground">Autonomous agents</span>
      </div>
    </Link>
  )
}

function NavLinks({ pathname, runningCount, onNavigate }) {
  return (
    <nav className="flex flex-col gap-1">
      {nav.map((item) => {
        const active = isActive(pathname, item.href)
        const Icon = item.icon
        return (
          <Link
            key={item.href}
            to={item.href}
            onClick={onNavigate}
            className={cn(
              'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              active
                ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground',
            )}
          >
            <Icon
              className={cn(
                'size-4 shrink-0',
                active ? 'text-primary' : 'text-muted-foreground',
              )}
            />
            <span className="flex-1">{item.label}</span>
            {item.href === '/tasks' && runningCount > 0 && (
              <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary/15 px-1.5 text-xs font-medium text-primary">
                {runningCount}
              </span>
            )}
          </Link>
        )
      })}
    </nav>
  )
}

function SidebarInner({ pathname, runningCount, healthOk, onNavigate, user, oauthEnabled, onLogout }) {
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="px-2 pt-2">
        <Brand />
      </div>
      <div className="flex-1">
        <NavLinks pathname={pathname} runningCount={runningCount} onNavigate={onNavigate} />
      </div>
      {oauthEnabled && (
        <div className="rounded-lg border border-border bg-card p-3">
          {user ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt="" className="size-7 rounded-full" />
                ) : (
                  <Github className="size-5 text-muted-foreground" />
                )}
                <span className="truncate text-sm font-medium">{user.login}</span>
              </div>
              <Button variant="ghost" size="sm" className="w-full justify-start gap-2" onClick={onLogout}>
                <LogOut className="size-3.5" />
                Sign out
              </Button>
            </div>
          ) : (
            <Button variant="outline" size="sm" className="w-full gap-2" onClick={startGitHubLogin}>
              <Github className="size-3.5" />
              Sign in with GitHub
            </Button>
          )}
        </div>
      )}
      <div className="rounded-lg border border-border bg-card p-3">
        <div className="flex items-center gap-2 text-xs font-medium text-foreground">
          <span
            className={cn(
              'size-2 rounded-full',
              healthOk ? 'bg-success' : 'animate-pulse bg-destructive',
            )}
          />
          {healthOk ? 'All systems operational' : 'API unreachable'}
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
          {healthOk
            ? 'Agent workers online. Vector index ready.'
            : 'Check Settings or start the backend.'}
        </p>
      </div>
    </div>
  )
}

function MobileSheet({ open, onClose, children }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <button
        type="button"
        className="absolute inset-0 bg-black/40 backdrop-blur-xs"
        aria-label="Close navigation"
        onClick={onClose}
      />
      <div className="absolute inset-y-0 left-0 w-72 border-r border-border bg-sidebar shadow-lg">
        <Button
          variant="ghost"
          size="icon-sm"
          className="absolute top-3 right-3"
          onClick={onClose}
          aria-label="Close"
        >
          <X className="size-4" />
        </Button>
        {children}
      </div>
    </div>
  )
}

export function AppShell({ children }) {
  const pathname = useLocation().pathname
  const [open, setOpen] = useState(false)
  const [healthOk, setHealthOk] = useState(false)
  const [runningCount, setRunningCount] = useState(0)
  const user = useAuthStore((s) => s.user)
  const oauthEnabled = useAuthStore((s) => s.oauthEnabled)

  async function handleLogout() {
    await logout()
  }

  useEffect(() => {
    fetchAuthStatus()
  }, [])

  useEffect(() => {
    let cancelled = false
    async function poll() {
      try {
        await checkHealth()
        if (!cancelled) setHealthOk(true)
        const tasks = await listTasks()
        if (!cancelled) {
          setRunningCount(
            tasks.filter((t) => t.status === 'running' || t.status === 'queued').length,
          )
        }
      } catch {
        if (!cancelled) setHealthOk(false)
      }
    }
    poll()
    const id = setInterval(poll, 15000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return (
    <div className="flex min-h-svh bg-background">
      <aside className="hidden w-64 shrink-0 border-r border-border bg-sidebar lg:block">
        <div className="sticky top-0 h-svh">
          <SidebarInner
            pathname={pathname}
            runningCount={runningCount}
            healthOk={healthOk}
            user={user}
            oauthEnabled={oauthEnabled}
            onLogout={handleLogout}
          />
        </div>
      </aside>

      <MobileSheet open={open} onClose={() => setOpen(false)}>
        <SidebarInner
          pathname={pathname}
          runningCount={runningCount}
          healthOk={healthOk}
          onNavigate={() => setOpen(false)}
          user={user}
          oauthEnabled={oauthEnabled}
          onLogout={handleLogout}
        />
      </MobileSheet>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur-sm lg:px-6">
          <Button
            variant="ghost"
            size="icon-sm"
            className="lg:hidden"
            aria-label="Open navigation"
            onClick={() => setOpen(true)}
          >
            <Menu className="size-5" />
          </Button>

          <div className="lg:hidden">
            <Brand />
          </div>

          <div className="ml-auto flex items-center gap-2">
            <Link to="/submit" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), 'hidden sm:inline-flex')}>
              <SquarePen className="size-3.5" />
              New task
            </Link>
            <ThemeToggle />
          </div>
        </header>

        <main className="flex-1">{children}</main>
      </div>
    </div>
  )
}
