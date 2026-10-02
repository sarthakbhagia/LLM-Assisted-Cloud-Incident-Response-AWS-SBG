import { Routes, Route } from 'react-router-dom'
import { AlertCircle, RefreshCw } from 'lucide-react'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Incidents from './pages/Incidents'
import IncidentDetail from './pages/IncidentDetail'
import Analytics from './pages/Analytics'
import ServiceMap from './pages/ServiceMap'
import Runbooks from './pages/Runbooks'
import ReplayMode from './pages/ReplayMode'
import SystemHealth from './pages/SystemHealth'
import { configError } from './config/api'

function ConfigErrorScreen() {
  if (!configError) return null
  
  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center p-8">
      <div className="card p-8 max-w-md w-full text-center">
        <AlertCircle className="mx-auto w-12 h-12 text-crimson mb-4" />
        <h1 className="text-lg font-semibold text-text-primary mb-2">Configuration Error</h1>
        <p className="text-xs text-text-secondary mb-4">{configError.message}</p>
        <ul className="text-xs text-text-muted mb-6 space-y-1 text-left">
          {configError.details.map((detail, i) => (
            <li key={i} className="font-mono">{detail}</li>
          ))}
        </ul>
        <p className="text-xs text-text-muted mb-6">{configError.help}</p>
        <button onClick={() => window.location.reload()} className="btn-primary">
          <RefreshCw className="w-4 h-4 mr-2" /> Retry
        </button>
      </div>
    </div>
  )
}

function App() {
  if (configError) {
    return <ConfigErrorScreen />
  }
  
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/incidents/:incidentId" element={<IncidentDetail />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/service-map" element={<ServiceMap />} />
        <Route path="/runbooks" element={<Runbooks />} />
        <Route path="/runbooks/:fault_class" element={<Runbooks />} />
        <Route path="/replay" element={<ReplayMode />} />
        <Route path="/replay/:incidentId" element={<ReplayMode />} />
        <Route path="/system-health" element={<SystemHealth />} />
      </Routes>
    </Layout>
  )
}

export default App