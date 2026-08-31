import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { AppLayout } from "@/components/layout/AppLayout"
import { ComingSoonPage } from "@/pages/ComingSoonPage"
import { DashboardPage } from "@/pages/DashboardPage"
import { HistoryPage } from "@/pages/HistoryPage"
import { RunDetailPage } from "@/pages/RunDetailPage"

// Each screen owns its own route. Adding a screen means adding a <Route>
// here plus a nav entry in Sidebar.tsx - the layout and every other screen
// stay untouched. history/:runId is nested under history/ (not a sibling
// top-level route) so the Sidebar's "History" NavLink stays highlighted
// while looking at one run's detail - it's part of that flow.
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="history/:runId" element={<RunDetailPage />} />
          <Route
            path="settings"
            element={
              <ComingSoonPage
                title="Settings"
                description="Will hold risk-gate thresholds, the autonomous watchlist, and Alpaca connection status once the team decides on that architecture."
              />
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
