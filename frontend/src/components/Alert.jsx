import { AlertCircle, CheckCircle2, Info, XCircle } from 'lucide-react'

const ICONS = {
  info: Info,
  success: CheckCircle2,
  error: XCircle,
  warning: AlertCircle,
}

const STYLES = {
  info: 'border-indigo-500/30 bg-indigo-500/10 text-indigo-200',
  success: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
  error: 'border-red-500/30 bg-red-500/10 text-red-200',
  warning: 'border-amber-500/30 bg-amber-500/10 text-amber-200',
}

export default function Alert({ type = 'info', title, children, onDismiss }) {
  const Icon = ICONS[type]

  return (
    <div className={`flex gap-3 rounded-xl border p-4 text-sm ${STYLES[type]}`}>
      <Icon className="mt-0.5 h-5 w-5 shrink-0 opacity-80" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={title ? 'mt-1 opacity-90' : ''}>{children}</div>}
      </div>
      {onDismiss && (
        <button type="button" onClick={onDismiss} className="opacity-60 hover:opacity-100">
          ×
        </button>
      )}
    </div>
  )
}
