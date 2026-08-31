import type { ChaosSandboxState, PipelineStep, RiskGateState, RunDetail, RunSummary, StrategyDecision } from "@/types/domain"

// Keyed by runId so both "the currently active run" and "look up run X by
// id" (the history drill-down) read from one map instead of two mock lists
// that could drift out of sync.
export const MOCK_RUN_DETAILS: Record<string, RunDetail> = {
  "run-8f21": {
    runId: "run-8f21",
    symbol: "AAPL",
    status: "running",
    initiatedAt: "2026-08-30T14:02:11Z",
    durationSeconds: 12,
    steps: [
      { id: "market_context", label: "Market Data", icon: "monitoring", status: "success" },
      { id: "trade_proposal", label: "AI Strategy", icon: "psychology", status: "success" },
      { id: "chaos_result", label: "Chaos Sandbox", icon: "science", status: "running" },
      { id: "risk_result", label: "Risk Gate", icon: "gavel", status: "pending" },
      { id: "execution", label: "Execute", icon: "send", status: "pending" },
    ],
    strategy: {
      symbol: "AAPL",
      action: "BUY",
      direction: "bullish",
      description: "Call Spread (180/185)",
      convictionPct: 88,
      reasoning:
        "Recent price action and trading volume suggest AAPL is likely to keep rising in the short term.",
    },
    chaosSandbox: {
      status: "running",
      logs: [
        "Initializing Monte Carlo simulation...",
        "Injected 500% spread...",
        "IV Crush -80%...",
        "Liquidity shock scenario A-3...",
        "Stress testing edge cases...",
      ],
    },
    riskGate: { status: "pending" },
  },

  "run-6e91": {
    runId: "run-6e91",
    symbol: "TSLA",
    status: "vetoed",
    initiatedAt: "2026-05-12T09:41:22Z",
    durationSeconds: 4.2,
    steps: [
      {
        id: "market_context",
        label: "Market Data",
        icon: "monitoring",
        status: "success",
        description: "Order book, sentiment, and price data loaded.",
      },
      {
        id: "trade_proposal",
        label: "AI Strategy",
        icon: "psychology",
        status: "success",
        description: "Identified a bullish price pattern.",
      },
      {
        id: "chaos_result",
        label: "Chaos Sandbox",
        icon: "science",
        status: "success",
        description: "Passed 10,000 simulated market scenarios.",
      },
      {
        id: "risk_result",
        label: "Risk Gate",
        icon: "gavel",
        status: "failed",
        description: "Blocked a hard safety-rule violation.",
      },
      {
        id: "execution",
        label: "Execute",
        icon: "send",
        status: "pending",
        description: "Skipped - the trade was blocked.",
      },
    ],
    strategy: {
      symbol: "TSLA",
      action: "BUY",
      direction: "bullish",
      description: "Call Spread",
      convictionPct: 65,
      reasoning: "A volatility breakout setup, though the position size pushed against portfolio limits.",
    },
    chaosSandbox: {
      status: "complete",
      logs: [],
      survivalScorePct: 94,
      summary: "Passed stress tests against historical flash crashes and extreme volatility spikes.",
    },
    riskGate: {
      status: "vetoed",
      reason: "Allocation of $45k exceeds single-position portfolio limit of 15% ($21k).",
    },
  },

  "run-7a03": {
    runId: "run-7a03",
    symbol: "NVDA",
    status: "success",
    initiatedAt: "2026-05-11T16:20:05Z",
    durationSeconds: 3.8,
    steps: [
      { id: "market_context", label: "Market Data", icon: "monitoring", status: "success" },
      { id: "trade_proposal", label: "AI Strategy", icon: "psychology", status: "success" },
      { id: "chaos_result", label: "Chaos Sandbox", icon: "science", status: "success" },
      { id: "risk_result", label: "Risk Gate", icon: "gavel", status: "success" },
      { id: "execution", label: "Execute", icon: "send", status: "success" },
    ],
    strategy: {
      symbol: "NVDA",
      action: "BUY",
      direction: "bullish",
      description: "Long Call (130)",
      convictionPct: 92,
      reasoning: "Strong earnings momentum and heightened trading activity point to continued strength.",
    },
    chaosSandbox: {
      status: "complete",
      logs: [],
      survivalScorePct: 97,
      summary: "Passed stress tests against historical flash crashes and extreme volatility spikes.",
    },
    riskGate: { status: "approved" },
  },

  "run-5c44": {
    runId: "run-5c44",
    symbol: "MSFT",
    status: "success",
    initiatedAt: "2026-05-10T11:05:47Z",
    durationSeconds: 3.1,
    steps: [
      { id: "market_context", label: "Market Data", icon: "monitoring", status: "success" },
      { id: "trade_proposal", label: "AI Strategy", icon: "psychology", status: "success" },
      { id: "chaos_result", label: "Chaos Sandbox", icon: "science", status: "success" },
      { id: "risk_result", label: "Risk Gate", icon: "gavel", status: "success" },
      { id: "execution", label: "Execute", icon: "send", status: "success" },
    ],
    strategy: {
      symbol: "MSFT",
      action: "HOLD",
      direction: "bullish",
      description: "No new position",
      convictionPct: 70,
      reasoning: "Range-bound price action - insufficient edge to justify opening a new position today.",
    },
    chaosSandbox: {
      status: "complete",
      logs: [],
      survivalScorePct: 96,
      summary: "No position proposed, so no stress scenario was required to run.",
    },
    riskGate: { status: "approved" },
  },
}

export const MOCK_RECENT_RUNS: RunSummary[] = [
  { id: "run-7a03", symbol: "NVDA", status: "success", action: "BUY", convictionPct: 92 },
  { id: "run-6e91", symbol: "TSLA", status: "vetoed", action: "BUY", convictionPct: 65 },
  { id: "run-5c44", symbol: "MSFT", status: "success", action: "HOLD", convictionPct: 70 },
]

// Which run "New Run" most recently started - getActiveRun() always reads
// through this instead of a hardcoded id, so starting a run actually changes
// what the Dashboard shows next time it polls.
let activeRunId = "run-8f21"

export function getActiveRunId(): string {
  return activeRunId
}

const STEP_TEMPLATE: readonly Omit<PipelineStep, "status">[] = [
  { id: "market_context", label: "Market Data", icon: "monitoring" },
  { id: "trade_proposal", label: "AI Strategy", icon: "psychology" },
  { id: "chaos_result", label: "Chaos Sandbox", icon: "science" },
  { id: "risk_result", label: "Risk Gate", icon: "gavel" },
  { id: "execution", label: "Execute", icon: "send" },
]

function buildStrategyFor(symbol: string): StrategyDecision {
  return {
    symbol,
    action: "BUY",
    direction: "bullish",
    description: `Long Call (${symbol})`,
    convictionPct: 75,
    reasoning: `Momentum and options flow on ${symbol} favor a bullish setup at current levels.`,
  }
}

function syncRecentRunsEntry(run: RunDetail): void {
  const entry = MOCK_RECENT_RUNS.find((summary) => summary.id === run.runId)
  if (entry) {
    entry.status = run.status
    entry.action = run.strategy.action
    entry.convictionPct = run.strategy.convictionPct
  }
}

// Mutates the run in place on a timer so polling (see the refetchInterval in
// hooks/useDashboard.ts) shows it actually progressing - stands in for what
// a real backend + poll/websocket would do once workflow/pipeline.py is
// exposed over HTTP. Always resolves to an approved, filled run - a live
// demo shouldn't show a fabricated veto with no real risk logic behind it.
function scheduleProgress(run: RunDetail): void {
  const advanceTo = (stepIndex: number, patch?: { chaos?: Partial<ChaosSandboxState>; risk?: RiskGateState }) => {
    run.steps[stepIndex] = { ...run.steps[stepIndex], status: "success" }
    if (run.steps[stepIndex + 1]) {
      run.steps[stepIndex + 1] = { ...run.steps[stepIndex + 1], status: "running" }
    }
    if (patch?.chaos) run.chaosSandbox = { ...run.chaosSandbox, ...patch.chaos }
    if (patch?.risk) run.riskGate = patch.risk
    if (stepIndex === run.steps.length - 1) {
      run.status = "success"
      syncRecentRunsEntry(run)
    }
  }

  setTimeout(() => advanceTo(0), 1500)
  setTimeout(() => advanceTo(1), 3000)
  setTimeout(
    () =>
      advanceTo(2, {
        chaos: {
          status: "complete",
          logs: [`Injected 500% spread on ${run.symbol}...`, "IV crush -80%...", "Liquidity shock scenario A-3..."],
          survivalScorePct: 91,
        },
      }),
    5000,
  )
  setTimeout(() => advanceTo(3, { risk: { status: "approved" } }), 6500)
  setTimeout(() => advanceTo(4), 8000)
}

export function createRun(ticker: string): RunDetail {
  const symbol = ticker.toUpperCase()
  const runId = `run-${Math.random().toString(36).slice(2, 6)}`

  const run: RunDetail = {
    runId,
    symbol,
    status: "running",
    initiatedAt: new Date().toISOString(),
    durationSeconds: 0,
    steps: STEP_TEMPLATE.map((step, index) => ({ ...step, status: index === 0 ? "running" : "pending" })),
    strategy: buildStrategyFor(symbol),
    chaosSandbox: { status: "pending", logs: [] },
    riskGate: { status: "pending" },
  }

  MOCK_RUN_DETAILS[runId] = run
  MOCK_RECENT_RUNS.unshift({ id: runId, symbol, status: "running", action: "BUY", convictionPct: run.strategy.convictionPct })
  activeRunId = runId
  scheduleProgress(run)

  return run
}
