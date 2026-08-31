import { useState } from "react"
import {
  autoUpdate,
  flip,
  FloatingPortal,
  offset,
  shift,
  useDismiss,
  useFloating,
  useFocus,
  useHover,
  useInteractions,
  useRole,
} from "@floating-ui/react"
import { GLOSSARY, type GlossaryTerm } from "@/lib/glossary"

interface InfoTooltipProps {
  term?: GlossaryTerm
  text?: string
}

// Portal-based (via floating-ui) so the popup escapes any ancestor's
// `overflow-hidden` - several GlassPanel cards use it to clip a decorative
// background icon, which was also clipping a plain `position: absolute`
// tooltip nested inside them. Same root cause class as the New Run modal's
// earlier positioning bug (an ancestor's CSS constraining a child that's
// supposed to float above everything).
export function InfoTooltip({ term, text }: InfoTooltipProps) {
  const content = text ?? (term ? GLOSSARY[term] : undefined)
  const [isOpen, setIsOpen] = useState(false)

  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    placement: "top",
    middleware: [offset(8), flip(), shift({ padding: 8 })],
    whileElementsMounted: autoUpdate,
  })

  const hover = useHover(context, { move: false })
  const focus = useFocus(context)
  const dismiss = useDismiss(context)
  const role = useRole(context, { role: "tooltip" })
  const { getReferenceProps, getFloatingProps } = useInteractions([hover, focus, dismiss, role])

  if (!content) return null

  return (
    <>
      <button
        ref={refs.setReference}
        type="button"
        aria-label="More info"
        className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-outline-variant align-middle text-[10px] leading-none text-outline transition-colors hover:border-primary-container hover:text-primary-container focus:border-primary-container focus:text-primary-container focus:outline-none"
        {...getReferenceProps()}
      >
        ?
      </button>
      {isOpen && (
        <FloatingPortal>
          <div
            // refs.setFloating is a callback ref *setter* from floating-ui's
            // API, not a `.current` read - this is the documented usage.
            // oxlint-disable-next-line react/refs
            ref={refs.setFloating}
            style={floatingStyles}
            className="z-50 w-56 rounded-lg border border-outline-variant bg-surface-container-highest p-3 text-left font-body-base text-[11px] leading-relaxed text-on-surface shadow-lg"
            {...getFloatingProps()}
          >
            {content}
          </div>
        </FloatingPortal>
      )}
    </>
  )
}
