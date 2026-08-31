import { useNavigate } from "react-router-dom"
import { Badge } from "@/components/ui/Badge"
import { StatusDot } from "@/components/ui/StatusDot"
import { Table, TableBody, TableCell, TableHead, TableHeadCell, TableRow } from "@/components/ui/Table"
import { cn } from "@/lib/cn"
import { ACTION_BADGE_TONE } from "@/lib/tradeAction"
import type { RunStatus, RunSummary } from "@/types/domain"

interface RunsTableProps {
  runs: RunSummary[]
}

// Maps a run's outcome to the dot/label shown in the Status column - one
// entry per status instead of a branch per row.
const STATUS_LABEL: Record<RunStatus, { tone: "success" | "error" | "info" | "neutral"; label: string }> = {
  success: { tone: "success", label: "Success" },
  vetoed: { tone: "error", label: "Vetoed" },
  running: { tone: "info", label: "Running" },
  failed: { tone: "error", label: "Failed" },
}

// A vetoed/failed run's conviction score didn't matter in the end, so it
// renders muted instead of with the "this number is good" glow.
const CONVICTION_CLASSES: Record<RunStatus, string> = {
  success: "text-primary-container neon-text-cyan",
  running: "text-primary-container neon-text-cyan",
  vetoed: "text-outline",
  failed: "text-outline",
}

// `action` is what the AI *proposed*, not what happened - for a vetoed or
// failed run nothing was ever executed, so the badge dims (same "didn't
// ultimately matter" treatment as CONVICTION_CLASSES) rather than looking
// as confident as an action that actually went through.
const ACTION_BADGE_CLASSES: Record<RunStatus, string> = {
  success: "",
  running: "",
  vetoed: "opacity-50",
  failed: "opacity-50",
}

// Bare table - no card chrome/title, so it can be dropped into a Dashboard
// widget (RecentRunsTable) or a full History page without either one
// re-typing the column/row rendering.
export function RunsTable({ runs }: RunsTableProps) {
  const navigate = useNavigate()

  return (
    <Table>
      <TableHead>
        <TableHeadCell>Symbol</TableHeadCell>
        <TableHeadCell>Status</TableHeadCell>
        <TableHeadCell>Action</TableHeadCell>
        <TableHeadCell align="right">Confidence</TableHeadCell>
      </TableHead>
      <TableBody>
        {runs.map((run) => {
          const status = STATUS_LABEL[run.status]
          return (
            <TableRow key={run.id} className="cursor-pointer" onClick={() => navigate(`/history/${run.id}`)}>
              <TableCell className="font-bold text-on-surface">{run.symbol}</TableCell>
              <TableCell>
                <StatusDot tone={status.tone} label={status.label} />
              </TableCell>
              <TableCell>
                <Badge tone={ACTION_BADGE_TONE[run.action]} className={cn(ACTION_BADGE_CLASSES[run.status])}>
                  {run.action}
                </Badge>
              </TableCell>
              <TableCell align="right" className={CONVICTION_CLASSES[run.status]}>
                {run.convictionPct}%
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
