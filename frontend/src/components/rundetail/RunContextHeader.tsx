import { Link } from "react-router-dom"
import { Icon } from "@/components/ui/Icon"
import { cn } from "@/lib/cn"
import { formatDuration, formatTimestampUtc } from "@/lib/format"
import type { RunStatus } from "@/types/domain"

interface RunContextHeaderProps {
  runId: string
  symbol: string
  status: RunStatus
  initiatedAt: string
  durationSeconds: number
}

// One entry per status instead of an if/else ladder in the render.
const STATUS_PILL: Record<RunStatus, { icon: string; label: string; className: string }> = {
  vetoed: {
    icon: "block",
    label: "Vetoed",
    className: "bg-error-container/20 border-error/50 text-error drop-shadow-[0_0_4px_rgba(255,180,171,0.5)]",
  },
  success: {
    icon: "check_circle",
    label: "Success",
    className: "bg-tertiary-container/20 border-tertiary/50 text-tertiary",
  },
  running: {
    icon: "sync",
    label: "Running",
    className: "bg-primary-container/20 border-primary-container/50 text-primary-container",
  },
  failed: {
    icon: "error",
    label: "Failed",
    className: "bg-error-container/20 border-error/50 text-error",
  },
}

export function RunContextHeader({ runId, symbol, status, initiatedAt, durationSeconds }: RunContextHeaderProps) {
  const pill = STATUS_PILL[status]

  return (
    <div className="flex items-end justify-between border-b border-outline-variant pb-4">
      <div>
        <div className="mb-2 flex items-center gap-2">
          <Icon name="arrow_back" className="text-outline" />
          <Link
            to="/history"
            className="font-data-mono-sm text-data-mono-sm text-on-surface-variant transition-colors hover:text-primary"
          >
            Back to History
          </Link>
        </div>
        <div className="flex items-center gap-4">
          <h2 className="font-display-lg text-display-lg text-on-surface">
            {symbol} Run <span className="text-outline">#{runId}</span>
          </h2>
          <div
            className={cn(
              "flex items-center gap-1 rounded-full border px-3 py-1 font-label-caps text-label-caps",
              pill.className,
            )}
          >
            <Icon name={pill.icon} className="text-[14px]" />
            {pill.label.toUpperCase()}
          </div>
        </div>
      </div>
      <div className="text-right font-data-mono-sm text-data-mono-sm text-on-surface-variant">
        Initiated: {formatTimestampUtc(initiatedAt)}
        <br />
        Duration: {formatDuration(durationSeconds)}
      </div>
    </div>
  )
}
