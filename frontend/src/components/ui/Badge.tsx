import type { HTMLAttributes } from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/cn"

// Every colored status pill in the app (run action, run status, risk
// verdict) reads from this one variant map instead of each screen inventing
// its own green/red classes.
const badgeStyles = cva("inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border", {
  variants: {
    tone: {
      success: "bg-tertiary-fixed/10 text-tertiary-fixed border-tertiary-fixed/30",
      error: "bg-error/10 text-error border-error/30",
      pending: "bg-secondary/10 text-secondary border-secondary/30",
      neutral: "bg-outline/10 text-outline border-outline/30",
      // trade-action aliases - same palette as success/error/neutral, named
      // for what they mean at the call site (a Run's action).
      buy: "bg-tertiary/10 text-tertiary border-tertiary/30",
      sell: "bg-error/10 text-error border-error/30",
      hold: "bg-outline/10 text-outline border-outline/30",
      info: "bg-primary-container/10 text-primary-container border-primary-container/40",
    },
  },
  defaultVariants: {
    tone: "neutral",
  },
})

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeStyles> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeStyles({ tone }), className)} {...props} />
}
