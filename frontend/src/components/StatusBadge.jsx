const STATUS_STYLES = {
  queued: 'bg-slate-500/15 text-slate-300 ring-slate-500/30',
  pending: 'bg-slate-500/15 text-slate-300 ring-slate-500/30',
  running: 'bg-indigo-500/15 text-indigo-300 ring-indigo-500/40',
  success: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/40',
  failed: 'bg-red-500/15 text-red-300 ring-red-500/40',
  cancelled: 'bg-amber-500/15 text-amber-300 ring-amber-500/40',
}

export default function StatusBadge({ status, pulse = false }) {
  const key = (status || 'pending').toLowerCase()
  const styles = STATUS_STYLES[key] || STATUS_STYLES.pending

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ring-1 ring-inset ${styles}`}
    >
      {pulse && (key === 'queued' || key === 'pending' || key === 'running') && (
        <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse-dot" />
      )}
      {status || 'unknown'}
    </span>
  )
}
