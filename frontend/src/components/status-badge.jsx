import {
  CheckCircle2,
  CircleDashed,
  Loader2,
  XCircle,
  Ban,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const taskConfig = {
  queued: {
    label: 'Queued',
    icon: CircleDashed,
    className: 'bg-muted text-muted-foreground border-border',
  },
  running: {
    label: 'Running',
    icon: Loader2,
    className: 'bg-info/10 text-info border-info/20',
    spin: true,
  },
  success: {
    label: 'Success',
    icon: CheckCircle2,
    className: 'bg-success/10 text-success border-success/20',
  },
  failed: {
    label: 'Failed',
    icon: XCircle,
    className: 'bg-destructive/10 text-destructive border-destructive/20',
  },
  cancelled: {
    label: 'Cancelled',
    icon: Ban,
    className: 'bg-muted text-muted-foreground border-border',
  },
}

export function StatusBadge({ status, className }) {
  const key = (status || 'queued').toLowerCase()
  const c = taskConfig[key] || taskConfig.queued
  const Icon = c.icon
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium',
        c.className,
        className,
      )}
    >
      <Icon className={cn('size-3', c.spin && 'animate-spin')} />
      {c.label}
    </span>
  )
}

const indexConfig = {
  indexed: {
    label: 'Indexed',
    className: 'bg-success/10 text-success border-success/20',
  },
  indexing: {
    label: 'Indexing',
    className: 'bg-info/10 text-info border-info/20',
  },
  not_indexed: {
    label: 'Not indexed',
    className: 'bg-muted text-muted-foreground border-border',
  },
  failed: {
    label: 'Failed',
    className: 'bg-destructive/10 text-destructive border-destructive/20',
  },
}

export function IndexBadge({ status }) {
  const c = indexConfig[status] || indexConfig.not_indexed
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium',
        c.className,
      )}
    >
      {status === 'indexing' && <Loader2 className="size-3 animate-spin" />}
      {c.label}
    </span>
  )
}
