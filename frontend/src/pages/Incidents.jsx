import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, RefreshCw, CheckCircle, Clock, ArrowRight,
  Search, X, ChevronDown, CheckSquare
} from 'lucide-react'
import { apiClient } from '../config/api'
import { FAULT_CLASS_LABELS, getConfidenceLevel } from '../utils/constants'
import { formatDate, getIncidentStatus, getSeverityFromFaultClass } from '../utils/helpers'

const CONFIDENCE_FILTER_THRESHOLDS = {
  high: 0.9,
  medium: 0.7,
  low: 0,
}

const DATE_RANGE_HOURS = {
  '1h': 1,
  '6h': 6,
  '24h': 24,
  '7d': 168,
}

export default function Incidents() {
  const navigate = useNavigate()
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [cursor, setCursor] = useState(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [approvingId, setApprovingId] = useState(null)

  const [filters, setFilters] = useState({
    status: '',
    faultClass: '',
    confidence: '',
    dateRange: '',
    search: '',
  })

  const buildParams = useCallback((cur = null) => {
    const params = { limit: 20 }
    if (filters.status) params.status = filters.status
    if (filters.faultClass) params.fault_class = filters.faultClass
    if (cur) params.next_token = cur
    return params
  }, [filters])

  const applyClientFilters = (list) => {
    return list.filter(inc => {
      // Search filter (client-side)
      if (filters.search) {
        const q = filters.search.toLowerCase()
        const idMatch = inc.incident_id?.toLowerCase().includes(q)
        const resMatch = inc.resource_id?.toLowerCase().includes(q)
        if (!idMatch && !resMatch) return false
      }

      // Confidence filter (client-side)
      if (filters.confidence) {
        const conf = parseFloat(inc.diagnosis?.confidence ?? -1)
        if (filters.confidence === 'high' && conf < CONFIDENCE_FILTER_THRESHOLDS.high) return false
        if (filters.confidence === 'medium' && (conf < CONFIDENCE_FILTER_THRESHOLDS.medium || conf >= CONFIDENCE_FILTER_THRESHOLDS.high)) return false
        if (filters.confidence === 'low' && conf >= CONFIDENCE_FILTER_THRESHOLDS.medium) return false
      }

      // Date range filter (client-side)
      if (filters.dateRange && DATE_RANGE_HOURS[filters.dateRange]) {
        const hours = DATE_RANGE_HOURS[filters.dateRange]
        const cutoff = new Date(Date.now() - hours * 3600 * 1000)
        if (!inc.detected_at || new Date(inc.detected_at) < cutoff) return false
      }

      return true
    })
  }

  const fetchIncidents = useCallback(async (resetList = true) => {
    try {
      if (resetList) setLoading(true)
      const data = await apiClient.getIncidents(buildParams(resetList ? null : cursor))
      const incoming = data?.items || []
      setIncidents(prev => resetList ? incoming : [...prev, ...incoming])
      setHasMore(Boolean(data?.next_token))
      setCursor(data?.next_token || null)
      setLastUpdated(new Date())
      setError(null)
    } catch (err) {
      console.error('Failed to fetch incidents:', err)
      setError('Failed to load incidents')
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [buildParams, cursor])

  useEffect(() => {
    fetchIncidents(true)
  }, [filters.status, filters.faultClass])

  const handleLoadMore = async () => {
    setLoadingMore(true)
    await fetchIncidents(false)
  }

  const handleInlineApprove = async (e, incidentId) => {
    e.stopPropagation()
    setApprovingId(incidentId)
    try {
      await apiClient.approveIncidentMain(incidentId)
      await fetchIncidents(true)
    } catch (err) {
      console.error('Inline approve failed:', err)
    } finally {
      setApprovingId(null)
    }
  }

  const clearFilters = () => {
    setFilters({ status: '', faultClass: '', confidence: '', dateRange: '', search: '' })
  }

  const hasFilters = Object.values(filters).some(Boolean)
  const displayed = applyClientFilters(incidents)

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Incidents</h1>
          <p className="text-xs text-text-muted mt-0.5">
            All incidents across fault classes and pipeline stages
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {lastUpdated && (
            <span className="text-xs text-text-muted mono">
              Updated {formatDate(lastUpdated.toISOString(), 'relative')}
            </span>
          )}
          <button onClick={() => fetchIncidents(true)} className="btn-ghost" title="Refresh">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-3 items-end">
          {/* Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              placeholder="Search ID or resource..."
              value={filters.search}
              onChange={e => setFilters(p => ({ ...p, search: e.target.value }))}
              className="bg-bg-input border border-border-default rounded-button pl-7 pr-3 py-1 text-xs text-text-primary focus:outline-none focus:border-border-strong w-48"
            />
            {filters.search && (
              <button
                onClick={() => setFilters(p => ({ ...p, search: '' }))}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Status */}
          <Select
            value={filters.status}
            onChange={v => setFilters(p => ({ ...p, status: v }))}
            label="Status"
            options={[
              { value: '', label: 'All Statuses' },
              { value: 'pending_approval', label: 'Pending Approval' },
              { value: 'approved', label: 'Approved' },
              { value: 'executed', label: 'Executed' },
              { value: 'rejected', label: 'Rejected' },
              { value: 'failed', label: 'Failed' },
            ]}
          />

          {/* Fault Class */}
          <Select
            value={filters.faultClass}
            onChange={v => setFilters(p => ({ ...p, faultClass: v }))}
            label="Fault Class"
            options={[
              { value: '', label: 'All Classes' },
              { value: 'resource_exhaustion', label: 'Resource Exhaustion' },
              { value: 'misconfiguration', label: 'Misconfiguration' },
              { value: 'service_cascade', label: 'Service Cascade' },
            ]}
          />

          {/* Confidence */}
          <Select
            value={filters.confidence}
            onChange={v => setFilters(p => ({ ...p, confidence: v }))}
            label="Confidence"
            options={[
              { value: '', label: 'All Confidence' },
              { value: 'high', label: 'High (>= 90%)' },
              { value: 'medium', label: 'Medium (70-90%)' },
              { value: 'low', label: 'Low (< 70%)' },
            ]}
          />

          {/* Date Range */}
          <Select
            value={filters.dateRange}
            onChange={v => setFilters(p => ({ ...p, dateRange: v }))}
            label="Date Range"
            options={[
              { value: '', label: 'All Time' },
              { value: '1h', label: 'Last 1 hour' },
              { value: '6h', label: 'Last 6 hours' },
              { value: '24h', label: 'Last 24 hours' },
              { value: '7d', label: 'Last 7 days' },
            ]}
          />

          {hasFilters && (
            <button onClick={clearFilters} className="btn-ghost text-xs h-auto py-1">
              Clear All
            </button>
          )}
        </div>

        <div className="mt-3 text-xs text-text-muted">
          {displayed.length} incident{displayed.length !== 1 ? 's' : ''} shown
          {hasFilters && ` (filtered from ${incidents.length})`}
        </div>
      </div>

      {/* Table */}
      {error ? (
        <div className="card text-center py-12">
          <AlertTriangle className="mx-auto h-10 w-10 text-crimson mb-3" />
          <p className="text-text-secondary mb-4">{error}</p>
          <button onClick={() => fetchIncidents(true)} className="btn-primary">
            <RefreshCw className="w-4 h-4 mr-2" />Retry
          </button>
        </div>
      ) : loading ? (
        <IncidentsTableSkeleton />
      ) : displayed.length === 0 ? (
        <div className="card text-center py-12">
          <CheckCircle className="mx-auto h-12 w-12 text-emerald mb-4" />
          <h3 className="text-base font-medium text-text-primary mb-1">
            {hasFilters ? 'No incidents match your filters' : 'No incidents found'}
          </h3>
          <p className="text-xs text-text-secondary">
            {hasFilters ? 'Try adjusting filters.' : 'Trigger a fault injection to create incidents.'}
          </p>
          {hasFilters && (
            <button onClick={clearFilters} className="btn-ghost mt-3">Clear Filters</button>
          )}
        </div>
      ) : (
        <>
          <div className="card p-0 overflow-hidden border border-border-default">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr className="table-header">
                    <th className="table-cell text-left">Severity</th>
                    <th className="table-cell text-left">Incident ID</th>
                    <th className="table-cell text-left">Fault Class</th>
                    <th className="table-cell text-left">Affected Resource</th>
                    <th className="table-cell text-left">Detected</th>
                    <th className="table-cell text-left">Pipeline Status</th>
                    <th className="table-cell text-left">AI Confidence</th>
                    <th className="table-cell text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {displayed.map((incident) => {
                    const statusInfo = getIncidentStatus(incident)
                    const severity = getSeverityFromFaultClass(incident.fault_class)
                    const conf = incident.diagnosis?.confidence != null
                      ? getConfidenceLevel(incident.diagnosis.confidence)
                      : null
                    const isPending = incident.remediation?.status === 'pending_approval'

                    return (
                      <tr
                        key={incident.incident_id}
                        className="table-row cursor-pointer group"
                        onClick={() => navigate(`/incidents/${incident.incident_id}`)}
                      >
                        <td className="table-cell">
                          <span className={`badge ${severity === 'critical' ? 'badge-critical' : 'badge-warning'}`}>
                            {severity === 'critical' ? 'Critical' : 'Warning'}
                          </span>
                        </td>
                        <td className="table-cell">
                          <span className="mono text-text-primary font-medium">
                            {incident.incident_id?.substring(0, 8) || '—'}
                          </span>
                        </td>
                        <td className="table-cell">
                          <span className="text-xs text-text-secondary">
                            {FAULT_CLASS_LABELS[incident.fault_class] || incident.fault_class?.replace(/_/g, ' ') || '—'}
                          </span>
                        </td>
                        <td className="table-cell max-w-xs">
                          <span className="mono text-xs text-text-secondary truncate block" title={incident.resource_id}>
                            {incident.resource_id || '—'}
                          </span>
                        </td>
                        <td className="table-cell">
                          <span className="mono text-xs text-text-secondary" title={formatDate(incident.detected_at)}>
                            {formatDate(incident.detected_at, 'relative')}
                          </span>
                        </td>
                        <td className="table-cell">
                          <StatusBadge statusKey={statusInfo.status} label={statusInfo.label} />
                        </td>
                        <td className="table-cell">
                          {conf ? (
                            <span className={`badge ${conf.className}`}>
                              {conf.label} {Math.round((incident.diagnosis.confidence || 0) * 100)}%
                            </span>
                          ) : (
                            <span className="text-xs text-text-muted">—</span>
                          )}
                        </td>
                        <td className="table-cell text-right">
                          {isPending ? (
                            <button
                              onClick={(e) => handleInlineApprove(e, incident.incident_id)}
                              disabled={approvingId === incident.incident_id}
                              className="btn-danger py-1 px-2 h-auto text-xs inline-flex items-center space-x-1"
                            >
                              <CheckSquare className="w-3.5 h-3.5" />
                              <span>{approvingId === incident.incident_id ? '...' : 'Approve'}</span>
                            </button>
                          ) : (
                            <button
                              onClick={(e) => { e.stopPropagation(); navigate(`/incidents/${incident.incident_id}`) }}
                              className="btn-ghost p-1 h-auto text-xs inline-flex items-center"
                            >
                              <span className="mr-1 hidden sm:inline">Details</span>
                              <ArrowRight className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Load More */}
          {hasMore && (
            <div className="text-center">
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="btn-ghost"
              >
                {loadingMore ? (
                  <><RefreshCw className="w-4 h-4 mr-2 animate-spin" />Loading...</>
                ) : (
                  <><ChevronDown className="w-4 h-4 mr-2" />Load More</>
                )}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Select({ value, onChange, options }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="bg-bg-input border border-border-default rounded-button px-3 py-1 text-xs text-text-primary focus:outline-none focus:border-border-strong"
    >
      {options.map(opt => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  )
}

function StatusBadge({ statusKey, label }) {
  const styles = {
    detected: 'bg-border-strong text-text-secondary',
    diagnosed: 'bg-violet-surface text-violet',
    pending_approval: 'badge-warning',
    approved: 'badge-success',
    executed: 'badge-success',
    resolved: 'badge-success',
    not_resolved: 'badge-critical',
    failed: 'badge-critical',
    rejected: 'bg-border-strong text-text-muted',
  }
  return (
    <span className={`badge ${styles[statusKey] || 'badge-info'}`}>{label}</span>
  )
}

function IncidentsTableSkeleton() {
  return (
    <div className="card p-0 overflow-hidden">
      <div className="table-header p-3">
        <div className="pulse-loading h-4 w-full"></div>
      </div>
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="border-b border-border-subtle p-3">
          <div className="flex gap-4 items-center">
            {[16, 20, 32, 28, 20, 24, 20, 8].map((w, j) => (
              <div key={j} className={`pulse-loading h-5 rounded w-${w} flex-shrink-0`}></div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
