import { InfoTooltip } from "@/components/ui/InfoTooltip"
import { cn } from "@/lib/cn"
import type { GlossaryTerm } from "@/lib/glossary"

interface InfoChipProps {
  label: string
  value: string
  valueClassName?: string
  tooltipTerm?: GlossaryTerm
}

// Small label-over-value box - Direction/Strategy on the run detail page
// today, reusable anywhere a compact fact needs its own boxed slot.
export function InfoChip({ label, value, valueClassName, tooltipTerm }: InfoChipProps) {
  return (
    <div className="cyber-chip flex flex-col rounded p-2">
      <span className="flex items-center gap-1 font-label-caps text-label-caps text-outline">
        {label}
        <InfoTooltip term={tooltipTerm} />
      </span>
      <span className={cn("font-data-mono-sm text-data-mono-sm text-on-surface", valueClassName)}>{value}</span>
    </div>
  )
}
