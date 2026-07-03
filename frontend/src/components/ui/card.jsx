import { cn } from '@/lib/utils'

export function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        'flex flex-col gap-4 overflow-hidden rounded-xl bg-card py-4 text-sm text-card-foreground ring-1 ring-foreground/10',
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({ className, ...props }) {
  return <div className={cn('flex flex-col gap-1 px-4', className)} {...props} />
}

export function CardTitle({ className, ...props }) {
  return <div className={cn('text-base font-medium leading-snug', className)} {...props} />
}

export function CardDescription({ className, ...props }) {
  return <div className={cn('text-sm text-muted-foreground', className)} {...props} />
}

export function CardContent({ className, ...props }) {
  return <div className={cn('px-4', className)} {...props} />
}

export function CardFooter({ className, ...props }) {
  return (
    <div
      className={cn('flex items-center rounded-b-xl border-t bg-muted/50 p-4', className)}
      {...props}
    />
  )
}
