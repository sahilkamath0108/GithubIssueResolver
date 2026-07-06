import { useEffect, useState } from 'react'
import { ExternalLink, KeyRound } from 'lucide-react'
import {
  extractErrorMessage,
  getProviderKeysStatus,
  updateProviderKeys,
} from '@/api/client'
import { useAuthStore } from '@/store/auth'
import { Button } from '@/components/ui/button'
import { Input, Label } from '@/components/ui/input'

const GROQ_KEYS_URL = 'https://console.groq.com/keys'
const JINA_URL = 'https://jina.ai/'

export function ProviderKeysModal() {
  const user = useAuthStore((s) => s.user)
  const authChecked = useAuthStore((s) => s.checked)
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState(null)
  const [groqKey, setGroqKey] = useState('')
  const [jinaKey, setJinaKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!authChecked || !user) {
      setOpen(false)
      return
    }
    let cancelled = false
    getProviderKeysStatus()
      .then((s) => {
        if (cancelled) return
        setStatus(s)
        const needsJina = s.embedding_provider === 'jina'
        const missing = !s.groq_configured || (needsJina && !s.jina_configured)
        setOpen(Boolean(s.user_keys_required && missing))
      })
      .catch(() => {
        if (!cancelled) setOpen(false)
      })
    return () => {
      cancelled = true
    }
  }, [user, authChecked])

  if (!open) return null

  const showJina = status?.embedding_provider === 'jina'
  const needsGroq = !status?.groq_configured
  const needsJina = showJina && !status?.jina_configured

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      const payload = {}
      if (needsGroq && groqKey.trim()) payload.groq_api_key = groqKey.trim()
      if (needsJina && jinaKey.trim()) payload.jina_api_key = jinaKey.trim()
      if (!payload.groq_api_key && !payload.jina_api_key) {
        setError('Enter the required API key(s) below.')
        return
      }
      if (needsGroq && !payload.groq_api_key) {
        setError('Groq API key is required.')
        return
      }
      if (needsJina && !payload.jina_api_key) {
        setError('Jina API key is required.')
        return
      }
      const next = await updateProviderKeys(payload)
      setStatus(next)
      const stillMissing =
        !next.groq_configured || (next.embedding_provider === 'jina' && !next.jina_configured)
      if (!stillMissing) {
        setGroqKey('')
        setJinaKey('')
        setOpen(false)
      }
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-xs" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="provider-keys-title"
        className="relative z-10 w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl"
      >
        <div className="mb-5 flex items-start gap-3">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <KeyRound className="size-5" />
          </span>
          <div>
            <h2 id="provider-keys-title" className="text-lg font-semibold tracking-tight">
              Connect your API keys
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              This app uses your own Groq and Jina accounts. Keys are encrypted and tied to your
              GitHub login — not shared with other users.
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {needsGroq && (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor="modal-groq-key">Groq API key</Label>
                <a
                  href={GROQ_KEYS_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  Get key
                  <ExternalLink className="size-3" />
                </a>
              </div>
              <Input
                id="modal-groq-key"
                type="password"
                placeholder="gsk_..."
                value={groqKey}
                onChange={(e) => setGroqKey(e.target.value)}
                autoComplete="off"
                autoFocus
              />
              <p className="text-xs text-muted-foreground">
                Powers planning and code writing via{' '}
                <a
                  href={GROQ_KEYS_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  Groq Console
                </a>
                .
              </p>
            </div>
          )}

          {needsJina && (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor="modal-jina-key">Jina API key</Label>
                <a
                  href={JINA_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  Get key
                  <ExternalLink className="size-3" />
                </a>
              </div>
              <Input
                id="modal-jina-key"
                type="password"
                placeholder="jina_..."
                value={jinaKey}
                onChange={(e) => setJinaKey(e.target.value)}
                autoComplete="off"
                autoFocus={!needsGroq}
              />
              <p className="text-xs text-muted-foreground">
                Powers repo indexing and semantic search via{' '}
                <a
                  href={JINA_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  Jina AI
                </a>
                .
              </p>
            </div>
          )}

          <Button type="submit" className="w-full" disabled={saving}>
            {saving ? 'Saving…' : 'Save and continue'}
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          You can update these later in Settings.
        </p>
      </div>
    </div>
  )
}
