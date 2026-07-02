export default function Input({ label, hint, error, className = '', ...props }) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1.5 block text-sm font-medium text-slate-300">{label}</span>
      )}
      <input
        className={`w-full rounded-lg border border-[var(--color-border)] bg-[#0a0d12] px-3.5 py-2.5 text-sm text-white placeholder:text-slate-600 outline-none transition focus:border-indigo-500/60 focus:ring-2 focus:ring-indigo-500/20 ${error ? 'border-red-500/60' : ''} ${className}`}
        {...props}
      />
      {hint && !error && <p className="mt-1.5 text-xs text-[var(--color-muted)]">{hint}</p>}
      {error && <p className="mt-1.5 text-xs text-red-400">{error}</p>}
    </label>
  )
}

export function Textarea({ label, hint, error, className = '', rows = 4, ...props }) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1.5 block text-sm font-medium text-slate-300">{label}</span>
      )}
      <textarea
        rows={rows}
        className={`w-full resize-y rounded-lg border border-[var(--color-border)] bg-[#0a0d12] px-3.5 py-2.5 text-sm text-white placeholder:text-slate-600 outline-none transition focus:border-indigo-500/60 focus:ring-2 focus:ring-indigo-500/20 ${error ? 'border-red-500/60' : ''} ${className}`}
        {...props}
      />
      {hint && !error && <p className="mt-1.5 text-xs text-[var(--color-muted)]">{hint}</p>}
      {error && <p className="mt-1.5 text-xs text-red-400">{error}</p>}
    </label>
  )
}

export function Checkbox({ label, description, ...props }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-[var(--color-border)] bg-[#0a0d12]/50 p-3.5 transition hover:border-indigo-500/30">
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-slate-600 bg-slate-900 text-indigo-600 focus:ring-indigo-500/30"
        {...props}
      />
      <span>
        <span className="block text-sm font-medium text-slate-200">{label}</span>
        {description && (
          <span className="mt-0.5 block text-xs text-[var(--color-muted)]">{description}</span>
        )}
      </span>
    </label>
  )
}
