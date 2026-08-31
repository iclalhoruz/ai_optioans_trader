import { GlassPanel } from "@/components/ui/GlassPanel"
import { InfoChip } from "@/components/ui/InfoChip"
import { ProgressBar } from "@/components/ui/ProgressBar"
import type { StrategyDecision, StrategyDirection } from "@/types/domain"

interface AiIntentCardProps {
  strategy: StrategyDecision
}

const DIRECTION_CONTENT: Record<StrategyDirection, { label: string; className: string }> = {
  bullish: { label: "Bullish", className: "text-tertiary" },
  bearish: { label: "Bearish", className: "text-error" },
}

export function AiIntentCard({ strategy }: AiIntentCardProps) {
  return (
    <GlassPanel className="flex flex-col gap-4 p-container-padding">
      <h4 className="border-b border-outline-variant pb-2 font-data-mono-lg text-data-mono-lg text-on-surface">
        AI Intent
      </h4>
      <div className="flex items-center justify-between">
        <span className="font-label-caps text-label-caps text-on-surface-variant">Confidence</span>
        <span className="font-data-mono-lg text-data-mono-lg text-primary neon-glow">{strategy.convictionPct}%</span>
      </div>
      <ProgressBar percent={strategy.convictionPct} tone="primary" />
      <div className="mt-2 grid grid-cols-2 gap-2">
        <InfoChip
          label="Direction"
          value={DIRECTION_CONTENT[strategy.direction].label}
          valueClassName={DIRECTION_CONTENT[strategy.direction].className}
        />
        <InfoChip label="Strategy" value={strategy.description} tooltipTerm="optionsStrategy" />
      </div>
    </GlassPanel>
  )
}
