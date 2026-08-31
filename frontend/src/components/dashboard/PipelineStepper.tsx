import { GlassPanel } from "@/components/ui/GlassPanel"
import { Icon } from "@/components/ui/Icon"
import { InfoTooltip } from "@/components/ui/InfoTooltip"
import { cn } from "@/lib/cn"
import type { GlossaryTerm } from "@/lib/glossary"
import type { PipelineStep, PipelineStepStatus } from "@/types/domain"

interface PipelineStepperProps {
  steps: PipelineStep[]
}

// Only the two steps whose names aren't self-explanatory get a tooltip -
// "Market Data"/"AI Strategy"/"Execute" don't need one.
const STEP_GLOSSARY: Partial<Record<string, GlossaryTerm>> = {
  chaos_result: "chaosSandbox",
  risk_result: "riskGate",
}

// One entry per status instead of an if/else ladder in the render - a
// completed step always shows a checkmark and the running one always shows
// a spinner, regardless of what icon the step itself carries; only a step
// that hasn't been reached yet shows its own real icon.
const CIRCLE_CLASSES: Record<PipelineStepStatus, string> = {
  success: "bg-tertiary/20 border border-tertiary text-tertiary shadow-[0_0_15px_rgba(57,251,136,0.3)]",
  running: "bg-primary-container/20 border-2 border-primary-container text-primary-container neon-pulse",
  pending: "bg-surface-container border border-outline text-outline",
  failed: "bg-error/20 border border-error text-error shadow-[0_0_15px_rgba(255,180,171,0.2)]",
}

const LABEL_CLASSES: Record<PipelineStepStatus, string> = {
  success: "text-on-surface",
  running: "font-bold text-primary-container neon-text-cyan",
  pending: "text-outline",
  failed: "font-bold text-error",
}

function stepIcon(step: PipelineStep): { name: string; spin?: boolean; glowClass?: string } {
  switch (step.status) {
    case "success":
      return { name: "check", glowClass: "neon-text-green" }
    case "running":
      return { name: "sync", spin: true, glowClass: "neon-text-cyan" }
    case "failed":
      return { name: "close" }
    case "pending":
      return { name: step.icon }
  }
}

function computeProgressPercent(steps: PipelineStep[]): number {
  if (steps.length < 2) return 0

  const runningIndex = steps.findIndex((step) => step.status === "running")
  if (runningIndex !== -1) return (runningIndex / (steps.length - 1)) * 100

  const lastSuccessIndex = steps.reduce((acc, step, index) => (step.status === "success" ? index : acc), -1)
  return ((lastSuccessIndex + 1) / (steps.length - 1)) * 100
}

export function PipelineStepper({ steps }: PipelineStepperProps) {
  const progressPercent = computeProgressPercent(steps)

  return (
    <GlassPanel className="relative overflow-hidden p-container-padding">
      <h2 className="relative z-10 mb-6 flex items-center gap-2 font-data-mono-sm uppercase tracking-widest text-on-surface-variant">
        <Icon name="timeline" className="text-sm" />
        Execution Pipeline
      </h2>
      <div className="relative z-10 flex w-full items-center justify-between px-4">
        {/* Inset wrapper so both lines' widths are relative to the same
            (already-inset) span - avoids fighting calc() to line up a
            percentage-width overlay against left/right-inset siblings. */}
        <div className="absolute inset-x-8 top-1/2 -translate-y-1/2">
          <div className="h-px bg-outline-variant" />
          <div
            className="absolute inset-y-0 left-0 h-px bg-primary-container shadow-[0_0_8px_rgba(0,209,255,0.6)]"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        {steps.map((step) => {
          const icon = stepIcon(step)
          return (
            <div
              key={step.id}
              className={cn("relative z-10 flex flex-col items-center gap-2", step.status === "pending" && "opacity-60")}
            >
              <div className={cn("flex h-8 w-8 items-center justify-center rounded-full", CIRCLE_CLASSES[step.status])}>
                <Icon name={icon.name} className={cn("text-sm", icon.spin && "animate-spin", icon.glowClass)} />
              </div>
              <span className={cn("flex items-center gap-1 font-data-mono-sm text-xs", LABEL_CLASSES[step.status])}>
                {step.label}
                <InfoTooltip term={STEP_GLOSSARY[step.id]} />
              </span>
            </div>
          )
        })}
      </div>
    </GlassPanel>
  )
}
