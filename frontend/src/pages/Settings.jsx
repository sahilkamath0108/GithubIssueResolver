import { useSettingsStore } from '../store/settings'
import Alert from '../components/Alert'
import Card, { CardHeader } from '../components/Card'
import Input from '../components/Input'

export default function Settings() {
  const apiKey = useSettingsStore((s) => s.apiKey)
  const apiBaseUrl = useSettingsStore((s) => s.apiBaseUrl)
  const setApiKey = useSettingsStore((s) => s.setApiKey)
  const setApiBaseUrl = useSettingsStore((s) => s.setApiBaseUrl)

  return (
    <div className="animate-fade-in mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white md:text-3xl">Settings</h1>
        <p className="mt-2 text-[var(--color-muted)]">
          Configure API connection. Values are stored in your browser only.
        </p>
      </div>

      <Card>
        <CardHeader
          title="API connection"
          subtitle="Leave base URL empty to use the same origin (Docker nginx proxy or Vite dev proxy)"
        />

        <div className="space-y-5">
          <Alert type="info" title="Development">
            With <code className="rounded bg-black/30 px-1">npm run dev</code>, requests proxy to{' '}
            <code className="rounded bg-black/30 px-1">localhost:8000</code>. With Docker, open{' '}
            <code className="rounded bg-black/30 px-1">localhost:3000</code> — nginx proxies{' '}
            <code className="rounded bg-black/30 px-1">/api</code> to the backend.
          </Alert>

          <Input
            label="API base URL (optional)"
            placeholder="http://localhost:8000"
            value={apiBaseUrl}
            onChange={(e) => setApiBaseUrl(e.target.value)}
            hint="Only set if the API is on a different host than the frontend"
          />

          <Input
            label="API key (optional)"
            type="password"
            placeholder="X-API-Key value from .env"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            hint="Required when API_KEY is set on the backend"
          />
        </div>
      </Card>
    </div>
  )
}
