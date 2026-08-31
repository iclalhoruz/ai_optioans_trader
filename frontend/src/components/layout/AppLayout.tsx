import { Outlet } from "react-router-dom"
import { Sidebar } from "@/components/layout/Sidebar"
import { TopBar } from "@/components/layout/TopBar"
import { useSidebarCollapsed } from "@/hooks/useSidebarCollapsed"
import { cn } from "@/lib/cn"
import { SIDEBAR_MARGIN } from "@/lib/layout"

// The router's layout route: rendered once, wraps every page via <Outlet/>.
// A page never re-declares the sidebar/topbar - it just renders its content
// and this shell is already around it. Owns the collapsed/expanded sidebar
// state since it has to keep Sidebar's width and this wrapper's margin in
// sync - if each owned its own state independently they could disagree.
export function AppLayout() {
  const [collapsed, setCollapsed] = useSidebarCollapsed()

  return (
    <div className="flex min-h-screen bg-background font-body-base text-on-surface">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <div
        className={cn(
          "ml-0 flex min-h-screen flex-1 flex-col transition-[margin] duration-200",
          SIDEBAR_MARGIN[collapsed ? "collapsed" : "expanded"],
        )}
      >
        <TopBar collapsed={collapsed} />
        {/* Width/max-width is each page's own call (a table-heavy dashboard
            wants full width, a stat-card page wants a centered column) -
            the shared layout only owns padding and scroll behavior. */}
        <main className="mt-16 flex-1 overflow-y-auto p-container-padding">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
