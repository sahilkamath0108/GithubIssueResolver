import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'

export function StatCard({ label, value, icon: Icon, hint, accent }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span
          className={cn(
            'flex size-8 items-center justify-center rounded-lg',
            accent === 'info' && 'bg-info/10 text-info',
            accent === 'warning' && 'bg-warning/10 text-warning',
            accent === 'destructive' && 'bg-destructive/10 text-destructive',
            (!accent || accent === 'primary') && 'bg-primary/10 text-primary',
          )}
        >
          <Icon className="size-4" />
        </span>
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </Card>
  )
}
