import { useState, useEffect, useRef } from 'react'
import { AlertTriangle, Clock, TrendingUp, CheckCircle, Check, AlertCircle } from 'lucide-react'
import IncidentFeed from '../components/IncidentFeed'
import DemoControls from '../components/DemoControls'
import { apiClient } from '../config/api'
import { POLLING_INTERVALS, FAULT_CLASS_LABELS } from '../utils/constants'
import { formatMTTR, formatDate } from '../utils/helpers'

export default function Overview() {
  const [kpis, setKpis] = useState({
    activeIncidents: 0,
    pendingApprovals: 0,
    recoverySuccessRate: 0,
    averageMTTR: 0
  })
  const [recentResolved, setRecentResolved] = useState([])
  const [systemHealth, setSystemHealth] = useState(null)
  const [systemHealthError, setSystemHealthError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  
  const feedRef = useRef(null)

  const fetchKPIs = async () => {
    try {
      // Try to get aggregate KPIs from backend analytics endpoint first
      const analyticsData = await apiClient.getAnalytics()
      if (analyticsData && typeof analyticsData === 'object' && 'kpis' in analyticsData) {
        setKpis(analyticsData.kpis)
      } else {
        // Fallback: compute from incidents list (limited to last 100)
        const incidentsData = await apiClient.getIncidents({ limit: 100 })
        const incidents = incidentsData?.items || []
        computeKPIsFromIncidents(incidents)
      }
      
      const incidentsData = await apiClient.getIncidents({ limit: 100 })
      const incidents = incidentsData?.items || []
      
      const sorted = [...incidents]
        .filter(i => i.verification?.status === 'resolved' && i.verification?.checked_at)
        .sort((a, b) => new Date(b.verification.checked_at) - new Date(a.verification.checked_at))
      setRecentResolved(sorted.slice(0, 3))

      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch KPIs:', error)
      // Fallback to client-side computation
      try {
        const incidentsData = await apiClient.getIncidents({ limit: 100 })
        computeKPIsFromIncidents(incidentsData?.items || [])
      } catch (e) {
        console.error('Fallback KPI fetch also failed:', e)
      }
      setLoading(false)
    }
  }

  const computeKPIsFromIncidents = (incidents) => {
    const activeIncidents = incidents.filter(i => 
      !['resolved', 'rejected', 'failed'].includes(i.remediation?.status) &&
      i.verification?.status !== 'resolved'
    ).length
    
    const pendingApprovals = incidents.filter(i => 
      i.remediation?.status === 'pending_approval'
    ).length
    
    const resolvedIncidents = incidents.filter(i => 
      i.verification?.status === 'resolved'
    ).length
    
    const recoverySuccessRate = incidents.length > 0 
      ? Math.round((resolvedIncidents / incidents.length) * 100)
      : null
    
    const resolvedWithTimes = incidents.filter(i => 
      i.verification?.status === 'resolved' && 
      i.detected_at && 
      i.verification?.checked_at
    )
    
    let averageMTTR = 0
    if (resolvedWithTimes.length > 0) {
      const totalMinutes = resolvedWithTimes.reduce((sum, incident) => {
        const detected = new Date(incident.detected_at)
        const resolved = new Date(incident.verification.checked_at)
        const minutes = (resolved - detected) / (1000 * 60)
        return sum + minutes
      }, 0)
      averageMTTR = Math.round(totalMinutes / resolvedWithTimes.length)
    }
    
    setKpis({
      activeIncidents,
      pendingApprovals,
      recoverySuccessRate,
      averageMTTR
    })
  }

  const fetchSystemHealth = async () => {
    try {
      const health = await apiClient.getHealth()
      setSystemHealth(health)
      setSystemHealthError(null)
    } catch (error) {
      console.error('Failed to fetch system health:', error)
      setSystemHealthError('Failed to load system health')
    }
  }

  useEffect(() => {
    fetchKPIs()
    fetchSystemHealth()
    const interval = setInterval(() => {
      fetchKPIs()
      fetchSystemHealth()
    }, POLLING_INTERVALS.INCIDENTS_FEED)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toast && (
        <div className={`p-4 rounded-card border flex items-center justify-between ${
          toast.type === 'success' 
            ? 'bg-emerald-surface border-emerald/30 text-emerald' 
            : 'bg-crimson-surface border-crimson/30 text-crimson'
        }`}>
          <div className="flex items-center space-x-2">
            {toast.type === 'success' ? (
              <Check className="w-5 h-5 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
            )}
            <span className="text-sm font-medium">{toast.message}</span>
          </div>
          <button 
            onClick={() => setToast(null)}
            className="text-xs hover:underline opacity-80"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Section A — Demo Mode Controls */}
      <DemoControls />

      {/* Section B — KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Active Incidents"
          value={loading ? '—' : kpis.activeIncidents}
          icon={AlertTriangle}
          iconColor={kpis.activeIncidents > 0 ? 'text-crimson' : 'text-text-muted'}
          trend={kpis.activeIncidents === 0 ? 'All clear' : `${kpis.activeIncidents} active`}
        />
        
        <KPICard
          title="Pending Approvals"
          value={loading ? '—' : kpis.pendingApprovals}
          icon={Clock}
          iconColor={kpis.pendingApprovals > 0 ? 'text-amber' : 'text-text-muted'}
          trend={kpis.pendingApprovals === 0 ? 'None pending' : `${kpis.pendingApprovals} awaiting`}
        />
        
<KPICard
          title="Recovery Rate"
          value={loading ? '—' : (kpis.recoverySuccessRate !== null ? `${kpis.recoverySuccessRate}%` : '—')}
          icon={CheckCircle}
          iconColor={kpis.recoverySuccessRate === null ? 'text-text-muted' :
                    kpis.recoverySuccessRate >= 80 ? 'text-emerald' : 
                    kpis.recoverySuccessRate >= 60 ? 'text-amber' : 'text-crimson'}
          trend={kpis.recoverySuccessRate === null ? 'No data yet' : 
                  kpis.recoverySuccessRate >= 80 ? 'Excellent' : 
                  kpis.recoverySuccessRate >= 60 ? 'Good' : 'Needs attention'}
        />
        
        <KPICard
          title="Average MTTR"
          value={loading ? '—' : (kpis.averageMTTR > 0 ? formatMTTR(kpis.averageMTTR) : '—')}
          icon={TrendingUp}
          iconColor={kpis.averageMTTR > 0 && kpis.averageMTTR <= 30 ? 'text-emerald' : 
                    kpis.averageMTTR <= 60 ? 'text-amber' : 'text-crimson'}
          trend={kpis.averageMTTR === 0 ? 'No resolved data' : (kpis.averageMTTR <= 30 ? 'Fast response' : 'Acceptable')}
        />
      </div>

      {/* Section C — Incident Feed Table */}
      <div ref={feedRef} className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3">
          <div className="card-elevated p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-text-primary">Incident Feed</h2>
              <div className="text-xs text-text-secondary">
                Live polling every {POLLING_INTERVALS.INCIDENTS_FEED / 1000}s across all services
              </div>
            </div>
            <IncidentFeed />
          </div>
        </div>

        {/* Right Panel - System Health */}
        <div className="space-y-4">
          <SystemHealthCard health={systemHealth} error={systemHealthError} />
          <RecentRemediationsCard incidents={recentResolved} />
        </div>
      </div>
    </div>
  )
}

function KPICard({ title, value, icon: Icon, iconColor, trend }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-text-secondary uppercase tracking-wide mb-1">
            {title}
          </p>
          <p className="text-2xl font-semibold text-text-primary mb-1">
            {value}
          </p>
          <p className="text-xs text-text-muted">
            {trend}
          </p>
        </div>
        <Icon className={`w-5 h-5 ${iconColor}`} />
      </div>
    </div>
  )
}

function SystemHealthCard({ health, error }) {
  if (error) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium text-text-primary mb-4">System Health</h3>
        <div className="p-3 bg-crimson-surface/30 border border-crimson/30 rounded-card">
          <p className="text-xs text-crimson">{error}</p>
          <button onClick={() => window.location.reload()} className="btn-ghost text-xs mt-2">Retry</button>
        </div>
      </div>
    )
  }

  if (!health) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium text-text-primary mb-4">System Health</h3>
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-8 bg-bg-elevated rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  const services = health.services || []
  const handlers = health.pipeline_handlers || {}
  const overall = health.overall === 'ok'
  const criticalFailures = health.critical_failures ?? 0

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-text-primary">System Health</h3>
        <span className={`badge ${overall ? 'badge-success' : 'badge-critical'}`}>
          {overall ? 'Healthy' : 'Degraded'}
        </span>
      </div>
      <div className="space-y-2">
        {services.map((svc) => (
          <div key={svc.service} className="flex items-center justify-between">
            <span className="text-xs text-text-secondary">{svc.service}</span>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${svc.status === 'ok' ? 'bg-emerald' : 'bg-crimson'}`}></div>
              <span className={`text-xs ${svc.status === 'ok' ? 'text-emerald' : 'text-crimson'}`}>
                {svc.status === 'ok' ? 'Healthy' : 'Unhealthy'}
              </span>
            </div>
          </div>
        ))}
        {Object.entries(handlers).map(([name, status]) => (
          <div key={name} className="flex items-center justify-between">
            <span className="text-xs text-text-secondary">{name}</span>
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${status === 'loaded' ? 'bg-emerald' : 'bg-crimson'}`}></div>
              <span className={`text-xs ${status === 'loaded' ? 'text-emerald' : 'text-crimson'}`}>
                {status === 'loaded' ? 'Loaded' : 'Error'}
              </span>
            </div>
          </div>
        ))}
      </div>
      {!overall && criticalFailures > 0 && (
        <p className="text-xs text-crimson mt-2">{criticalFailures} critical service(s) unavailable</p>
      )}
    </div>
  )
}

function RecentRemediationsCard({ incidents = [] }) {
  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-4">Recent Actions</h3>
      <div className="space-y-3">
        {incidents.length === 0 ? (
          <div className="text-center text-text-muted py-6">
            <CheckCircle className="mx-auto w-6 h-6 mb-2 opacity-50" />
            <p className="text-xs">No recent remediations</p>
          </div>
        ) : (
          incidents.map((inc) => (
            <div key={inc.incident_id} className="flex items-start space-x-2">
              <div className="w-4 h-4 rounded-full bg-emerald-surface flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3 h-3 text-emerald" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-text-primary truncate">
                  {(inc.remediation?.action_taken || inc.fault_class || 'Resolved').replace(/_/g, ' ')}
                </p>
                <p className="text-xs text-text-muted mono">
                  {FAULT_CLASS_LABELS[inc.fault_class] || inc.fault_class} &bull; {formatDate(inc.verification.checked_at, 'relative')}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}