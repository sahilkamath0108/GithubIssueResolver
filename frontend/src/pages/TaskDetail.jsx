import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  ExternalLink,
  GitPullRequest,
  RefreshCw,
  RotateCcw,
} from 'lucide-react'
import {
  extractErrorMessage,
  getTaskLogs,
  getTaskStatus,
  retryTask,
} from '../api/client'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card, { CardHeader } from '../components/Card'
import LogViewer from '../components/LogViewer'
import StatusBadge from '../components/StatusBadge'

const ACTIVE = new Set(['queued', 'pending', 'running'])

export default function TaskDetail() {
  const { taskUuid } = useParams()
  const [status, setStatus] = useState(null)
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [statusData, logsData] = await Promise.all([
        getTaskStatus(taskUuid),
        getTaskLogs(taskUuid),
      ])
      setStatus(statusData)
      setLogs(logsData)
      setError('')
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [taskUuid])

  useEffect(() => {
    setLoading(true)
    refresh()
  }, [refresh])

  useEffect(() => {
    if (!status || !ACTIVE.has(status.status)) return undefined
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  }, [status?.status, refresh])

  async function handleRetry() {
    setRetrying(true)
    setError('')
    try {
      await retryTask(taskUuid)
      await refresh()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setRetrying(false)
    }
  }

  if (loading && !status) {
    return <p className="text-[var(--color-muted)]">Loading task…</p>
  }

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <Link
          to="/tasks"
          className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to tasks
        </Link>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Task details</h1>
          <p className="mt-1 font-mono text-xs text-slate-500">{taskUuid}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={refresh}>
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          {status?.status === 'failed' && (
            <Button onClick={handleRetry} loading={retrying}>
              <RotateCcw className="h-4 w-4" />
              Retry
            </Button>
          )}
        </div>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {status && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[
            ['Status', <StatusBadge key="s" status={status.status} pulse />],
            ['Current step', status.current_step || '—'],
            ['Retries', status.retry_count],
            ['Task ID', status.task_id],
          ].map(([label, value]) => (
            <div
              key={label}
              className="rounded-xl border border-[var(--color-border)] bg-[#12161f]/80 p-4"
            >
              <p className="text-xs text-[var(--color-muted)]">{label}</p>
              <div className="mt-1 text-sm font-medium text-white">{value}</div>
            </div>
          ))}
        </div>
      )}

      {status?.result_pr_url && (
        <Alert type="success" title="Pull request created">
          <a
            href={status.result_pr_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 font-medium underline underline-offset-2"
          >
            <GitPullRequest className="h-4 w-4" />
            {status.result_pr_url}
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </Alert>
      )}

      {status?.error && (
        <Alert type="error" title="Workflow error">
          {status.error}
        </Alert>
      )}

      <Card>
        <CardHeader
          title="Execution logs"
          subtitle={
            status && ACTIVE.has(status.status)
              ? 'Auto-refreshing every 4 seconds'
              : 'Step-by-step agent output'
          }
        />
        <LogViewer logs={logs} />
      </Card>
    </div>
  )
}
