import { NavLink } from "react-router-dom"
import { Icon } from "@/components/ui/Icon"
import { cn } from "@/lib/cn"
import { SIDEBAR_WIDTH } from "@/lib/layout"
import type { NavItem } from "@/types/domain"

// Data-driven nav list - adding/removing/reordering a screen means editing
// this array, not copy-pasting another <NavLink> block. Active state comes
// from the URL (react-router), not a prop passed down from whichever page
// happens to be rendering - so it can never drift out of sync with what's
// actually on screen.
const NAV_ITEMS: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: "dashboard", path: "/dashboard" },
  { id: "history", label: "History", icon: "history", path: "/history" },
  { id: "settings", label: "Settings", icon: "settings", path: "/settings" },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <nav
      className={cn(
        "fixed left-0 top-0 z-50 hidden h-full flex-col border-r border-outline-variant bg-surface-container-lowest py-6 transition-[width] duration-200 md:flex",
        SIDEBAR_WIDTH[collapsed ? "collapsed" : "expanded"],
      )}
    >
      <div className="flex flex-col items-center gap-stack-lg">
        {/* Replaces what used to be a static "A" logo - the app name is
            already prominent in TopBar, so this slot is better spent on the
            one control every screen needs: collapse/expand. */}
        <button
          onClick={onToggle}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-primary/50 bg-primary/20 text-primary shadow-[0_0_12px_rgba(0,209,255,0.4)] transition-colors hover:border-primary-container hover:text-primary-container hover:shadow-[0_0_12px_rgba(0,209,255,0.6)]"
        >
          <Icon name={collapsed ? "chevron_right" : "chevron_left"} className="text-lg" />
        </button>
        <div className="flex w-full flex-col gap-stack-sm px-2">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.id}
              to={item.path}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                cn(
                  "flex w-full scale-95 items-center gap-3 rounded-lg p-3 transition-all duration-200 active:scale-90",
                  collapsed ? "flex-col justify-center" : "flex-row",
                  isActive
                    ? "border border-primary-container/30 bg-primary-container/10 text-primary-container shadow-[0_0_12px_rgba(0,209,255,0.3)]"
                    : "text-outline hover:bg-surface-container-highest hover:text-on-surface-variant",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon name={item.icon} filled={isActive} className={cn("shrink-0", isActive && "neon-text-cyan")} />
                  {!collapsed && <span className="font-data-mono-sm text-data-mono-sm">{item.label}</span>}
                </>
              )}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  )
}
