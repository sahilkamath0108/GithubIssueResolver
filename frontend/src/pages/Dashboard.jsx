import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Database,
  GitPullRequest,
  PlusCircle,
  Sparkles,
} from 'lucide-react'
import { checkHealth, listTasks } from '../api/client'
import Card, { CardHeader } from '../components/Card'
import StatusBadge from '../components/StatusBadge'
import Button from '../components/Button'

function StatCard({ label, value, accent }) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[#12161f]/80 p-4">
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted)]">
        {label}
      </p>
      <p className={`mt-2 text-3xl font-bold tabular-nums ${accent}`}>{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [healthOk, setHealthOk] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        await checkHealth()
        if (!cancelled) setHealthOk(true)
        const data = await listTasks()
        if (!cancelled) setTasks(Array.isArray(data) ? data : [])
      } catch {
        if (!cancelled) setHealthOk(false)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const sorted = [...tasks].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at),
  )
  const recent = sorted.slice(0, 6)
  const counts = tasks.reduce(
    (acc, t) => {
      acc[t.status] = (acc[t.status] || 0) + 1
      return acc
    },
    {},
  )

  return (
    <div className="animate-fade-in space-y-8">
      <section>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 flex items-center gap-2 text-sm text-indigo-300/80">
              <Sparkles className="h-4 w-4" />
              Autonomous GitHub issue resolution
            </p>
            <h1 className="text-3xl font-bold tracking-tight text-white md:text-4xl">
              Welcome to <span className="gradient-text">Issue Resolver</span>
            </h1>
            <p className="mt-3 max-w-2xl text-[var(--color-muted)]">
              Index a repository, submit a GitHub issue, and let agents plan, search your
              codebase, write fixes, and open a pull request — no Swagger required.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link to="/submit">
              <Button>
                <PlusCircle className="h-4 w-4" />
                Resolve issue
              </Button>
            </Link>
            <Link to="/index">
              <Button variant="secondary">
                <Database className="h-4 w-4" />
                Index repo
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total tasks" value={tasks.length} accent="text-white" />
        <StatCard
          label="Running"
          value={counts.running || 0}
          accent="text-indigo-300"
        />
        <StatCard
          label="Succeeded"
          value={counts.success || 0}
          accent="text-emerald-400"
        />
        <StatCard label="Failed" value={counts.failed || 0} accent="text-red-400" />
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2" glow>
          <CardHeader
            title="Recent tasks"
            subtitle="Latest workflow runs across your repositories"
            action={
              <Link to="/tasks" className="text-sm text-indigo-300 hover:text-indigo-200">
                View all →
              </Link>
            }
          />

          {loading ? (
            <p className="text-sm text-[var(--color-muted)]">Loading tasks…</p>
          ) : recent.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--color-border)] p-8 text-center">
              <p className="text-[var(--color-muted)]">No tasks yet.</p>
              <Link to="/submit" className="mt-4 inline-block">
                <Button variant="secondary">Submit your first issue</Button>
              </Link>
            </div>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {recent.map((task) => (
                <li key={task.uuid}>
                  <Link
                    to={`/tasks/${task.uuid}`}
                    className="flex flex-wrap items-center justify-between gap-3 py-4 transition hover:bg-white/[0.02] -mx-2 px-2 rounded-lg"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-white">
                        {task.issue_url?.replace('https://github.com/', '') || 'Issue'}
                      </p>
                      <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                        {task.current_step || '—'} ·{' '}
                        {new Date(task.created_at).toLocaleString()}
                      </p>
                    </div>
                    <StatusBadge status={task.status} pulse />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader
            title="How it works"
            subtitle="Three steps to an automated PR"
          />
          <ol className="space-y-4">
            {[
              { step: '1', text: 'Index your repo into Qdrant via GitHub API' },
              { step: '2', text: 'Submit a GitHub issue URL matching that repo' },
              { step: '3', text: 'Agents plan, search, patch, test, and open a PR' },
            ].map(({ step, text }) => (
              <li key={step} className="flex gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-600/20 text-xs font-bold text-indigo-300 ring-1 ring-indigo-500/30">
                  {step}
                </span>
                <p className="text-sm text-slate-300">{text}</p>
              </li>
            ))}
          </ol>
          <div className="mt-6 rounded-lg border border-[var(--color-border)] bg-[#0a0d12] p-3">
            <div className="flex items-center gap-2 text-xs text-[var(--color-muted)]">
              <GitPullRequest className="h-3.5 w-3.5" />
              API status: {healthOk ? 'healthy' : 'unreachable — check Settings'}
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
