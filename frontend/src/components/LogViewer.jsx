import { useMemo, useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

const LEVEL_STYLES = {
  info: 'border-l-indigo-500/60',
  warning: 'border-l-amber-500/60',
  error: 'border-l-red-500/60',
  debug: 'border-l-slate-500/60',
}

function MetadataBlock({ metadata }) {
  const [open, setOpen] = useState(false)
  if (!metadata || Object.keys(metadata).length === 0) return null

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-indigo-300/80 hover:text-indigo-200"
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        {open ? 'Hide metadata' : 'Show metadata'}
      </button>
      {open && (
        <pre className="mt-2 max-h-64 overflow-auto rounded-lg bg-black/40 p-3 text-xs text-slate-400">
          {JSON.stringify(metadata, null, 2)}
        </pre>
      )}
    </div>
  )
}

export default function LogViewer({ logs }) {
  const sorted = useMemo(
    () =>
      [...(logs || [])].sort(
        (a, b) => new Date(a.created_at) - new Date(b.created_at),
      ),
    [logs],
  )

  if (sorted.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-[var(--color-muted)]">
        No logs yet — workflow may still be starting.
      </p>
    )
  }

  return (
    <ul className="space-y-3">
      {sorted.map((log, i) => (
        <li
          key={`${log.created_at}-${i}`}
          className={`rounded-r-lg border-l-2 bg-[#0a0d12]/80 py-3 pl-4 pr-3 ${LEVEL_STYLES[log.level] || LEVEL_STYLES.info}`}
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {log.level}
            </span>
            <time className="text-xs text-slate-600">
              {new Date(log.created_at).toLocaleString()}
            </time>
          </div>
          <p className="mt-1 text-sm text-slate-200 whitespace-pre-wrap break-words">
            {log.message}
          </p>
          <MetadataBlock metadata={log.metadata} />
        </li>
      ))}
    </ul>
  )
}
