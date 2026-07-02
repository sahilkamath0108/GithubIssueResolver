export default function Card({ children, className = '', glow = false }) {
  return (
    <div
      className={`glass-panel rounded-2xl p-6 ${glow ? 'shadow-[0_0_40px_-12px_rgba(99,102,241,0.25)]' : ''} ${className}`}
    >
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, action }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        {title && <h2 className="text-lg font-semibold text-white">{title}</h2>}
        {subtitle && <p className="mt-1 text-sm text-[var(--color-muted)]">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}
