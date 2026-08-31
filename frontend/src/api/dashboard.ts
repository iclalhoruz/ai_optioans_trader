import { apiClient } from "@/api/client"
import { createRun, getActiveRunId, MOCK_RECENT_RUNS, MOCK_RUN_DETAILS } from "@/api/mocks/dashboard"
import { delay } from "@/api/mocks/delay"
import type { RunDetail, RunSummary } from "@/types/domain"

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== "false"

// "Active" just means "whichever run is currently in focus on the
// Dashboard" - it doesn't have to still be running.
export function getActiveRun(): Promise<RunDetail> {
  return USE_MOCKS ? delay(MOCK_RUN_DETAILS[getActiveRunId()]) : apiClient.get<RunDetail>("/runs/active")
}

export function getRunDetail(runId: string): Promise<RunDetail> {
  return USE_MOCKS ? delay(MOCK_RUN_DETAILS[runId]) : apiClient.get<RunDetail>(`/runs/${runId}`)
}

export function getRecentRuns(): Promise<RunSummary[]> {
  return USE_MOCKS ? delay(MOCK_RECENT_RUNS) : apiClient.get<RunSummary[]>("/runs/recent")
}

// Kicks off a new pipeline run for a ticker - once workflow/pipeline.py is
// exposed over HTTP this becomes a real POST that calls
// PipelineOrchestrator.run(ticker) and returns its run_id.
export function startRun(ticker: string): Promise<{ runId: string }> {
  if (USE_MOCKS) {
    const run = createRun(ticker)
    return delay({ runId: run.runId }, 300)
  }
  return apiClient.post<{ runId: string }>("/runs", { ticker })
}
