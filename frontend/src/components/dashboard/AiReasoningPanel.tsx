import { Icon } from "@/components/ui/Icon"
import { RadialGauge } from "@/components/ui/RadialGauge"

interface AiReasoningPanelProps {
  convictionPct: number
  reasoning: string
}

export function AiReasoningPanel({ convictionPct, reasoning }: AiReasoningPanelProps) {
  return (
    <div className="border-b border-outline-variant p-container-padding">
      <h3 className="mb-4 flex items-center gap-2 font-data-mono-sm uppercase tracking-widest text-on-surface-variant">
        <Icon name="memory" className="text-sm" />
        AI Reasoning
      </h3>
      <div className="mb-4 flex items-center justify-center py-4">
        <RadialGauge percent={convictionPct} label="Confidence" />
      </div>
      <div className="rounded-lg border border-primary/20 bg-surface-container-low/50 p-4 shadow-[inset_0_0_10px_rgba(0,209,255,0.05)]">
        <p className="font-data-mono-sm text-sm leading-relaxed text-on-surface">
          <span className="mr-1 text-primary-container neon-text-cyan">&gt;</span> {reasoning}
        </p>
      </div>
    </div>
  )
}
