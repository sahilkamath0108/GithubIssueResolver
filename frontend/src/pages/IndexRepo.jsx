import { useState } from 'react'
import { CheckCircle2, Database } from 'lucide-react'
import { extractErrorMessage, syncRepoIndex } from '../api/client'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card, { CardHeader } from '../components/Card'
import Input, { Checkbox } from '../components/Input'

export default function IndexRepo() {
  const [repo, setRepo] = useState('')
  const [forceFull, setForceFull] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const data = await syncRepoIndex(repo.trim(), forceFull)
      setResult(data)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-fade-in mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white md:text-3xl">Index repository</h1>
        <p className="mt-2 text-[var(--color-muted)]">
          Sync code from GitHub into Qdrant for semantic search. Run this before resolving
          issues in a new repo.
        </p>
      </div>

      <Card glow>
        <CardHeader
          title="Repository sync"
          subtitle="Full, incremental, or skipped — decided automatically by commit SHA"
        />

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && <Alert type="error">{error}</Alert>}

          <Input
            label="Repository"
            placeholder="owner/name"
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            required
            hint='GitHub repo in "owner/name" format'
          />

          <Checkbox
            label="Force full reindex"
            description="Wipes existing vectors for this repo in Qdrant and rebuilds from scratch"
            checked={forceFull}
            onChange={(e) => setForceFull(e.target.checked)}
          />

          <Button type="submit" loading={loading} disabled={!repo.trim()}>
            <Database className="h-4 w-4" />
            Sync index
          </Button>
        </form>
      </Card>

      {result && (
        <Card className="border-emerald-500/20">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-400" />
            <div className="flex-1 space-y-3">
              <div>
                <p className="font-medium text-white">Sync complete</p>
                <p className="text-sm text-[var(--color-muted)]">{result.message}</p>
              </div>
              <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
                {[
                  ['Mode', result.mode],
                  ['Commit', result.commit_sha?.slice(0, 8)],
                  ['Files indexed', result.files_indexed],
                  ['Chunks written', result.chunks_written],
                  ['Files deleted', result.files_deleted],
                  ['Skipped unchanged', result.files_skipped_unchanged],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-[#0a0d12] px-3 py-2">
                    <dt className="text-xs text-[var(--color-muted)]">{label}</dt>
                    <dd className="mt-0.5 font-medium text-white">{value ?? '—'}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
