import { useNavigate } from "react-router-dom"
import { RunsTable } from "@/components/dashboard/RunsTable"
import { GlassPanel } from "@/components/ui/GlassPanel"
import { Icon } from "@/components/ui/Icon"
import type { RunSummary } from "@/types/domain"

interface RecentRunsTableProps {
  runs: RunSummary[]
}

export function RecentRunsTable({ runs }: RecentRunsTableProps) {
  const navigate = useNavigate()

  return (
    <GlassPanel className="flex min-h-[250px] flex-1 flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b border-outline-variant/40 bg-surface-container-low/40 p-4">
        <h2 className="flex items-center gap-2 font-data-mono-sm uppercase tracking-widest text-on-surface-variant">
          <Icon name="list_alt" className="text-sm" />
          Recent Runs
        </h2>
        <button
          onClick={() => navigate("/history")}
          className="font-data-mono-sm text-xs text-primary-container transition-colors hover:text-primary hover:underline"
        >
          View All
        </button>
      </div>
      <RunsTable runs={runs} />
    </GlassPanel>
  )
}
