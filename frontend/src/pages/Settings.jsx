import { useSettingsStore } from '@/store/settings'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/input'

export default function Settings() {
  const apiKey = useSettingsStore((s) => s.apiKey)
  const apiBaseUrl = useSettingsStore((s) => s.apiBaseUrl)
  const setApiKey = useSettingsStore((s) => s.setApiKey)
  const setApiBaseUrl = useSettingsStore((s) => s.setApiBaseUrl)

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6 p-4 lg:p-6">
      <PageHeader
        title="Settings"
        description="Configure API connection. Values are stored in your browser only."
      />

      <Card>
        <CardHeader>
          <CardTitle>API connection</CardTitle>
          <CardDescription>
            Leave base URL empty to use the same origin (Docker nginx or Vite dev proxy).
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
            <Label htmlFor="api-key">API key (optional)</Label>
            <Input
              id="api-key"
              type="password"
              placeholder="X-API-Key from .env"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
