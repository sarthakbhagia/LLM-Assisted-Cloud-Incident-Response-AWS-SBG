import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import IncidentDetail from './pages/IncidentDetail'
import Analytics from './pages/Analytics'
import ReplayMode from './pages/ReplayMode'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/incidents/:incidentId" element={<IncidentDetail />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/replay" element={<ReplayMode />} />
        <Route path="/replay/:incidentId" element={<ReplayMode />} />
      </Routes>
    </Layout>
  )
}

export default App