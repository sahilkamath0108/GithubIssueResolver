import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Rocket } from 'lucide-react'
import {
  extractErrorMessage,
  parseIssueRepo,
  repoToUrl,
  submitWorkflow,
} from '../api/client'
import Alert from '../components/Alert'
import Button from '../components/Button'
import Card, { CardHeader } from '../components/Card'
import Input from '../components/Input'

export default function SubmitWorkflow() {
  const navigate = useNavigate()
  const [issueUrl, setIssueUrl] = useState('')
  const [repoUrl, setRepoUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function handleIssueChange(value) {
    setIssueUrl(value)
    const repo = parseIssueRepo(value)
    if (repo && !repoUrl) setRepoUrl(repoToUrl(repo))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await submitWorkflow(issueUrl.trim(), repoUrl.trim())
      navigate(`/tasks/${result.task_uuid}`)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-fade-in mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white md:text-3xl">Resolve an issue</h1>
        <p className="mt-2 text-[var(--color-muted)]">
          Submit a GitHub issue and queue the multi-agent workflow. The issue and repository
          must belong to the same repo.
        </p>
      </div>

      <Card glow>
        <CardHeader
          title="Issue details"
          subtitle="We'll fetch the issue, index the repo if needed, and start the agent pipeline"
        />

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && <Alert type="error">{error}</Alert>}

          <Input
            label="GitHub issue URL"
            placeholder="https://github.com/owner/repo/issues/42"
            value={issueUrl}
            onChange={(e) => handleIssueChange(e.target.value)}
            required
            hint="Full URL to the GitHub issue"
          />

          <Input
            label="Repository URL"
            placeholder="https://github.com/owner/repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            required
            hint="Must match the repository that owns the issue"
          />

          <div className="flex flex-wrap gap-3 pt-2">
            <Button type="submit" loading={loading} disabled={!issueUrl || !repoUrl}>
              <Rocket className="h-4 w-4" />
              Start workflow
            </Button>
          </div>
        </form>
      </Card>
    </div>
  )
}
