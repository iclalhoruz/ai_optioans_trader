import type { HTMLAttributes } from "react"
import { cn } from "@/lib/cn"

// The frosted-glass card used for every panel/section on every screen.
export function GlassPanel({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("glass-panel rounded-xl", className)} {...props} />
}
