import { forwardRef, type ButtonHTMLAttributes } from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/cn"

// Every button in the app goes through this one file - change a variant
// here and it updates everywhere, instead of hunting down className strings
// scattered across screens.
const buttonStyles = cva(
  "inline-flex items-center justify-center gap-2 rounded font-data-mono-sm text-data-mono-sm font-bold transition-colors disabled:opacity-50 disabled:pointer-events-none",
  {
    variants: {
      variant: {
        primary:
          "bg-primary-container text-on-primary-container shadow-[0_0_10px_rgba(0,209,255,0.3)] hover:bg-primary-fixed hover:shadow-[0_0_15px_rgba(0,209,255,0.5)]",
        outline:
          "border border-outline-variant text-on-surface-variant hover:text-primary hover:border-primary",
        ghost: "text-on-surface-variant hover:text-primary hover:bg-surface-container-highest",
      },
      size: {
        sm: "px-3 py-1",
        md: "px-4 py-2",
        icon: "w-8 h-8 p-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonStyles> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonStyles({ variant, size }), className)} {...props} />
  ),
)
Button.displayName = "Button"
