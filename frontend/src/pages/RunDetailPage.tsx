import { useParams } from "react-router-dom"
import { AiIntentCard } from "@/components/rundetail/AiIntentCard"
import { ChaosTestCard } from "@/components/rundetail/ChaosTestCard"
import { PipelineTimeline } from "@/components/rundetail/PipelineTimeline"
import { RunActions } from "@/components/rundetail/RunActions"
import { RunContextHeader } from "@/components/rundetail/RunContextHeader"
import { VerdictBanner } from "@/components/rundetail/VerdictBanner"
import { ErrorState } from "@/components/ui/ErrorState"
import { LoadingState } from "@/components/ui/LoadingState"
import { PlainSummary } from "@/components/ui/PlainSummary"
import { useRunDetail } from "@/hooks/useDashboard"
import { buildRunPlainSummary } from "@/lib/runSummary"

export function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const { data: run, isPending, isError } = useRunDetail(runId ?? "")

  if (isPending) return <LoadingState label="Loading run…" />
  if (isError || !run) return <ErrorState message="Couldn't find that run." />

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-container-padding">
      <RunContextHeader
        runId={run.runId}
        symbol={run.symbol}
        status={run.status}
        initiatedAt={run.initiatedAt}
        durationSeconds={run.durationSeconds}
      />
      <PlainSummary text={buildRunPlainSummary(run)} />
      <div className="grid grid-cols-1 gap-container-padding lg:grid-cols-12">
        <div className="flex flex-col gap-stack-md lg:col-span-4">
          <h3 className="font-headline-md text-headline-md text-on-surface">Execution Pipeline</h3>
          <PipelineTimeline steps={run.steps} />
        </div>
        <div className="flex flex-col gap-container-padding lg:col-span-8">
          <VerdictBanner gate={run.riskGate} />
          <div className="grid grid-cols-1 gap-container-padding md:grid-cols-2">
            <AiIntentCard strategy={run.strategy} />
            <ChaosTestCard sandbox={run.chaosSandbox} />
          </div>
          <RunActions status={run.status} />
        </div>
      </div>
    </div>
  )
}
