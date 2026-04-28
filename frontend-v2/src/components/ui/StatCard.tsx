import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

/* ── Variant definitions ── */
const cardVariants = cva(
  'relative rounded-sm border bg-surface px-5 py-4 transition-all duration-200 hover:border-neon/40',
  {
    variants: {
      variant: {
        default: 'border-border',
        warning: 'border-l-[3px] border-l-critical border-t-border border-r-border border-b-border bg-critical/5',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

/* ── Count-up hook ── */
function useCountUp(target: number, duration = 1200) {
  const [current, setCurrent] = useState(0)
  const frameRef = useRef<number>(0)
  const startRef = useRef<number | null>(null)

  useEffect(() => {
    // Don't animate strings or NaN
    if (!Number.isFinite(target)) {
      setCurrent(target)
      return
    }

    startRef.current = null

    const step = (timestamp: number) => {
      if (startRef.current === null) startRef.current = timestamp
      const elapsed = timestamp - startRef.current
      const progress = Math.min(elapsed / duration, 1)

      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3)
      setCurrent(eased * target)

      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step)
      } else {
        setCurrent(target)
      }
    }

    frameRef.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frameRef.current)
  }, [target, duration])

  return current
}

/* ── Formatting helpers ── */
function formatValue(raw: number, display: string): string {
  // If the display string has a % or decimal, preserve that format
  if (display.includes('%')) {
    const decimals = display.split('.')[1]?.replace('%', '').length ?? 0
    return raw.toFixed(decimals) + '%'
  }
  if (display.includes('.')) {
    const decimals = display.split('.')[1]?.length ?? 0
    return raw.toFixed(decimals)
  }
  // Large integers get comma-separated
  return Math.round(raw).toLocaleString('en-US')
}

/* ── Props ── */
export interface StatCardProps extends VariantProps<typeof cardVariants> {
  /** Label above the big number */
  title: string
  /** Display string — e.g. "94.2%", "1,402", "4.2" */
  value: string
  /** Delta text, e.g. "↑2.1%  vs last 24h" */
  delta?: string
  /** Green (true) or red (false) delta color */
  deltaPositive?: boolean
  /** Optional icon rendered top-right */
  icon?: ReactNode
  /** Custom content below the value (e.g. progress bar) */
  children?: ReactNode
  /** Additional classes */
  className?: string
}

export default function StatCard({
  title,
  value,
  delta,
  deltaPositive = true,
  icon,
  variant,
  children,
  className,
}: StatCardProps) {
  // Parse numeric part of value for the count-up
  const numericTarget = parseFloat(value.replace(/[^0-9.\-]/g, '')) || 0
  const animatedValue = useCountUp(numericTarget)

  return (
    <div className={cn(cardVariants({ variant }), className)}>
      {/* Header row */}
      <div className="flex items-start justify-between">
        <span className="text-[11px] font-semibold tracking-[0.15em] uppercase text-muted">
          {title}
        </span>
        {icon && (
          <span className="text-muted">{icon}</span>
        )}
      </div>

      {/* Big value */}
      <p className="mt-2 font-display text-3xl font-bold leading-none text-text">
        {formatValue(animatedValue, value)}
      </p>

      {/* Delta */}
      {delta && (
        <p
          className={cn(
            'mt-1.5 text-[11px] tracking-wide',
            deltaPositive ? 'text-neon-dim' : 'text-critical'
          )}
        >
          {delta}
        </p>
      )}

      {/* Optional custom content (progress bar, etc.) */}
      {children}
    </div>
  )
}
