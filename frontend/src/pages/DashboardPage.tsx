import { AiReasoningPanel } from "@/components/dashboard/AiReasoningPanel"
import { ChaosSandboxPanel } from "@/components/dashboard/ChaosSandboxPanel"
import { PipelineStepper } from "@/components/dashboard/PipelineStepper"
import { RecentRunsTable } from "@/components/dashboard/RecentRunsTable"
import { RiskGatePanel } from "@/components/dashboard/RiskGatePanel"
import { StrategyDecisionCard } from "@/components/dashboard/StrategyDecisionCard"
import { ErrorState } from "@/components/ui/ErrorState"
import { LoadingState } from "@/components/ui/LoadingState"
import { PlainSummary } from "@/components/ui/PlainSummary"
import { StatusDot } from "@/components/ui/StatusDot"
import { useActiveRun, useRecentRuns } from "@/hooks/useDashboard"
import { buildRunPlainSummary } from "@/lib/runSummary"

export function DashboardPage() {
  const activeRunQuery = useActiveRun()
  const recentRunsQuery = useRecentRuns()

  if (activeRunQuery.isPending || recentRunsQuery.isPending) {
    return <LoadingState label="Loading dashboard…" />
  }

  if (activeRunQuery.isError || recentRunsQuery.isError) {
    return <ErrorState message="Couldn't load the dashboard." />
  }

  const run = activeRunQuery.data
  const isProcessing = run.steps.some((step) => step.status === "running")

  return (
    <div className="flex h-full w-full flex-col gap-container-padding md:flex-row">
      <div className="flex flex-1 flex-col gap-container-padding overflow-y-auto">
        <div className="flex items-center justify-between">
          <h1 className="font-headline-md text-headline-md text-on-surface">
            Active Run:{" "}
            <span className="ml-1 font-data-mono-lg text-2xl text-primary-container neon-text-cyan">
              {run.symbol}
            </span>
          </h1>
          {isProcessing && (
            <div className="flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 shadow-[0_0_10px_rgba(0,209,255,0.15)]">
              <StatusDot tone="info" label="Processing" pulse />
            </div>
          )}
        </div>

        <PlainSummary text={buildRunPlainSummary(run)} />
        <PipelineStepper steps={run.steps} />
        <StrategyDecisionCard decision={run.strategy} />
        <RecentRunsTable runs={recentRunsQuery.data} />
      </div>

      <div className="flex w-full flex-col border-l border-outline-variant bg-surface-container-lowest/60 backdrop-blur-md md:w-96">
        <AiReasoningPanel convictionPct={run.strategy.convictionPct} reasoning={run.strategy.reasoning} />
        <ChaosSandboxPanel sandbox={run.chaosSandbox} />
        <RiskGatePanel gate={run.riskGate} />
      </div>
    </div>
  )
}
