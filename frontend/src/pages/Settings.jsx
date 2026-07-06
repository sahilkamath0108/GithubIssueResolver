import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSettingsStore } from '@/store/settings'
import { useAuthStore } from '@/store/auth'
import {
  extractErrorMessage,
  getProviderKeysStatus,
  updateProviderKeys,
} from '@/api/client'
import { PageHeader } from '@/components/page-header'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/input'

export default function Settings() {
  const apiKey = useSettingsStore((s) => s.apiKey)
  const apiBaseUrl = useSettingsStore((s) => s.apiBaseUrl)
  const setApiKey = useSettingsStore((s) => s.setApiKey)
  const setApiBaseUrl = useSettingsStore((s) => s.setApiBaseUrl)
  const user = useAuthStore((s) => s.user)
  const oauthEnabled = useAuthStore((s) => s.oauthEnabled)

  const [keyStatus, setKeyStatus] = useState(null)
  const [groqKey, setGroqKey] = useState('')
  const [jinaKey, setJinaKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!user) return
    getProviderKeysStatus()
      .then(setKeyStatus)
      .catch(() => setKeyStatus(null))
  }, [user])

  async function handleSaveProviderKeys(e) {
    e.preventDefault()
    setError('')
    setSaved(false)
    setSaving(true)
    try {
      const payload = {}
      if (groqKey.trim()) payload.groq_api_key = groqKey.trim()
      if (jinaKey.trim()) payload.jina_api_key = jinaKey.trim()
      if (!payload.groq_api_key && !payload.jina_api_key) {
        setError('Enter at least one API key to save.')
        return
      }
      const status = await updateProviderKeys(payload)
      setKeyStatus(status)
      setGroqKey('')
      setJinaKey('')
      setSaved(true)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const showJina = keyStatus?.embedding_provider === 'jina'

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6 p-4 lg:p-6">
      <PageHeader
        title="Settings"
        description="Connection options and your own LLM / embedding API keys."
      />

      {oauthEnabled && user && keyStatus?.user_keys_required && (
        <Card className="border-warning/30 bg-warning/5">
          <CardContent className="py-4 text-sm">
            This deployment does not include shared Groq/Jina keys. Add your own below
            before submitting issues or indexing repos.
          </CardContent>
        </Card>
      )}

      {oauthEnabled && user && (
        <Card>
          <CardHeader>
            <CardTitle>Your API keys</CardTitle>
            <CardDescription>
              Stored encrypted on the server, linked to your GitHub account. Used for
              workflows and indexing while you are logged in. Keys are cleared when you
              sign out.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {keyStatus && (
              <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
                <span>
                  Groq:{' '}
                  <strong className="text-foreground">
                    {keyStatus.groq_configured ? 'configured' : 'missing'}
                  </strong>
                </span>
                {showJina && (
                  <span>
                    Jina:{' '}
                    <strong className="text-foreground">
                      {keyStatus.jina_configured ? 'configured' : 'missing'}
                    </strong>
                  </span>
                )}
              </div>
            )}

            {error && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}
            {saved && (
              <div className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-sm text-success">
                API keys saved.
              </div>
            )}

            <form onSubmit={handleSaveProviderKeys} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="groq-key">Groq API key</Label>
                <Input
                  id="groq-key"
                  type="password"
                  placeholder={keyStatus?.groq_user_configured ? '•••••••• (saved — paste to replace)' : 'gsk_...'}
                  value={groqKey}
                  onChange={(e) => setGroqKey(e.target.value)}
                  autoComplete="off"
                />
                <p className="text-xs text-muted-foreground">
                  Powers planning and code writing.{' '}
                  <a
                    href="https://console.groq.com/keys"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    Get a key
                  </a>
                </p>
              </div>

              {showJina && (
                <div className="space-y-2">
                  <Label htmlFor="jina-key">Jina API key</Label>
                  <Input
                    id="jina-key"
                    type="password"
                    placeholder={keyStatus?.jina_user_configured ? '•••••••• (saved — paste to replace)' : 'jina_...'}
                    value={jinaKey}
                    onChange={(e) => setJinaKey(e.target.value)}
                    autoComplete="off"
                  />
                  <p className="text-xs text-muted-foreground">
                    Powers repo indexing and semantic search.{' '}
                    <a
                      href="https://jina.ai/api-dashboard/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      Get a key
                    </a>
                  </p>
                </div>
              )}

              <Button type="submit" disabled={saving}>
                {saving ? 'Saving…' : 'Save API keys'}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {oauthEnabled && !user && (
        <Card>
          <CardContent className="py-4 text-sm text-muted-foreground">
            <Link to="/login" className="text-primary hover:underline">
              Sign in with GitHub
            </Link>{' '}
            to add your Groq and Jina API keys.
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>API connection</CardTitle>
          <CardDescription>
            Optional overrides stored in your browser only.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="rounded-lg border border-info/20 bg-info/5 px-3 py-2 text-sm text-muted-foreground">
            <strong className="text-foreground">Development:</strong> With{' '}
            <code className="rounded bg-muted px-1">npm run dev</code>, requests proxy to port 8000.
            With Docker, open port 3000 — nginx proxies <code className="rounded bg-muted px-1">/api</code>.
          </div>

          <div className="space-y-2">
            <Label htmlFor="base-url">API base URL (optional)</Label>
            <Input
              id="base-url"
              placeholder="http://localhost:8000"
              value={apiBaseUrl}
              onChange={(e) => setApiBaseUrl(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="api-key">Service API key (optional)</Label>
            <Input
              id="api-key"
              type="password"
              placeholder="X-API-Key for non-OAuth deployments"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
