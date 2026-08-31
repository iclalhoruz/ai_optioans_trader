export interface NavItem {
  id: string
  label: string
  icon: string
  path: string
}

// Mirrors the pipeline's 5-step chain in workflow/pipeline.py's STEPS
// registry - "success"/"running"/"pending" line up with PipelineState's
// per-step slots being filled or not, "failed" with PipelineStatus.FAILED.
export type PipelineStepStatus = "success" | "running" | "pending" | "failed"

export interface PipelineStep {
  id: string
  label: string
  icon: string
  status: PipelineStepStatus
  // Only rendered by the vertical run-detail timeline - Dashboard's compact
  // horizontal stepper doesn't have room for it.
  description?: string
}

export type TradeAction = "BUY" | "SELL" | "HOLD"
export type StrategyDirection = "bullish" | "bearish"

// Frontend-shaped view of a TradeProposal - once a real read API exists over
// PipelineState this maps from `trade_proposal` + `strategy_id`.
export interface StrategyDecision {
  symbol: string
  action: TradeAction
  direction: StrategyDirection
  description: string
  convictionPct: number
  reasoning: string
}

// Frontend-shaped view of a ChaosTestResult. `logs` maps directly to
// ChaosTestResult.logs: List[str]. `survivalScorePct` is a display-friendly
// inverse of the real `stress_score` field (contracts/schemas.py has LOW
// stress_score = safe; this is HIGH = survived well) - whichever service
// exposes this for real will need `(1 - stress_score) * 100`, not a direct
// passthrough.
export interface ChaosSandboxState {
  status: "running" | "complete" | "pending"
  logs: string[]
  survivalScorePct?: number
  summary?: string
}

export type RiskGateStatus = "pending" | "approved" | "vetoed"

// Frontend-shaped view of a RiskResult - `reason` maps to `veto_reason`.
// Kept as a single opaque string, same as the real contract - not parsed
// into structured sub-fields the backend doesn't actually provide.
export interface RiskGateState {
  status: RiskGateStatus
  reason?: string
}

export type RunStatus = "success" | "vetoed" | "running" | "failed"

// Full record for one pipeline run - used both for "the run currently in
// focus" on the Dashboard and for a historical run's detail page. A run is
// a run regardless of whether it's still going or long finished, so one
// shape covers both instead of two near-duplicate types.
export interface RunDetail {
  runId: string
  symbol: string
  status: RunStatus
  initiatedAt: string
  durationSeconds: number
  steps: PipelineStep[]
  strategy: StrategyDecision
  chaosSandbox: ChaosSandboxState
  riskGate: RiskGateState
}

export interface RunSummary {
  id: string
  symbol: string
  status: RunStatus
  action: TradeAction
  convictionPct: number
}
