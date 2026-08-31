import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { NewRunButton } from "@/components/layout/NewRunButton"
import { Button } from "@/components/ui/Button"
import { Icon } from "@/components/ui/Icon"
import { StatusDot } from "@/components/ui/StatusDot"
import { cn } from "@/lib/cn"
import { SIDEBAR_OFFSET } from "@/lib/layout"

interface TopBarProps {
  collapsed: boolean
}

export function TopBar({ collapsed }: TopBarProps) {
  const [search, setSearch] = useState("")
  const navigate = useNavigate()

  // "run-xxxx" (our own id format, see api/mocks/dashboard.ts's createRun)
  // jumps straight to that run; anything else is treated as a ticker and
  // filters the History list, matching the "Symbol or Run ID" placeholder.
  const handleSearchSubmit = (event: FormEvent) => {
    event.preventDefault()
    const query = search.trim()
    if (!query) return

    if (query.toLowerCase().startsWith("run-")) {
      navigate(`/history/${query.toLowerCase()}`)
    } else {
      navigate(`/history?symbol=${encodeURIComponent(query.toUpperCase())}`)
    }
    setSearch("")
  }

  return (
    <header
      className={cn(
        "fixed left-0 right-0 top-0 z-40 flex h-16 items-center justify-between border-b border-outline-variant bg-surface-container/80 px-gutter font-data-mono-sm text-data-mono-sm text-primary backdrop-blur-md transition-[left] duration-200",
        SIDEBAR_OFFSET[collapsed ? "collapsed" : "expanded"],
      )}
    >
      <div className="flex items-center gap-gutter">
        <span className="font-headline-md text-headline-md font-bold tracking-tight text-on-surface">
          Aegis-OptionAI
        </span>
        <form
          onSubmit={handleSearchSubmit}
          className="group ml-stack-lg flex h-10 w-64 items-center rounded-lg border border-primary/30 bg-surface-container-low px-stack-sm py-unit transition-all focus-within:border-primary focus-within:shadow-[0_0_10px_rgba(0,209,255,0.2)] focus-within:ring-1 focus-within:ring-primary/40"
        >
          <button type="submit" aria-label="Search" className="flex items-center">
            <Icon name="search" className="text-lg text-outline-variant transition-colors group-focus-within:text-primary" />
          </button>
          <input
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Symbol or Run ID"
            className="w-full border-none bg-transparent px-stack-sm uppercase text-on-surface placeholder-outline-variant focus:ring-0"
          />
          <StatusDot tone="info" label="Active" pulse />
        </form>
      </div>
      <div className="flex items-center gap-container-padding">
        <Button variant="ghost" size="icon" title="Settings" onClick={() => navigate("/settings")}>
          <Icon name="settings" />
        </Button>
        <NewRunButton />
      </div>
    </header>
  )
}
