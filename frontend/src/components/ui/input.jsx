import { cn } from '@/lib/utils'

export function Input({ className, type, ...props }) {
  return (
    <input
      type={type}
      className={cn(
        'h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30',
        className,
      )}
      {...props}
    />
  )
}

export function Label({ className, ...props }) {
  return (
    <label
      className={cn('text-sm font-medium leading-none select-none', className)}
      {...props}
    />
  )
}

export function Textarea({ className, ...props }) {
  return (
    <textarea
      className={cn(
        'flex min-h-16 w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30',
        className,
      )}
      {...props}
    />
  )
}

export function Switch({ checked, onCheckedChange, className, ...props }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onCheckedChange?.(!checked)}
      className={cn(
        'relative inline-flex h-[18px] w-8 shrink-0 items-center rounded-full transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50',
        checked ? 'bg-primary' : 'bg-input dark:bg-input/80',
        className,
      )}
      {...props}
    >
      <span
        className={cn(
          'block size-3.5 rounded-full bg-background transition-transform dark:bg-primary-foreground',
          checked ? 'translate-x-[calc(100%-2px)]' : 'translate-x-0.5',
        )}
      />
    </button>
  )
}

export function Separator({ className, orientation = 'horizontal', ...props }) {
  return (
    <div
      role="separator"
      className={cn(
        'shrink-0 bg-border',
        orientation === 'horizontal' ? 'h-px w-full' : 'h-full w-px',
        className,
      )}
      {...props}
    />
  )
}

export function Progress({ value = 0, className }) {
  return (
    <div className={cn('relative h-1 w-full overflow-hidden rounded-full bg-muted', className)}>
      <div
        className="h-full bg-primary transition-all duration-500"
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  )
}
