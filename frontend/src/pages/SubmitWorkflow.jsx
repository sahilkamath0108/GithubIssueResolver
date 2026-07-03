import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Rocket } from 'lucide-react'
import {
  extractErrorMessage,
  parseIssueRepo,
  repoToUrl,
  submitWorkflow,
} from '@/api/client'
import { PageHeader } from '@/components/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/input'

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
    <div className="mx-auto w-full max-w-2xl space-y-6 p-4 lg:p-6">
      <PageHeader
        title="Submit issue"
        description="Queue a multi-agent workflow. The issue and repository must belong to the same repo."
      />

      <Card>
        <CardHeader>
          <CardTitle>Issue details</CardTitle>
          <CardDescription>
            Agents will plan, search your indexed codebase, write patches, test, and open a PR.
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
              <Label htmlFor="issue-url">GitHub issue URL</Label>
              <Input
                id="issue-url"
                placeholder="https://github.com/owner/repo/issues/42"
                value={issueUrl}
                onChange={(e) => handleIssueChange(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="repo-url">Repository URL</Label>
              <Input
                id="repo-url"
                placeholder="https://github.com/owner/repo"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                required
              />
            </div>

            <Button type="submit" disabled={loading || !issueUrl || !repoUrl}>
              {loading ? (
                <>Starting…</>
              ) : (
                <>
                  <Rocket className="size-4" />
                  Start workflow
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
