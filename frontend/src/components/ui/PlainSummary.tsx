import { Icon } from "@/components/ui/Icon"

interface PlainSummaryProps {
  text: string
}

// A one-sentence "here's what's happening" line meant to sit above the
// technical breakdown on a screen - not a replacement for the detail below
// it, just the thing a first-time or non-technical viewer reads first.
export function PlainSummary({ text }: PlainSummaryProps) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3">
      <Icon name="lightbulb" className="mt-0.5 shrink-0 text-primary" />
      <p className="font-body-base text-sm text-on-surface-variant">{text}</p>
    </div>
  )
}
