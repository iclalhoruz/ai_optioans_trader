import { GlassPanel } from "@/components/ui/GlassPanel"
import { Icon } from "@/components/ui/Icon"
import { InfoTooltip } from "@/components/ui/InfoTooltip"
import { cn } from "@/lib/cn"
import type { RiskGateState, RiskGateStatus } from "@/types/domain"

interface VerdictBannerProps {
  gate: RiskGateState
}

// One entry per verdict instead of an if/else ladder - every risk-engine
// outcome (contracts/schemas.py RiskResult.is_approved) gets its own tone,
// icon, and headline here.
const VERDICT_CONTENT: Record<
  RiskGateStatus,
  { icon: string; title: string; toneClass: string; badge: string }
> = {
  vetoed: {
    icon: "block",
    title: "VETOED: Hard-rule violation",
    toneClass: "border-l-error red-alert hazard-pulse",
    badge: "Deterministic / Hard Gate",
  },
  approved: {
    icon: "verified",
    title: "APPROVED: Cleared all hard gates",
    toneClass: "border-l-tertiary",
    badge: "Deterministic / Hard Gate",
  },
  pending: {
    icon: "hourglass_empty",
    title: "PENDING: Awaiting risk evaluation",
    toneClass: "border-l-outline-variant",
    badge: "Deterministic / Hard Gate",
  },
}

export function VerdictBanner({ gate }: VerdictBannerProps) {
  const content = VERDICT_CONTENT[gate.status]

  return (
    <GlassPanel className={cn("relative overflow-hidden border-l-4 p-6", content.toneClass)}>
      <div className="pointer-events-none absolute -right-10 -top-10 opacity-10">
        <Icon name="gavel" className="text-[200px]" />
      </div>
      <div className="relative z-10 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 font-headline-md text-headline-md font-bold">
            <Icon name={content.icon} />
            {content.title}
          </h3>
          <span className="flex items-center gap-1.5 rounded border border-outline-variant bg-surface-container-low px-3 py-1 font-label-caps text-label-caps text-outline">
            {content.badge}
            <InfoTooltip term="hardGate" />
          </span>
        </div>
        {gate.reason && (
          <div className="rounded-lg border border-error/30 bg-surface-container-lowest/80 p-4 font-data-mono-sm text-data-mono-sm shadow-inner">
            <span className="text-on-surface-variant">Reason:</span>
            <br />
            <span className="text-on-surface">{gate.reason}</span>
          </div>
        )}
      </div>
    </GlassPanel>
  )
}
