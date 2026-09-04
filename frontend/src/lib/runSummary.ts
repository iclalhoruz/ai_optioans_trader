import type { RunDetail, RunStatus } from "@/types/domain"

// One sentence per status instead of an if/else ladder - shared by Dashboard
// and Run Detail so the same run status always reads the same way. "success"
// covers two real outcomes (a HOLD that reached the end of the pipeline with
// nothing to trade, and a BUY that actually executed) - risk-engine approves
// both, since a HOLD has nothing to veto, so this has to check the actual
// action rather than assume "success" always means a trade happened.
const SUMMARY_BY_STATUS: Record<RunStatus, (run: RunDetail) => string> = {
  running: (run) => `Your AI is analyzing ${run.symbol} and running safety checks before trading.`,
  success: (run) =>
    run.strategy.action === "HOLD"
      ? `Your AI reviewed ${run.symbol} and found no trade worth making this cycle.`
      : `This trade on ${run.symbol} passed every safety check and was executed.`,
  vetoed: () => "This trade was blocked automatically before it reached the market.",
  failed: () => "This run stopped early due to an error before a trade could be made.",
}

export function buildRunPlainSummary(run: RunDetail): string {
  return SUMMARY_BY_STATUS[run.status](run)
}
