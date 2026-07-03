import { Github } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchAuthStatus, openGitHubAccountSwitch, startGitHubLogin } from '@/api/client'
import { useAuthStore } from '@/store/auth'
import { PageHeader } from '@/components/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function LoginPage() {
  const [searchParams] = useSearchParams()
  const oauthEnabled = useAuthStore((s) => s.oauthEnabled)
  const checked = useAuthStore((s) => s.checked)
  const [error, setError] = useState('')

  useEffect(() => {
    const authError = searchParams.get('auth_error')
    if (authError) setError(`GitHub sign-in failed: ${authError}`)
  }, [searchParams])

  useEffect(() => {
    if (!checked) fetchAuthStatus()
  }, [checked])

  if (checked && !oauthEnabled) {
    return (
      <div className="mx-auto max-w-lg p-6">
        <Card>
          <CardHeader>
            <CardTitle>GitHub sign-in not configured</CardTitle>
            <CardDescription>
              Set GITHUB_OAUTH_CLIENT_ID, GITHUB_OAUTH_CLIENT_SECRET, GITHUB_OAUTH_CALLBACK_URL, and
              JWT_SECRET in the backend environment, or use an API key in Settings.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto flex min-h-[60vh] w-full max-w-md flex-col justify-center p-4">
      <PageHeader
        title="Sign in"
        description="Connect your GitHub account to submit issues and index repositories you have access to."
      />
      <Card>
        <CardHeader>
          <CardTitle>GitHub OAuth</CardTitle>
          <CardDescription>
            Workflows run with your token — only repos you can push to are allowed.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}
          <Button type="button" className="w-full gap-2" onClick={startGitHubLogin}>
            <Github className="size-4" />
            Continue with GitHub
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Wrong account?{' '}
            <button
              type="button"
              className="text-primary underline-offset-2 hover:underline"
              onClick={openGitHubAccountSwitch}
            >
              Sign out of GitHub
            </button>{' '}
            in a new tab, then return here and sign in again.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
