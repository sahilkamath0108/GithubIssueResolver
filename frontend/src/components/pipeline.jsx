import {
  Check,
  FileSearch,
  GitPullRequest,
  ListTodo,
  Loader2,
  PenLine,
  TestTube,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const stepIcons = {
  plan: ListTodo,
  search: FileSearch,
  write: PenLine,
  test: TestTube,
  pr: GitPullRequest,
}

export function Pipeline({ steps }) {
  return (
    <div className="flex items-center">
      {steps.map((step, i) => {
        const Icon = stepIcons[step.key]
        const isLast = i === steps.length - 1
        return (
          <div key={step.key} className={cn('flex items-center', !isLast && 'flex-1')}>
            <div className="flex flex-col items-center gap-2">
              <div
                className={cn(
                  'flex size-9 items-center justify-center rounded-full border transition-colors',
                  step.status === 'done' && 'border-success/30 bg-success/10 text-success',
                  step.status === 'running' && 'border-info/30 bg-info/10 text-info',
                  step.status === 'failed' && 'border-destructive/30 bg-destructive/10 text-destructive',
                  (step.status === 'pending' || step.status === 'skipped') &&
                    'border-border bg-muted/40 text-muted-foreground',
                )}
              >
                {step.status === 'done' ? (
                  <Check className="size-4" />
                ) : step.status === 'failed' ? (
                  <X className="size-4" />
                ) : step.status === 'running' ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Icon className="size-4" />
                )}
              </div>
              <span
                className={cn(
                  'text-xs font-medium',
                  step.status === 'pending' || step.status === 'skipped'
                    ? 'text-muted-foreground'
                    : 'text-foreground',
                )}
              >
                {step.label}
              </span>
            </div>
            {!isLast && (
              <div
                className={cn(
                  'mx-2 h-px flex-1 -translate-y-3 transition-colors',
                  step.status === 'done' ? 'bg-success/40' : 'bg-border',
                )}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

export function PipelineCompact({ steps }) {
  return (
    <div className="flex items-center gap-1">
      {steps.map((step) => (
        <span
          key={step.key}
          title={`${step.label}: ${step.status}`}
          className={cn(
            'h-1.5 w-6 rounded-full',
            step.status === 'done' && 'bg-success',
            step.status === 'running' && 'animate-pulse bg-info',
            step.status === 'failed' && 'bg-destructive',
            (step.status === 'pending' || step.status === 'skipped') && 'bg-border',
          )}
        />
      ))}
    </div>
  )
}
