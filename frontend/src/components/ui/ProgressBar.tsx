import { cn } from "@/lib/cn"

type ProgressBarTone = "cyan" | "primary" | "success"

interface ProgressBarProps {
  percent: number
  tone?: ProgressBarTone
}

// One entry per tone instead of a prop for every possible fill color -
// covers the 3 shades this app's mockups actually use (Dashboard's vivid
// cyan conviction bar, the run-detail page's soft-cyan conviction bar and
// green survival-score bar).
const TONE_CLASSES: Record<ProgressBarTone, string> = {
  cyan: "bg-primary-container shadow-[0_0_8px_rgba(0,209,255,0.8)]",
  primary: "bg-primary shadow-[0_0_8px_rgba(164,230,255,0.6)]",
  success: "bg-tertiary shadow-[0_0_8px_rgba(57,251,136,0.6)]",
}

// Used for conviction/completion bars - a single glowing fill on a track,
// reused anywhere a 0-100 value needs a horizontal bar instead of a number.
export function ProgressBar({ percent, tone = "cyan" }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, percent))

  return (
    <div className="h-2 w-full overflow-hidden rounded-full border border-outline-variant/30 bg-surface-container">
      <div className={cn("relative h-full", TONE_CLASSES[tone])} style={{ width: `${clamped}%` }}>
        <div className="absolute inset-0 w-full animate-[pulse_2s_ease-in-out_infinite] bg-white/20" />
      </div>
    </div>
  )
}
