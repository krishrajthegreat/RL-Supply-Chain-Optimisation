import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import DashboardPage   from '@/pages/DashboardPage'
import GlobalMapPage   from '@/pages/GlobalMapPage'
import RLOptimizerPage from '@/pages/RLOptimizerPage'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-dvh bg-bg text-text font-mono">
        <Routes>
          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          {/* Main routes */}
          <Route path="/dashboard"    element={<DashboardPage />} />
          <Route path="/global-map"   element={<GlobalMapPage />} />
          <Route path="/rl-optimizer" element={<RLOptimizerPage />} />

          {/* Catch-all fallback */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
