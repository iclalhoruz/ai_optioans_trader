import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { getActiveRun, getRecentRuns, getRunDetail, startRun } from "@/api/dashboard"

// Poll every 2s while a run is still in progress - stands in for a
// websocket/live-push once a real backend exists. Stops automatically once
// the run reaches a terminal status, so a finished/historical run's detail
// page doesn't poll forever.
function pollWhileRunning(query: { state: { data?: { status?: string } } }): number | false {
  return query.state.data?.status === "running" ? 2000 : false
}

export function useActiveRun() {
  return useQuery({ queryKey: ["active-run"], queryFn: getActiveRun, refetchInterval: pollWhileRunning })
}

export function useRunDetail(runId: string) {
  return useQuery({
    queryKey: ["run-detail", runId],
    queryFn: () => getRunDetail(runId),
    refetchInterval: pollWhileRunning,
  })
}

export function useRecentRuns() {
  return useQuery({ queryKey: ["recent-runs"], queryFn: getRecentRuns })
}

export function useStartRun() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: startRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["active-run"] })
      queryClient.invalidateQueries({ queryKey: ["recent-runs"] })
    },
  })
}
