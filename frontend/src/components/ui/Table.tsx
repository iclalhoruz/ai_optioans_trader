import type { HTMLAttributes, ReactNode, TdHTMLAttributes, ThHTMLAttributes } from "react"
import { cn } from "@/lib/cn"

// Composable table primitives so every data table in the app (positions,
// run history, ...) shares one set of cell/row styles instead of each
// screen re-typing the same padding/border classes on every <td>.

export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left border-collapse">{children}</table>
    </div>
  )
}

export function TableHead({ children }: { children: ReactNode }) {
  return (
    <thead>
      <tr className="border-b border-outline-variant/50 bg-surface-container-lowest/50">{children}</tr>
    </thead>
  )
}

interface AlignProp {
  align?: "left" | "right"
}

export function TableHeadCell({
  align = "left",
  className,
  ...props
}: ThHTMLAttributes<HTMLTableCellElement> & AlignProp) {
  return (
    <th
      className={cn(
        "py-4 px-6 font-label-caps text-label-caps text-outline uppercase",
        align === "right" && "text-right",
        className,
      )}
      {...props}
    />
  )
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody className="font-data-mono-sm text-data-mono-sm">{children}</tbody>
}

export function TableRow({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn("border-b border-outline-variant/30 hover:bg-white/[0.03] transition-colors group", className)}
      {...props}
    />
  )
}

export function TableCell({
  align = "left",
  className,
  ...props
}: TdHTMLAttributes<HTMLTableCellElement> & AlignProp) {
  return <td className={cn("py-4 px-6", align === "right" && "text-right", className)} {...props} />
}
