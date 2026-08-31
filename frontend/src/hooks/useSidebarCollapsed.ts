import { useEffect, useState } from "react"

const STORAGE_KEY = "aegis:sidebar-collapsed"

// Per-viewer UI preference, not app data - localStorage is the right tool
// here (see artifact/browser-storage conventions: fine for "remembered
// collapsed state", never for anything that needs to be shared or reliable).
export function useSidebarCollapsed(): [boolean, (value: boolean) => void] {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) !== "false"
    } catch {
      return true
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(collapsed))
    } catch {
      // localStorage unavailable (private browsing, etc.) - just don't persist.
    }
  }, [collapsed])

  return [collapsed, setCollapsed]
}
