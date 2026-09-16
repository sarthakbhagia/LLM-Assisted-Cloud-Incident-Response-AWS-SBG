import { useState, useEffect, useRef } from 'react'
import { AlertTriangle, Clock, TrendingUp, CheckCircle, Zap, Loader2, Check, AlertCircle } from 'lucide-react'
import IncidentFeed from '../components/IncidentFeed'
import { apiClient } from '../config/api'
import { POLLING_INTERVALS } from '../utils/constants'
import { formatMTTR } from '../utils/helpers'

export default function Overview() {
  const [kpis, setKpis] = useState({
    activeIncidents: 0,
    pendingApprovals: 0,
    recoverySuccessRate: 0,
    averageMTTR: 0
  })
  const [loading, setLoading] = useState(true)
  const [injectingFault, setInjectingFault] = useState(null)
  const [isDisabled, setIsDisabled] = useState(false)
  const [toast, setToast] = useState(null)
  
  const feedRef = useRef(null)

  const fetchKPIs = async () => {
    try {
      const incidentsData = await apiClient.getIncidents({ limit: 100 })
      const incidents = incidentsData.incidents || []
      
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
        : 0
      
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
      
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch KPIs:', error)
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchKPIs()
    const interval = setInterval(fetchKPIs, POLLING_INTERVALS.INCIDENTS_FEED)
    return () => clearInterval(interval)
  }, [])

  const handleTriggerFault = async (faultClass) => {
    if (isDisabled || injectingFault) return

    setInjectingFault(faultClass)
    setToast(null)

    try {
      await apiClient.injectFault(faultClass)
      setToast({
        type: 'success',
        message: 'Fault injected. Watch the incident feed for detection.'
      })
      
      // Auto scroll to incident feed
      if (feedRef.current) {
        feedRef.current.scrollIntoView({ behavior: 'smooth' })
      }
      
      // Refresh KPIs quickly after injection
      setTimeout(fetchKPIs, 2000)
    } catch (err) {
      console.error('Failed to inject fault:', err)
      setToast({
        type: 'error',
        message: err.message || 'Failed to trigger fault injection.'
      })
    } finally {
      setInjectingFault(null)
      setIsDisabled(true)
      setTimeout(() => {
        setIsDisabled(false)
      }, 10000)
    }
  }

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

      {/* Section A — Fault Injection Panel */}
      <div className="card p-6 border-border-strong">
        <div className="flex items-center space-x-2 mb-2">
          <Zap className="w-5 h-5 text-amber" />
          <h2 className="text-base font-semibold text-text-primary">Trigger Fault Injection</h2>
        </div>
        <p className="text-xs text-text-secondary mb-4">
          Simulate cloud environment failures to trigger the autonomous incident response pipeline end to end.
        </p>
        
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <button
            onClick={() => handleTriggerFault('resource_exhaustion')}
            disabled={isDisabled || injectingFault !== null}
            className="btn-primary flex items-center justify-center space-x-2 py-2 h-auto text-xs sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {injectingFault === 'resource_exhaustion' ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-amber" />
                <span>Injecting...</span>
              </>
            ) : (
              <span>Trigger Resource Exhaustion</span>
            )}
          </button>

          <button
            onClick={() => handleTriggerFault('misconfiguration')}
            disabled={isDisabled || injectingFault !== null}
            className="btn-primary flex items-center justify-center space-x-2 py-2 h-auto text-xs sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {injectingFault === 'misconfiguration' ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-amber" />
                <span>Injecting...</span>
              </>
            ) : (
              <span>Trigger Misconfiguration</span>
            )}
          </button>

          <button
            onClick={() => handleTriggerFault('service_cascade')}
            disabled={isDisabled || injectingFault !== null}
            className="btn-primary flex items-center justify-center space-x-2 py-2 h-auto text-xs sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {injectingFault === 'service_cascade' ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-amber" />
                <span>Injecting...</span>
              </>
            ) : (
              <span>Trigger Service Cascade</span>
            )}
          </button>
        </div>
        {isDisabled && (
          <p className="text-[11px] text-text-muted mt-2">
            Cooldown active — buttons will re-enable shortly to prevent duplicate injections.
          </p>
        )}
      </div>

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
          value={loading ? '—' : `${kpis.recoverySuccessRate}%`}
          icon={CheckCircle}
          iconColor={kpis.recoverySuccessRate >= 80 ? 'text-emerald' : 
                    kpis.recoverySuccessRate >= 60 ? 'text-amber' : 'text-crimson'}
          trend={kpis.recoverySuccessRate >= 80 ? 'Excellent' : 
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
                Live polling every 5s across all services
              </div>
            </div>
            <IncidentFeed />
          </div>
        </div>

        {/* Right Panel - System Health */}
        <div className="space-y-4">
          <SystemHealthCard />
          <RecentRemediationsCard />
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

function SystemHealthCard() {
  const services = [
    { name: 'Service A', status: 'healthy' },
    { name: 'Service B', status: 'healthy' },
    { name: 'Service C', status: 'healthy' },
    { name: 'Collector', status: 'healthy' },
    { name: 'Diagnosis', status: 'healthy' }
  ]

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-4">System Health</h3>
      <div className="space-y-3">
        {services.map((service) => (
          <div key={service.name} className="flex items-center justify-between">
            <span className="text-xs text-text-secondary">{service.name}</span>
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-emerald rounded-full"></div>
              <span className="text-xs text-emerald">Healthy</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function RecentRemediationsCard() {
  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-4">Recent Actions</h3>
      <div className="space-y-3">
        <div className="text-center text-text-muted py-6">
          <CheckCircle className="mx-auto w-6 h-6 mb-2 opacity-50" />
          <p className="text-xs">No recent remediations</p>
        </div>
      </div>
    </div>
  )
}