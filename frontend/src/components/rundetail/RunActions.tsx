import { Icon } from "@/components/ui/Icon"
import type { RunStatus } from "@/types/domain"

interface RunActionsProps {
  status: RunStatus
}

// "Modify Parameters" only makes sense for a run that didn't go through -
// there's nothing to modify on an already-executed or still-running trade.
// Presentational only for now - no backend endpoint exists yet to resubmit
// a run with edited parameters. There is no "Override veto" action,
// deliberately: the risk gate's whole premise is a hard veto with no
// exceptions (see contracts/schemas.py's RiskResult, CLAUDE.md) - a button
// that lets a human override it would contradict that.
export function RunActions({ status }: RunActionsProps) {
  if (status !== "vetoed" && status !== "failed") return null

  return (
    <div className="mt-4 flex justify-end gap-4">
      <button className="flex items-center gap-2 rounded border border-outline-variant bg-surface-container/50 px-6 py-2 font-label-caps text-label-caps text-on-surface backdrop-blur-sm transition-colors hover:border-outline hover:bg-surface-container-highest">
        <Icon name="tune" className="text-[18px]" />
        Modify Parameters
      </button>
    </div>
  )
}
