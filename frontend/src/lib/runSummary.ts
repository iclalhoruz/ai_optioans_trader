import type { RunDetail, RunStatus } from "@/types/domain"

// One sentence per status instead of an if/else ladder - shared by Dashboard
// and Run Detail so the same run status always reads the same way.
const SUMMARY_BY_STATUS: Record<RunStatus, (run: RunDetail) => string> = {
  running: (run) => `Your AI is analyzing ${run.symbol} and running safety checks before trading.`,
  success: (run) => `This trade on ${run.symbol} passed every safety check and was executed.`,
  vetoed: () => "This trade was blocked automatically before it reached the market.",
  failed: () => "This run stopped early due to an error before a trade could be made.",
}

export function buildRunPlainSummary(run: RunDetail): string {
  return SUMMARY_BY_STATUS[run.status](run)
}
