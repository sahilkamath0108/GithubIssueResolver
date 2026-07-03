import { useState } from 'react'
import { CheckCircle2, Database, RefreshCw } from 'lucide-react'
import { extractErrorMessage, syncRepoIndex } from '@/api/client'
import { IndexBadge } from '@/components/status-badge'
import { PageHeader } from '@/components/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label, Switch } from '@/components/ui/input'
import { useRepoStore } from '@/store/repos'
import { relativeTime } from '@/lib/format'

export default function Repositories() {
  const [repo, setRepo] = useState('')
  const [forceFull, setForceFull] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const repositories = useRepoStore((s) => s.repositories)
  const upsertFromSync = useRepoStore((s) => s.upsertFromSync)
  const setIndexing = useRepoStore((s) => s.setIndexing)
  const markFailed = useRepoStore((s) => s.markFailed)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    const name = repo.trim()
    setIndexing(name)
    try {
      const data = await syncRepoIndex(name, forceFull)
      setResult(data)
      upsertFromSync(data)
    } catch (err) {
      markFailed(name)
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-4 lg:p-6">
      <PageHeader
        title="Repositories"
        description="Sync GitHub repositories into Qdrant for semantic code search before resolving issues."
      />

      <Card>
        <CardHeader>
          <CardTitle>Index repository</CardTitle>
          <CardDescription>
            Full, incremental, or skipped — decided automatically by commit SHA.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="repo">Repository</Label>
              <Input
                id="repo"
                placeholder="owner/name"
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                required
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border border-border p-3">
              <div>
                <p className="text-sm font-medium">Force full reindex</p>
                <p className="text-xs text-muted-foreground">
                  Wipe existing vectors and rebuild from scratch
                </p>
              </div>
              <Switch checked={forceFull} onCheckedChange={setForceFull} />
            </div>

            <Button type="submit" disabled={loading || !repo.trim()}>
              {loading ? (
                <>
                  <RefreshCw className="size-4 animate-spin" />
                  Syncing…
                </>
              ) : (
                <>
                  <Database className="size-4" />
                  Sync index
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {result && (
        <Card className="border-success/20">
          <CardContent className="flex items-start gap-3 py-4">
            <CheckCircle2 className="mt-0.5 size-5 text-success" />
            <div className="flex-1 space-y-3">
              <div>
                <p className="font-medium">Sync complete</p>
                <p className="text-sm text-muted-foreground">{result.message}</p>
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                {[
                  ['Mode', result.mode],
                  ['Commit', result.commit_sha?.slice(0, 8)],
                  ['Files', result.files_indexed],
                  ['Chunks', result.chunks_written],
                  ['Deleted', result.files_deleted],
                  ['Skipped', result.files_skipped_unchanged],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-muted/40 px-3 py-2">
                    <dt className="text-xs text-muted-foreground">{label}</dt>
                    <dd className="mt-0.5 font-medium tabular-nums">{value ?? '—'}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Connected repositories</CardTitle>
        </CardHeader>
        <CardContent>
          {repositories.length === 0 ? (
            <p className="text-sm text-muted-foreground">No repositories indexed in this browser yet.</p>
          ) : (
            <ul className="divide-y divide-border">
              {repositories.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                  <div>
                    <p className="font-mono text-sm">{r.name}</p>
                    {r.lastIndexed && (
                      <p className="text-xs text-muted-foreground">
                        Last synced {relativeTime(r.lastIndexed)}
                        {r.chunks ? ` · ${r.chunks} chunks` : ''}
                      </p>
                    )}
                  </div>
                  <IndexBadge status={r.status} />
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
