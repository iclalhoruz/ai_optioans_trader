import { cn } from "@/lib/cn"

type StatusTone = "success" | "error" | "info" | "neutral"

interface StatusDotProps {
  tone: StatusTone
  label: string
  pulse?: boolean
}

// One entry per tone instead of an if/else ladder - add a new tone by
// adding a row here.
const DOT_CLASSES: Record<StatusTone, string> = {
  success: "bg-tertiary shadow-[0_0_6px_rgba(57,251,136,0.8)]",
  error: "bg-error shadow-[0_0_6px_rgba(255,180,171,0.8)]",
  info: "bg-primary-container shadow-[0_0_6px_rgba(0,209,255,0.8)]",
  neutral: "bg-outline",
}

const LABEL_CLASSES: Record<StatusTone, string> = {
  success: "text-tertiary neon-text-green",
  error: "text-error neon-text-amber",
  info: "text-primary-container neon-text-cyan",
  neutral: "text-outline",
}

export function StatusDot({ tone, label, pulse }: StatusDotProps) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={cn("h-1.5 w-1.5 rounded-full", DOT_CLASSES[tone], pulse && "neon-pulse")} />
      <span className={cn("font-data-mono-sm text-xs", LABEL_CLASSES[tone])}>{label}</span>
    </div>
  )
}
