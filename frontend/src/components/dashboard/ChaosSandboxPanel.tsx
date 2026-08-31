import { Badge } from "@/components/ui/Badge"
import { Icon } from "@/components/ui/Icon"
import type { ChaosSandboxState } from "@/types/domain"

interface ChaosSandboxPanelProps {
  sandbox: ChaosSandboxState
}

// logs is a plain List[str] on the wire (see ChaosTestResult.logs in
// contracts/schemas.py) - every line already happened by the time it's in
// the list, so a checkmark next to each is honest; there's no per-line
// status field to fabricate.
export function ChaosSandboxPanel({ sandbox }: ChaosSandboxPanelProps) {
  return (
    <div className="flex flex-1 flex-col border-b border-outline-variant p-container-padding">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="flex items-center gap-2 font-data-mono-sm uppercase tracking-widest text-on-surface-variant">
          <Icon name="science" className="text-sm" />
          Chaos Sandbox
        </h3>
        {sandbox.status === "running" && (
          <Badge tone="info" className="animate-pulse rounded px-2 py-0.5 text-[10px] shadow-[0_0_8px_rgba(0,209,255,0.2)]">
            Running
          </Badge>
        )}
      </div>
      <p className="mb-3 font-body-base text-xs text-on-surface-variant">
        Testing this trade against extreme market scenarios before trusting it.
      </p>
      <div className="relative flex-1 overflow-y-auto rounded-lg border border-primary/20 bg-[#0c0e12] p-4 font-data-mono-sm text-xs shadow-[inset_0_0_15px_rgba(0,209,255,0.05)]">
        {sandbox.status === "running" && <div className="ai-processing absolute inset-0 rounded-lg" />}
        <div className="relative z-10 flex flex-col gap-2.5">
          {sandbox.logs.map((log) => (
            <div key={log} className="flex justify-between gap-4">
              <span className="text-outline-variant">{log}</span>
              <Icon name="check" className="shrink-0 text-sm text-tertiary neon-text-green" />
            </div>
          ))}
          {sandbox.status === "running" && (
            <div className="mt-2 flex justify-between border-t border-outline-variant/30 pt-2">
              <span className="font-bold text-primary-container neon-text-cyan">STRESS TESTING EDGE CASES...</span>
              <span className="animate-pulse font-bold text-primary-container">|</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
