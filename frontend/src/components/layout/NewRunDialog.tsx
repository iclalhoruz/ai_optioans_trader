import { useState, type FormEvent } from "react"
import { createPortal } from "react-dom"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/Button"
import { Icon } from "@/components/ui/Icon"
import { useStartRun } from "@/hooks/useDashboard"

interface NewRunDialogProps {
  onClose: () => void
}

// Rendered via portal straight into <body> - TopBar (where this gets
// triggered from) has backdrop-blur on its <header>, and a backdrop-filter
// ancestor turns into the containing block for `position: fixed`
// descendants in most browsers. Left in the normal tree, `inset-0` here
// would resolve against the 64px header instead of the viewport - exactly
// the "cut off at the top" bug this fixes.
function NewRunDialogPortal({ onClose }: NewRunDialogProps) {
  const [ticker, setTicker] = useState("")
  const navigate = useNavigate()
  const startRun = useStartRun()

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    const symbol = ticker.trim()
    if (!symbol) return

    startRun.mutate(symbol, {
      onSuccess: () => {
        onClose()
        navigate("/dashboard")
      },
    })
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <form
        onClick={(event) => event.stopPropagation()}
        onSubmit={handleSubmit}
        className="glass-panel w-full max-w-sm rounded-xl p-container-padding"
      >
        <h3 className="mb-4 font-headline-md text-headline-md text-on-surface">Start a new run</h3>
        <label className="mb-1 block font-label-caps text-label-caps text-outline">Ticker symbol</label>
        <input
          autoFocus
          value={ticker}
          onChange={(event) => setTicker(event.target.value.toUpperCase())}
          placeholder="AAPL"
          className="mb-4 w-full rounded-lg border border-outline-variant bg-surface-container-low px-3 py-2 font-data-mono-sm uppercase text-on-surface placeholder-outline-variant focus:border-primary focus:outline-none"
        />
        {startRun.isError && (
          <p className="mb-4 font-data-mono-sm text-xs text-error">Couldn't start the run. Try again.</p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={startRun.isPending || !ticker.trim()}>
            {startRun.isPending ? "Starting…" : "Start Run"}
            {!startRun.isPending && <Icon name="arrow_forward" className="text-sm" />}
          </Button>
        </div>
      </form>
    </div>
  )
}

export function NewRunDialog(props: NewRunDialogProps) {
  return createPortal(<NewRunDialogPortal {...props} />, document.body)
}
