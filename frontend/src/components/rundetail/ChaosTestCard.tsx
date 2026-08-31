import { GlassPanel } from "@/components/ui/GlassPanel"
import { ProgressBar } from "@/components/ui/ProgressBar"
import type { ChaosSandboxState } from "@/types/domain"

interface ChaosTestCardProps {
  sandbox: ChaosSandboxState
}

export function ChaosTestCard({ sandbox }: ChaosTestCardProps) {
  const score = sandbox.survivalScorePct ?? 0

  return (
    <GlassPanel className="flex flex-col gap-4 p-container-padding">
      <h4 className="border-b border-outline-variant pb-2 font-data-mono-lg text-data-mono-lg text-on-surface">
        Chaos Test
      </h4>
      <div className="flex items-center justify-between">
        <span className="font-label-caps text-label-caps text-on-surface-variant">Survival Score</span>
        <span className="font-data-mono-lg text-data-mono-lg text-tertiary neon-glow">{score}%</span>
      </div>
      <ProgressBar percent={score} tone="success" />
      {sandbox.summary && (
        <p className="mt-2 font-data-mono-sm text-data-mono-sm text-on-surface-variant">{sandbox.summary}</p>
      )}
    </GlassPanel>
  )
}
