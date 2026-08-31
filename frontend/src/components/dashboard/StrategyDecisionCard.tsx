import { Badge } from "@/components/ui/Badge"
import { GlassPanel } from "@/components/ui/GlassPanel"
import { Icon } from "@/components/ui/Icon"
import { InfoTooltip } from "@/components/ui/InfoTooltip"
import { ProgressBar } from "@/components/ui/ProgressBar"
import { ACTION_BADGE_TONE } from "@/lib/tradeAction"
import type { StrategyDecision } from "@/types/domain"

interface StrategyDecisionCardProps {
  decision: StrategyDecision
}

export function StrategyDecisionCard({ decision }: StrategyDecisionCardProps) {
  return (
    <GlassPanel className="border-l-4 border-l-tertiary p-container-padding shadow-[-2px_0_10px_rgba(57,251,136,0.2)]">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <Icon name="psychology" className="text-sm text-tertiary neon-text-green" />
            <h3 className="font-data-mono-sm font-bold uppercase tracking-wider text-on-surface">
              Strategy Generated
            </h3>
          </div>
          <p className="font-body-base text-sm text-outline">Model complete. Target identified.</p>
        </div>
        <div className="flex items-center gap-2 rounded-md border border-outline-variant bg-surface-container-highest/50 px-3 py-1">
          <span className="font-data-mono-sm text-xs text-outline">Target</span>
          <span className="font-data-mono-sm font-bold text-on-surface">{decision.symbol}</span>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-stack-md rounded-lg border border-outline-variant/50 bg-surface-container-lowest/40 p-4">
        <div className="flex flex-col gap-1">
          <span className="font-data-mono-sm text-[10px] uppercase tracking-widest text-outline">
            Recommended Action
          </span>
          <div className="mt-1 flex items-center gap-2">
            <Badge tone={ACTION_BADGE_TONE[decision.action]} className="rounded px-3 py-1 text-sm">
              {decision.action}
            </Badge>
            <span className="flex items-center gap-1 font-data-mono-sm text-on-surface">
              {decision.description}
              <InfoTooltip term="optionsStrategy" />
            </span>
          </div>
        </div>
        <div className="flex flex-col justify-center gap-1">
          <div className="mb-1 flex w-full items-center justify-between">
            <span className="font-data-mono-sm text-[10px] uppercase tracking-widest text-outline">Confidence</span>
            <span className="font-data-mono-sm font-bold text-primary-container neon-text-cyan">
              {decision.convictionPct}%
            </span>
          </div>
          <ProgressBar percent={decision.convictionPct} />
        </div>
      </div>
    </GlassPanel>
  )
}
