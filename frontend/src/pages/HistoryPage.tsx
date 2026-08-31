import { useSearchParams } from "react-router-dom"
import { RunsTable } from "@/components/dashboard/RunsTable"
import { Button } from "@/components/ui/Button"
import { ErrorState } from "@/components/ui/ErrorState"
import { GlassPanel } from "@/components/ui/GlassPanel"
import { Icon } from "@/components/ui/Icon"
import { LoadingState } from "@/components/ui/LoadingState"
import { useRecentRuns } from "@/hooks/useDashboard"

export function HistoryPage() {
  const { data: runs, isPending, isError } = useRecentRuns()
  const [searchParams, setSearchParams] = useSearchParams()
  const symbolFilter = searchParams.get("symbol")

  if (isPending) return <LoadingState label="Loading run history…" />
  if (isError || !runs) return <ErrorState message="Couldn't load run history." />

  const visibleRuns = symbolFilter
    ? runs.filter((run) => run.symbol.toUpperCase() === symbolFilter.toUpperCase())
    : runs

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-stack-lg">
      <div className="flex items-center justify-between">
        <h1 className="font-headline-md text-headline-md text-on-surface">Run History</h1>
        {symbolFilter && (
          <div className="flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 font-data-mono-sm text-xs text-primary-container">
            Showing: {symbolFilter}
            <Button variant="ghost" size="icon" className="h-5 w-5" onClick={() => setSearchParams({})}>
              <Icon name="close" className="text-sm" />
            </Button>
          </div>
        )}
      </div>
      {visibleRuns.length === 0 ? (
        <GlassPanel className="p-16 text-center text-on-surface-variant">
          {symbolFilter ? `No runs found for ${symbolFilter}.` : "No runs yet."}
        </GlassPanel>
      ) : (
        <GlassPanel className="overflow-hidden">
          <RunsTable runs={visibleRuns} />
        </GlassPanel>
      )}
    </div>
  )
}
