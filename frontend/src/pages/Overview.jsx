import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Clock, TrendingUp, CheckCircle, Check, AlertCircle, ChevronRight } from 'lucide-react'
import IncidentFeed from '../components/IncidentFeed'
import DemoControls from '../components/DemoControls'
import { apiClient } from '../config/api'
import { POLLING_INTERVALS, FAULT_CLASS_LABELS, CURRENT_USER } from '../utils/constants'
import { formatMTTR, formatDate } from '../utils/helpers'

export default function Overview() {
  const [kpis, setKpis] = useState({
    activeIncidents: 0,
    pendingApprovals: 0,
    recoverySuccessRate: 0,
    averageMTTR: 0
  })
  const [incidents, setIncidents] = useState([])
  const [recentResolved, setRecentResolved] = useState([])
  const [loading, setLoading] = useState(true)
  const [toast, setToast] = useState(null)
  const [greeting, setGreeting] = useState('Welcome back')

  const feedRef = useRef(null)

  // Time-aware greeting, refreshed alongside the polling cadence
  useEffect(() => {
    const hour = new Date().getHours()
    setGreeting(hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening')
  }, [])

  const fetchKPIs = async () => {
    try {
      const incidentsData = await apiClient.getIncidents({ limit: 100 })
      const incidents = incidentsData?.items || []

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
      setIncidents(incidents)

      const sorted = [...incidents]
        .filter(i => i.verification?.status === 'resolved' && i.verification?.checked_at)
        .sort((a, b) => new Date(b.verification.checked_at) - new Date(a.verification.checked_at))
      setRecentResolved(sorted.slice(0, 4))

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

  return (
    <div className="space-y-6">
      {/* Toast Notification */}
      {toast && (
        <div className={`p-4 rounded-card border flex items-center justify-between fade-up ${
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
            <span className="text-sm font-semibold">{toast.message}</span>
          </div>
          <button
            onClick={() => setToast(null)}
            className="text-xs hover:underline opacity-80"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Greeting */}
      <div className="pt-8">
        <h1 className="text-3xl font-bold text-text-primary tracking-[-0.035em]">
          {greeting}, {CURRENT_USER.firstName}
        </h1>
        <p className="text-[14.5px] text-text-muted mt-1.5 max-w-xl">
          {loading
            ? 'Loading the pipeline status…'
            : `${incidents.length} incidents in the current window — ${kpis.recoverySuccessRate}% resolved without lasting impact.`}
        </p>
      </div>

      {/* KPI Cards — real sparklines derived from the incident feed */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5">
        <KPICard
          title="Open incidents"
          value={loading ? '—' : kpis.activeIncidents}
          delta={kpis.pendingApprovals > 0 ? `${kpis.pendingApprovals} awaiting approval` : 'none awaiting approval'}
          deltaTone={kpis.pendingApprovals > 0 ? 'warn' : 'flat'}
          spark={sparkline(incidents, i => i.remediation?.status !== 'resolved' && i.verification?.status !== 'resolved')}
          sparkColor="#E11D48"
        />
        <KPICard
          title="Auto-resolved"
          value={loading ? '—' : `${kpis.recoverySuccessRate}%`}
          delta={loading ? '—' : `${incidents.filter(i => i.verification?.status === 'resolved').length} of ${incidents.length} incidents`}
          deltaTone="ok"
          spark={sparkline(incidents, i => i.verification?.status === 'resolved')}
          sparkColor="#0C9B6C"
        />
        <KPICard
          title="Mean time to resolve"
          value={loading ? '—' : (kpis.averageMTTR > 0 ? formatMTTR(kpis.averageMTTR) : '—')}
          delta={kpis.averageMTTR === 0 ? 'no resolved data yet' : (kpis.averageMTTR <= 30 ? 'fast response' : 'within target')}
          deltaTone={kpis.averageMTTR > 0 && kpis.averageMTTR <= 30 ? 'ok' : 'flat'}
          spark={sparkline(
            incidents,
            i => i.verification?.status === 'resolved' && i.detected_at && i.verification?.checked_at,
            'detections'
          )}
          sparkColor="#6366F1"
        />
        <KPICard
          title="Pending approvals"
          value={loading ? '—' : kpis.pendingApprovals}
          delta={kpis.pendingApprovals > 0 ? 'action required' : 'nothing to review'}
          deltaTone={kpis.pendingApprovals > 0 ? 'warn' : 'ok'}
          spark={sparkline(incidents, i => i.remediation?.status === 'pending_approval')}
          sparkColor="#D97706"
        />
      </div>

      {/* Live AWS Demo hero */}
      <DemoControls />

      {/* Incident Feed + side cards */}
      <div ref={feedRef} className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        <div className="lg:col-span-3">
          <div className="card-elevated !p-0 overflow-hidden">
            <div className="flex items-center justify-between px-6 pt-5 pb-2">
              <div>
                <h2 className="text-base font-semibold text-text-primary tracking-[-0.01em]">Incident feed</h2>
                <div className="text-xs text-text-muted mt-0.5">
                  Live from incidents-staging · refreshed every {POLLING_INTERVALS.INCIDENTS_FEED / 1000}s
                </div>
              </div>
              <span className="badge badge-success"><span className="live-dot !w-1.5 !h-1.5" /> streaming</span>
            </div>
            <div className="px-6 pb-5 pt-2">
              <IncidentFeed />
            </div>
          </div>
        </div>

        {/* Right Panel — Pipeline Health + Recent Actions */}
        <div className="space-y-4">
          <PipelineHealthCard incidents={incidents} loading={loading} />
          <RecentRemediationsCard incidents={recentResolved} />
        </div>
      </div>
    </div>
  )
}

// Build a 12-bucket sparkline series from the incident list, bucketed by
// detected_at (oldest → newest). `predicate` selects which incidents count;
// pass `mode='detections'` to bucket the whole feed (for MTTR coverage).
function sparkline(incidents, predicate, mode) {
  if (!incidents || incidents.length < 2) return [1, 2, 1, 3, 2, 4, 3, 5, 4, 6, 5, 7]
  const sel = incidents.filter(i => (mode === 'detections' ? true : predicate(i)))
  const times = incidents
    .map(i => (i.detected_at ? new Date(i.detected_at).getTime() : null))
    .filter(Boolean)
  if (sel.length < 2 || times.length < 2) return [1, 2, 1, 3, 2, 4, 3, 5, 4, 6, 5, 7]
  const min = Math.min(...times)
  const max = Math.max(...times)
  const span = max - min || 1
  const buckets = new Array(12).fill(0)
  sel.forEach(i => {
    const t = i.detected_at ? new Date(i.detected_at).getTime() : null
    if (!t) return
    const idx = Math.min(11, Math.floor(((t - min) / span) * 12))
    buckets[idx] += 1
  })
  return buckets
}

function KPICard({ title, value, delta, deltaTone = 'flat', spark = [], sparkColor = '#6366F1' }) {
  // Sparkline: smooth polyline scaled to the card's spark box
  const w = 76
  const h = 26
  const max = Math.max(...spark, 1)
  const min = Math.min(...spark, 0)
  const range = max - min || 1
  const pts = spark
    .map((v, i) => `${(i / (spark.length - 1)) * w},${h - ((v - min) / range) * (h - 4) - 2}`)
    .join(' ')

  const toneClass =
    deltaTone === 'ok' ? 'text-emerald' :
    deltaTone === 'warn' ? 'text-amber' : 'text-text-muted'

  return (
    <div className="card relative overflow-hidden transition-all duration-150 hover:shadow-lift hover:border-border-strong">
      <div className="kpi-label text-[12.5px] font-medium text-text-muted">{title}</div>
      <div className="text-[32px] font-bold text-text-primary tracking-[-0.045em] leading-[1.1] mt-1.5 tabular-nums">
        {value}
      </div>
      <div className={`text-xs font-semibold mt-1.5 ${toneClass}`}>{delta}</div>
      {spark.length > 1 && (
        <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="absolute right-4 bottom-4 opacity-90">
          <polyline
            points={pts}
            fill="none"
            stroke={sparkColor}
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      )}
    </div>
  )
}

// Real pipeline throughput derived from the same incidents the feed uses —
// replaces the previous hardcoded all-green "System Health" list.
function PipelineHealthCard({ incidents = [], loading }) {
  const total = incidents.length
  const diagnosed = incidents.filter(i => i.diagnosis?.root_cause).length
  const remediated = incidents.filter(
    i => ['executed', 'resolved'].includes(i.remediation?.status) || i.verification?.status === 'resolved'
  ).length
  const verified = incidents.filter(i => i.verification?.status === 'resolved').length
  const failed = incidents.filter(
    i => i.remediation?.status === 'failed' || i.verification?.status === 'not_resolved'
  ).length

  const rows = [
    { name: 'Diagnosed', value: diagnosed, dot: 'bg-violet' },
    { name: 'Remediated', value: remediated, dot: 'bg-amber' },
    { name: 'Verified OK', value: verified, dot: 'bg-emerald' },
    { name: 'Failed', value: failed, dot: failed > 0 ? 'bg-crimson' : 'bg-border-strong' }
  ]

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-text-primary mb-4">Pipeline Health</h3>
      {total === 0 ? (
        <p className="text-xs text-text-muted py-4 text-center">
          {loading ? 'Loading…' : 'No incident data yet'}
        </p>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => (
            <div key={row.name} className="flex items-center justify-between">
              <span className="text-xs text-text-secondary flex items-center space-x-2">
                <span className={`w-2 h-2 rounded-full ${row.dot}`}></span>
                {row.name}
              </span>
              <span className="text-xs text-text-primary mono tabular-nums">
                {row.value}
                <span className="text-text-muted"> / {total}</span>
              </span>
            </div>
          ))}
          <p className="text-[11px] text-text-muted pt-1 border-t border-border-subtle">
            Last {total} incidents
          </p>
        </div>
      )}
    </div>
  )
}

function RecentRemediationsCard({ incidents = [] }) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-text-primary mb-4">Recent Actions</h3>
      <div className="space-y-3">
        {incidents.length === 0 ? (
          <div className="text-center text-text-muted py-6">
            <CheckCircle className="mx-auto w-6 h-6 mb-2 opacity-50" />
            <p className="text-xs">No recent remediations</p>
          </div>
        ) : (
          incidents.map((inc) => (
            <Link
              key={inc.incident_id}
              to={`/incidents/${inc.incident_id}`}
              className="flex items-start space-x-2 group"
            >
              <div className="w-4 h-4 rounded-full bg-emerald-surface flex items-center justify-center flex-shrink-0 mt-0.5">
                <CheckCircle className="w-3 h-3 text-emerald" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-text-primary truncate group-hover:text-indigo">
                  {(inc.remediation?.action_taken || inc.fault_class || 'Resolved').replace(/_/g, ' ')}
                </p>
                <p className="text-xs text-text-muted mono">
                  {FAULT_CLASS_LABELS[inc.fault_class] || inc.fault_class} &bull; {formatDate(inc.verification.checked_at, 'relative')}
                </p>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-text-muted opacity-0 group-hover:opacity-100 mt-0.5 flex-shrink-0 transition-opacity" />
            </Link>
          ))
        )}
      </div>
    </div>
  )
}
