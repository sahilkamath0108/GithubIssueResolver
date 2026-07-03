import { Link } from 'react-router-dom'
import {
  ArrowRight,
  CheckCircle2,
  Database,
  GitPullRequest,
  ListChecks,
  Loader2,
  SquarePen,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { listTasks } from '@/api/client'
import { PageHeader } from '@/components/page-header'
import { StatCard } from '@/components/stat-card'
import { StatusBadge } from '@/components/status-badge'
import { PipelineCompact } from '@/components/pipeline'
import { Button, buttonVariants } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { relativeTime } from '@/lib/format'
import {
  buildPipelineSteps,
  issueTitleFromUrl,
  parseIssueNumber,
  parseRepoFromUrl,
  weeklyThroughput,
} from '@/lib/task-utils'
import { useRepoStore } from '@/store/repos'
import { cn } from '@/lib/utils'

export default function Dashboard() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const repositories = useRepoStore((s) => s.repositories)

  useEffect(() => {
    listTasks()
      .then((data) => setTasks(Array.isArray(data) ? data : []))
      .finally(() => setLoading(false))
  }, [])

  const running = tasks.filter((t) => t.status === 'running' || t.status === 'queued').length
  const success = tasks.filter((t) => t.status === 'success').length
  const failed = tasks.filter((t) => t.status === 'failed').length
  const completed = success + failed
  const successRate = completed ? Math.round((success / completed) * 100) : 0
  const prs = tasks.filter((t) => t.status === 'success').length

  const recent = [...tasks]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 6)

  const weekly = weeklyThroughput(tasks)
  const maxWeekly = Math.max(1, ...weekly.map((w) => w.resolved + w.failed))

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-4 lg:p-6">
      <PageHeader
        title="Dashboard"
        description="Overview of your autonomous issue-resolution pipeline."
      >
        <Link to="/submit" className={buttonVariants({ size: 'sm' })}>
          <SquarePen className="size-3.5" />
          Submit issue
        </Link>
      </PageHeader>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Active tasks" value={running} icon={Loader2} accent="info" hint="Running or queued" />
        <StatCard label="Success rate" value={`${successRate}%`} icon={CheckCircle2} accent="primary" hint={`${success} resolved / ${completed} completed`} />
        <StatCard label="PRs opened" value={prs} icon={GitPullRequest} accent="primary" hint="Successful workflows" />
        <StatCard label="Indexed repos" value={repositories.filter((r) => r.status === 'indexed').length} icon={Database} accent="warning" hint={`${repositories.length} connected`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex-row items-center justify-between">
            <CardTitle>Recent activity</CardTitle>
            <Link to="/tasks" className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'text-muted-foreground')}>
              View all
              <ArrowRight className="size-3.5" />
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <p className="px-4 pb-4 text-sm text-muted-foreground">Loading tasks…</p>
            ) : recent.length === 0 ? (
              <div className="px-4 pb-6 text-center">
                <p className="text-sm text-muted-foreground">No tasks yet.</p>
                <Link to="/submit" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), 'mt-4 inline-flex')}>
                  Submit your first issue
                </Link>
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {recent.map((task) => {
                  const steps = buildPipelineSteps(task.current_step, task.status)
                  const repo = parseRepoFromUrl(task.issue_url)
                  const issueNum = parseIssueNumber(task.issue_url)
                  return (
                    <li key={task.uuid}>
                      <Link
                        to={`/tasks/${task.uuid}`}
                        className="flex items-center gap-4 px-4 py-3 transition-colors hover:bg-muted/40"
                      >
                        <div className="min-w-0 flex-1">
                          <span className="truncate text-sm font-medium">{issueTitleFromUrl(task.issue_url)}</span>
                          <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                            <span className="font-mono">{repo}</span>
                            {issueNum && (
                              <>
                                <span aria-hidden>·</span>
                                <span>#{issueNum}</span>
                              </>
                            )}
                            <span aria-hidden>·</span>
                            <span>{relativeTime(task.created_at)}</span>
                          </div>
                        </div>
                        <div className="hidden sm:block">
                          <PipelineCompact steps={steps} />
                        </div>
                        <StatusBadge status={task.status} />
                      </Link>
                    </li>
                  )
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Throughput</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex h-32 items-end justify-between gap-2">
                {weekly.map((w) => (
                  <div key={w.day} className="flex flex-1 flex-col items-center gap-2">
                    <div className="flex h-24 w-full flex-col justify-end gap-0.5">
                      {w.failed > 0 && (
                        <div className="w-full rounded-sm bg-destructive/60" style={{ height: `${(w.failed / maxWeekly) * 100}%` }} />
                      )}
                      <div className="w-full rounded-sm bg-primary" style={{ height: `${(w.resolved / maxWeekly) * 100}%` }} />
                    </div>
                    <span className="text-[10px] text-muted-foreground">{w.day}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex items-center justify-center gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="size-2 rounded-full bg-primary" />
                  Resolved
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="size-2 rounded-full bg-destructive/60" />
                  Failed
                </span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Repositories</CardTitle>
              <Link to="/repositories" className={cn(buttonVariants({ variant: 'ghost', size: 'sm' }), 'text-muted-foreground')}>
                Manage
                <ArrowRight className="size-3.5" />
              </Link>
            </CardHeader>
            <CardContent className="space-y-3">
              {repositories.length === 0 ? (
                <p className="text-xs text-muted-foreground">No repos indexed yet.</p>
              ) : (
                repositories.slice(0, 4).map((repo) => (
                  <div key={repo.id} className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-xs">{repo.name}</span>
                    <span className="rounded-full border border-success/20 bg-success/10 px-2 py-0.5 text-xs text-success">
                      Indexed
                    </span>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardContent className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ListChecks className="size-5" />
            </span>
            <div>
              <p className="text-sm font-medium">Ready to fix another issue?</p>
              <p className="text-xs text-muted-foreground">
                Paste a GitHub issue URL and the agents take it from there.
              </p>
            </div>
          </div>
          <Link to="/submit" className={buttonVariants()}>
            Submit an issue
            <ArrowRight className="size-4" />
          </Link>
        </CardContent>
      </Card>
    </div>
  )
}
