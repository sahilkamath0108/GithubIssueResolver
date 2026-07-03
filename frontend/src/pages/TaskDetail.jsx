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
  listTasks,
  retryTask,
} from '@/api/client'
import { PageHeader } from '@/components/page-header'
import { Pipeline } from '@/components/pipeline'
import { StatusBadge } from '@/components/status-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/input'
import { formatTime } from '@/lib/format'
import {
  buildPipelineSteps,
  computeProgress,
  issueTitleFromUrl,
  parseRepoFromUrl,
} from '@/lib/task-utils'

const ACTIVE = new Set(['queued', 'running'])

export default function TaskDetail() {
  const { taskUuid } = useParams()
  const [status, setStatus] = useState(null)
  const [issueUrl, setIssueUrl] = useState('')
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [statusData, logsData, tasksData] = await Promise.all([
        getTaskStatus(taskUuid),
        getTaskLogs(taskUuid),
        listTasks(),
      ])
      const match = tasksData.find((t) => t.uuid === taskUuid)
      if (match?.issue_url) setIssueUrl(match.issue_url)
      setStatus(statusData)
      setLogs(Array.isArray(logsData) ? logsData : [])
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

  const steps = status
    ? buildPipelineSteps(status.current_step, status.status)
    : []
  const progress = computeProgress(steps)

  if (loading && !status) {
    return (
      <div className="mx-auto max-w-6xl p-6 text-muted-foreground">Loading task…</div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-4 lg:p-6">
      <Link
        to="/tasks"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to tasks
      </Link>

      <PageHeader
        title={issueUrl ? issueTitleFromUrl(issueUrl) : 'Task details'}
        description={
          issueUrl
            ? `${parseRepoFromUrl(issueUrl)} · ${taskUuid}`
            : taskUuid
        }
      >
        <Button variant="outline" size="sm" onClick={refresh}>
          <RefreshCw className="size-3.5" />
          Refresh
        </Button>
        {status?.status === 'failed' && (
          <Button size="sm" onClick={handleRetry} disabled={retrying}>
            <RotateCcw className="size-3.5" />
            {retrying ? 'Retrying…' : 'Retry'}
          </Button>
        )}
      </PageHeader>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {status && (
        <>
          <div className="grid gap-4 md:grid-cols-4">
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">Status</p>
              <div className="mt-2">
                <StatusBadge status={status.status} />
              </div>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">Current step</p>
              <p className="mt-2 text-sm font-medium">{status.current_step || '—'}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">Retries</p>
              <p className="mt-2 text-sm font-medium tabular-nums">{status.retry_count}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">Progress</p>
              <p className="mt-2 text-sm font-medium tabular-nums">{progress}%</p>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Agent pipeline</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Progress value={progress} />
              <Pipeline steps={steps} />
            </CardContent>
          </Card>

          {status.result_pr_url && (
            <Card className="border-success/20 bg-success/5">
              <CardContent className="flex items-center gap-3 py-4">
                <GitPullRequest className="size-5 text-success" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">Pull request created</p>
                  <a
                    href={status.result_pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-0.5 inline-flex items-center gap-1 text-sm text-primary hover:underline"
                  >
                    {status.result_pr_url}
                    <ExternalLink className="size-3.5" />
                  </a>
                </div>
              </CardContent>
            </Card>
          )}

          {status.error && (
            <Card className="border-destructive/30 bg-destructive/5">
              <CardContent className="py-4">
                <p className="text-sm font-medium text-destructive">Workflow error</p>
                <p className="mt-1 text-sm text-destructive/90">{status.error}</p>
              </CardContent>
            </Card>
          )}
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Execution logs</CardTitle>
          {status && ACTIVE.has(status.status) && (
            <p className="text-xs text-muted-foreground">Auto-refreshing every 4 seconds</p>
          )}
        </CardHeader>
        <CardContent>
          {logs.length === 0 ? (
            <p className="py-4 text-center text-sm text-muted-foreground">
              No logs yet — workflow may still be starting.
            </p>
          ) : (
            <ul className="max-h-[480px] space-y-2 overflow-y-auto">
              {logs.map((log, i) => (
                <li
                  key={`${log.created_at}-${i}`}
                  className="rounded-lg border border-border bg-muted/20 px-3 py-2.5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                    <span className="uppercase tracking-wide">{log.level}</span>
                    <span>{formatTime(log.created_at)}</span>
                  </div>
                  <p className="mt-1 text-sm whitespace-pre-wrap">{log.message}</p>
                  {log.metadata && Object.keys(log.metadata).length > 0 && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs text-primary">Metadata</summary>
                      <pre className="mt-2 max-h-48 overflow-auto rounded bg-background p-2 text-xs text-muted-foreground">
                        {JSON.stringify(log.metadata, null, 2)}
                      </pre>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
