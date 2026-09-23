import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Incidents from './pages/Incidents'
import IncidentDetail from './pages/IncidentDetail'
import Analytics from './pages/Analytics'
import ServiceMap from './pages/ServiceMap'
import Runbooks from './pages/Runbooks'
import ReplayMode from './pages/ReplayMode'
import SystemHealth from './pages/SystemHealth'

function App() {
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