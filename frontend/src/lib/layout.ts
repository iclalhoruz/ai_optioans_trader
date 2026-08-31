// Sidebar width is shared between Sidebar (its own width), AppLayout (the
// content wrapper's left margin) and TopBar (its fixed left offset) - one
// source so they can never drift out of sync when the sidebar toggles.
export const SIDEBAR_WIDTH = { collapsed: "w-16", expanded: "w-56" } as const
export const SIDEBAR_MARGIN = { collapsed: "md:ml-16", expanded: "md:ml-56" } as const
export const SIDEBAR_OFFSET = { collapsed: "md:left-16", expanded: "md:left-56" } as const
