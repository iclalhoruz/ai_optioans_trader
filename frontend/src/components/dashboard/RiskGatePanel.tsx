import { Icon } from "@/components/ui/Icon"
import { InfoTooltip } from "@/components/ui/InfoTooltip"
import { cn } from "@/lib/cn"
import type { RiskGateState, RiskGateStatus } from "@/types/domain"

interface RiskGatePanelProps {
  gate: RiskGateState
}

// One entry per status instead of an if/else ladder - each maps to a
// RiskResult verdict (contracts/schemas.py): pending = risk-engine hasn't
// run, approved = is_approved=true, vetoed = is_approved=false + veto_reason.
const STATUS_CONTENT: Record<RiskGateStatus, { icon: string; label: string; className: string }> = {
  pending: { icon: "lock_clock", label: "Pending", className: "border-dashed border-outline-variant text-outline" },
  approved: { icon: "verified", label: "Approved", className: "border-tertiary/40 text-tertiary" },
  vetoed: { icon: "block", label: "Vetoed", className: "border-error/40 text-error" },
}

export function RiskGatePanel({ gate }: RiskGatePanelProps) {
  const content = STATUS_CONTENT[gate.status]

  return (
    <div className="bg-surface-container-lowest/80 p-container-padding">
      <h3 className="mb-4 flex items-center gap-2 font-data-mono-sm uppercase tracking-widest text-on-surface-variant">
        <Icon name="security" className="text-sm" />
        Risk Gate
        <InfoTooltip term="riskGate" />
      </h3>
      <div
        className={cn(
          "flex w-full flex-col items-center justify-center rounded-lg border bg-surface-container-low/20 p-6",
          content.className,
        )}
      >
        <Icon name={content.icon} className="mb-2 text-3xl opacity-70" />
        <span className="font-data-mono-sm text-sm font-bold uppercase tracking-[0.15em]">{content.label}</span>
        {gate.status === "pending" && (
          <span className="mt-2 text-center font-data-mono-sm text-xs text-outline-variant">
            Waiting for the safety test to finish
          </span>
        )}
        {gate.status === "vetoed" && gate.reason && (
          <span className="mt-2 text-center font-data-mono-sm text-xs text-outline-variant">{gate.reason}</span>
        )}
      </div>
    </div>
  )
}
