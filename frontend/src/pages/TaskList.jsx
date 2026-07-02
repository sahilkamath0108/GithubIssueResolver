import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { extractErrorMessage, listTasks } from '../api/client'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card, { CardHeader } from '../components/Card'
import StatusBadge from '../components/StatusBadge'

const FILTERS = ['all', 'queued', 'running', 'success', 'failed']

export default function TaskList() {
  const [tasks, setTasks] = useState([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const status = filter === 'all' ? undefined : filter
      const data = await listTasks(status)
      setTasks(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [filter])

  const sorted = [...tasks].sort(
    (a, b) => new Date(b.created_at) - new Date(a.created_at),
  )

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white md:text-3xl">Tasks</h1>
          <p className="mt-1 text-[var(--color-muted)]">
            Monitor all workflow runs and open details for logs and PR links.
          </p>
        </div>
        <Button variant="secondary" onClick={load} loading={loading}>
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded-full px-3.5 py-1.5 text-xs font-medium capitalize transition ${
              filter === f
                ? 'bg-indigo-600/25 text-indigo-200 ring-1 ring-indigo-500/40'
                : 'bg-[#181d28] text-slate-400 hover:text-slate-200'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {error && <Alert type="error">{error}</Alert>}

      <Card>
        {loading && tasks.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">Loading…</p>
        ) : sorted.length === 0 ? (
          <p className="py-8 text-center text-[var(--color-muted)]">No tasks found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-xs uppercase tracking-wider text-[var(--color-muted)]">
                  <th className="pb-3 pr-4 font-medium">Issue</th>
                  <th className="pb-3 pr-4 font-medium">Status</th>
                  <th className="pb-3 pr-4 font-medium">Step</th>
                  <th className="pb-3 font-medium">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {sorted.map((task) => (
                  <tr key={task.uuid} className="group">
                    <td className="py-3.5 pr-4">
                      <Link
                        to={`/tasks/${task.uuid}`}
                        className="font-medium text-indigo-300 hover:text-indigo-200"
                      >
                        {task.issue_url?.replace('https://github.com/', '') || task.uuid}
                      </Link>
                    </td>
                    <td className="py-3.5 pr-4">
                      <StatusBadge status={task.status} pulse />
                    </td>
                    <td className="py-3.5 pr-4 text-slate-400">{task.current_step || '—'}</td>
                    <td className="py-3.5 text-slate-500">
                      {new Date(task.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
