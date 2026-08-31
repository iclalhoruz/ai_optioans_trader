import { GlassPanel } from "@/components/ui/GlassPanel"
import { Icon } from "@/components/ui/Icon"
import { InfoTooltip } from "@/components/ui/InfoTooltip"
import { cn } from "@/lib/cn"
import type { GlossaryTerm } from "@/lib/glossary"
import type { PipelineStep, PipelineStepStatus } from "@/types/domain"

interface PipelineTimelineProps {
  steps: PipelineStep[]
}

// Same two terms as the Dashboard stepper get a tooltip here - kept in sync
// so both screens explain the same steps the same way.
const STEP_GLOSSARY: Partial<Record<string, GlossaryTerm>> = {
  chaos_result: "chaosSandbox",
  risk_result: "riskGate",
}

const CIRCLE_CLASSES: Record<PipelineStepStatus, string> = {
  success: "bg-surface-container-low border border-tertiary text-tertiary shadow-[0_0_8px_rgba(57,251,136,0.3)]",
  running: "bg-primary-container/20 border border-primary-container text-primary-container neon-pulse",
  pending: "bg-surface-container-highest border border-outline-variant text-outline-variant",
  failed: "bg-error-container/30 border border-error text-error shadow-[0_0_12px_rgba(255,180,171,0.5)]",
}

const LABEL_CLASSES: Record<PipelineStepStatus, string> = {
  success: "text-on-surface",
  running: "text-primary-container neon-text-cyan",
  pending: "text-on-surface-variant",
  failed: "text-error drop-shadow-[0_0_4px_rgba(255,180,171,0.3)]",
}

const DESCRIPTION_CLASSES: Record<PipelineStepStatus, string> = {
  success: "text-on-surface-variant",
  running: "text-on-surface-variant",
  pending: "text-on-surface-variant",
  failed: "text-error",
}

function stepIcon(step: PipelineStep): { name: string; spin?: boolean } {
  switch (step.status) {
    case "success":
      return { name: "check" }
    case "running":
      return { name: "sync", spin: true }
    case "failed":
      return { name: "warning" }
    case "pending":
      return { name: step.icon }
  }
}

// Line-after-step-N is colored by whether the NEXT step succeeded, failed,
// or hasn't run yet - it represents the outcome of the transition, not the
// step it starts from.
function lineClassForNext(nextStatus: PipelineStepStatus | undefined): string | null {
  if (!nextStatus) return null
  if (nextStatus === "success" || nextStatus === "running") return "step-line-active"
  if (nextStatus === "failed") return "step-line-error"
  return "step-line"
}

export function PipelineTimeline({ steps }: PipelineTimelineProps) {
  return (
    <GlassPanel className="relative flex flex-col gap-6 p-container-padding">
      {steps.map((step, index) => {
        const icon = stepIcon(step)
        const lineClass = lineClassForNext(steps[index + 1]?.status)

        return (
          <div
            key={step.id}
            className={cn("relative z-10 flex items-start gap-4", step.status === "pending" && "opacity-40")}
          >
            {lineClass && <div className={cn("step-line", lineClass !== "step-line" && lineClass)} />}
            <div className={cn("z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full", CIRCLE_CLASSES[step.status])}>
              <Icon name={icon.name} className={cn("text-[16px]", icon.spin && "animate-spin")} />
            </div>
            <div>
              <h4 className={cn("flex items-center gap-1 font-data-mono-lg text-data-mono-lg", LABEL_CLASSES[step.status])}>
                {index + 1}. {step.label}
                <InfoTooltip term={STEP_GLOSSARY[step.id]} />
              </h4>
              {step.description && (
                <p className={cn("mt-1 font-data-mono-sm text-data-mono-sm", DESCRIPTION_CLASSES[step.status])}>
                  {step.description}
                </p>
              )}
            </div>
          </div>
        )
      })}
    </GlassPanel>
  )
}
