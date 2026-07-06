import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { extractErrorMessage, listTasks } from '@/api/client'
import { PageHeader } from '@/components/page-header'
import { StatusBadge } from '@/components/status-badge'
import { PipelineCompact } from '@/components/pipeline'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { relativeTime } from '@/lib/format'
import {
  buildPipelineSteps,
  issueTitleFromUrl,
  parseRepoFromUrl,
} from '@/lib/task-utils'

const FILTERS = ['all', 'queued', 'running', 'success', 'failed', 'cancelled']

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
    <div className="mx-auto w-full max-w-6xl space-y-6 p-4 lg:p-6">
      <PageHeader
        title="Tasks"
        description="Monitor workflow runs, open details for logs and PR links."
      >
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={loading ? 'size-3.5 animate-spin' : 'size-3.5'} />
          Refresh
        </Button>
      </PageHeader>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded-full px-3.5 py-1.5 text-xs font-medium capitalize transition ${
              filter === f
                ? 'bg-primary/15 text-primary ring-1 ring-primary/30'
                : 'bg-muted text-muted-foreground hover:text-foreground'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          {loading && tasks.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">Loading…</p>
          ) : sorted.length === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">No tasks found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-4 pb-3 font-medium">Issue</th>
                    <th className="px-4 pb-3 font-medium">Pipeline</th>
                    <th className="px-4 pb-3 font-medium">Status</th>
                    <th className="px-4 pb-3 font-medium">Step</th>
                    <th className="px-4 pb-3 font-medium">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {sorted.map((task) => {
                    const steps = buildPipelineSteps(task.current_step, task.status)
                    return (
                      <tr key={task.uuid} className="hover:bg-muted/30">
                        <td className="px-4 py-3.5">
                          <Link
                            to={`/tasks/${task.uuid}`}
                            className="font-medium text-primary hover:underline"
                          >
                            {issueTitleFromUrl(task.issue_url)}
                          </Link>
                          <p className="mt-0.5 font-mono text-xs text-muted-foreground">
                            {parseRepoFromUrl(task.issue_url)}
                          </p>
                        </td>
                        <td className="px-4 py-3.5">
                          <PipelineCompact steps={steps} />
                        </td>
                        <td className="px-4 py-3.5">
                          <StatusBadge status={task.status} />
                        </td>
                        <td className="px-4 py-3.5 text-muted-foreground">
                          {task.current_step || '—'}
                        </td>
                        <td className="px-4 py-3.5 text-muted-foreground">
                          {relativeTime(task.created_at)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
