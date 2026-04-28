import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import LandingPage      from '@/pages/LandingPage'
import DashboardPage    from '@/pages/DashboardPage'
import GlobalMapPage    from '@/pages/GlobalMapPage'
import RLOptimizerPage  from '@/pages/RLOptimizerPage'
import ShipmentsPage    from '@/pages/ShipmentsPage'
import InsightsPage     from '@/pages/InsightsPage'
import RiskPage         from '@/pages/RiskPage'
import FleetPage        from '@/pages/FleetPage'
import ResiliencePage   from '@/pages/ResiliencePage'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-dvh bg-bg text-text font-mono">
        <Routes>
          <Route path="/"             element={<LandingPage />} />
          <Route path="/dashboard"    element={<DashboardPage />} />
          <Route path="/global-map"   element={<GlobalMapPage />} />
          <Route path="/shipments"    element={<ShipmentsPage />} />
          <Route path="/risk"         element={<RiskPage />} />
          <Route path="/insights"     element={<InsightsPage />} />
          <Route path="/fleet"        element={<FleetPage />} />
          <Route path="/resilience"   element={<ResiliencePage />} />
          <Route path="/rl-optimizer" element={<RLOptimizerPage />} />
          <Route path="*"             element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
