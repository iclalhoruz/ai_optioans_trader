import { cn } from "@/lib/cn"

interface IconProps {
  name: string
  filled?: boolean
  className?: string
}

// Material Symbols renders via ligature: the text content IS the icon name.
export function Icon({ name, filled = false, className }: IconProps) {
  return (
    <span
      className={cn("material-symbols-outlined select-none", className)}
      style={{ fontVariationSettings: `'FILL' ${filled ? 1 : 0}` }}
      aria-hidden="true"
    >
      {name}
    </span>
  )
}
