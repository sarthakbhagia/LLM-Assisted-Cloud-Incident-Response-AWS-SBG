import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { RefreshCw, AlertTriangle, Clock, CheckCircle, ArrowRight, CheckSquare } from 'lucide-react'
import { apiClient } from '../config/api'
import { POLLING_INTERVALS, FAULT_CLASS_LABELS, getConfidenceLevel } from '../utils/constants'
import { formatDate, getIncidentStatus, getSeverityFromFaultClass } from '../utils/helpers'

export default function IncidentFeed() {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [filters, setFilters] = useState({
    status: '',
    faultClass: ''
  })
  const [approvingId, setApprovingId] = useState(null)
  
  const navigate = useNavigate()

  const fetchIncidents = async () => {
    try {
      const params = {}
      if (filters.status) params.status = filters.status
      if (filters.faultClass) params.faultClass = filters.faultClass
      
      const data = await apiClient.getIncidents(params)
      setIncidents(data?.items || [])
      setLastUpdated(new Date())
      setError(null)
    } catch (err) {
      console.error('Failed to fetch incidents:', err)
      setError('Failed to load incidents')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchIncidents()
    const interval = setInterval(fetchIncidents, POLLING_INTERVALS.INCIDENTS_FEED)
    return () => clearInterval(interval)
  }, [filters])

  const handleRowClick = (incidentId) => {
    navigate(`/incidents/${incidentId}`)
  }

  const handleInlineApprove = async (e, incidentId) => {
    e.stopPropagation()
    setApprovingId(incidentId)
    try {
      await apiClient.approveIncidentMain(incidentId)
      await fetchIncidents()
    } catch (err) {
      console.error('Inline approve failed:', err)
    } finally {
      setApprovingId(null)
    }
  }

  const clearFilters = () => {
    setFilters({ status: '', faultClass: '' })
  }

  if (loading && incidents.length === 0) {
    return <IncidentFeedSkeleton />
  }

  if (error && incidents.length === 0) {
    return (
      <div className="card text-center py-8">
        <AlertTriangle className="mx-auto h-8 w-8 text-crimson mb-3" />
        <p className="text-text-secondary mb-4">{error}</p>
        <button onClick={fetchIncidents} className="btn-primary">
          <RefreshCw className="w-4 h-4 mr-2" />
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Filters and Refresh Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <select 
            value={filters.status}
            onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value }))}
            className="bg-bg-input border border-border-default rounded-button px-3 py-1 text-xs text-text-primary focus:outline-none focus:border-border-strong"
          >
            <option value="">All Statuses</option>
            <option value="pending_approval">Pending Approval</option>
            <option value="approved">Approved</option>
            <option value="executed">Executed</option>
            <option value="rejected">Rejected</option>
            <option value="failed">Failed</option>
          </select>
          
          <select
            value={filters.faultClass}
            onChange={(e) => setFilters(prev => ({ ...prev, faultClass: e.target.value }))}
            className="bg-bg-input border border-border-default rounded-button px-3 py-1 text-xs text-text-primary focus:outline-none focus:border-border-strong"
          >
            <option value="">All Fault Classes</option>
            <option value="resource_exhaustion">Resource Exhaustion</option>
            <option value="misconfiguration">Misconfiguration</option>
            <option value="service_cascade">Service Cascade</option>
          </select>
          
          {(filters.status || filters.faultClass) && (
            <button onClick={clearFilters} className="btn-ghost text-xs">
              Clear Filters
            </button>
          )}
        </div>
        
        {lastUpdated && (
          <div className="flex items-center space-x-2 text-text-muted text-xs mono">
            <Clock className="w-3 h-3" />
            <span>Updated {formatDate(lastUpdated.toISOString(), 'relative')}</span>
          </div>
        )}
      </div>

      {/* Incidents Table */}
      {incidents.length === 0 ? (
        <div className="card text-center py-12">
          <CheckCircle className="mx-auto h-12 w-12 text-emerald mb-4" />
          <h3 className="text-base font-medium text-text-primary mb-1">
            {filters.status || filters.faultClass ? 'No incidents match your filters' : 'No active incidents. Your cloud environment is healthy.'}
          </h3>
          <p className="text-xs text-text-secondary mb-4">
            {filters.status || filters.faultClass ? 
              'Try adjusting your filters to see more results.' : 
              'Trigger a fault injection above to start the incident response flow.'
            }
          </p>
          {(filters.status || filters.faultClass) && (
            <button onClick={clearFilters} className="btn-ghost">
              Clear Filters
            </button>
          )}
        </div>
      ) : (
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
                  <th className="table-cell text-left">Status</th>
                  <th className="table-cell text-left">Confidence</th>
                  <th className="table-cell text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((incident) => {
                  const statusInfo = getIncidentStatus(incident)
                  const severity = getSeverityFromFaultClass(incident.fault_class)
                  const confidenceLevel = incident.diagnosis?.confidence != null
                    ? getConfidenceLevel(incident.diagnosis.confidence)
                    : null
                  const isPendingApproval = incident.remediation?.status === 'pending_approval'

                  return (
                    <tr 
                      key={incident.incident_id}
                      className="table-row cursor-pointer group"
                      onClick={() => handleRowClick(incident.incident_id)}
                    >
                      {/* Severity */}
                      <td className="table-cell">
                        <span className={`badge ${severity === 'critical' ? 'badge-critical' : 'badge-warning'}`}>
                          {severity === 'critical' ? 'Critical' : 'Warning'}
                        </span>
                      </td>

                      {/* Incident ID */}
                      <td className="table-cell">
                        <span className="mono text-text-primary font-medium">
                          {incident.incident_id ? incident.incident_id.substring(0, 8) : '—'}
                        </span>
                      </td>

                      {/* Fault Class */}
                      <td className="table-cell">
                        <span className="text-xs text-text-secondary">
                          {FAULT_CLASS_LABELS[incident.fault_class] || incident.fault_class?.replace(/_/g, ' ') || '—'}
                        </span>
                      </td>

                      {/* Affected Resource */}
                      <td className="table-cell max-w-xs">
                        <span className="mono text-xs text-text-secondary truncate block" title={incident.resource_id}>
                          {incident.resource_id || '—'}
                        </span>
                      </td>

                      {/* Detected */}
                      <td className="table-cell">
                        <span className="mono text-xs text-text-secondary" title={formatDate(incident.detected_at)}>
                          {formatDate(incident.detected_at, 'relative')}
                        </span>
                      </td>

                      {/* Status Badge */}
                      <td className="table-cell">
                        <StatusBadge statusKey={statusInfo.status} label={statusInfo.label} />
                      </td>

                      {/* AI Confidence */}
                      <td className="table-cell">
                        {confidenceLevel ? (
                          <span className={`badge ${confidenceLevel.className}`}>
                            {confidenceLevel.label} {Math.round((incident.diagnosis.confidence || 0) * 100)}%
                          </span>
                        ) : (
                          <span className="text-xs text-text-muted">—</span>
                        )}
                      </td>

                      {/* Action */}
                      <td className="table-cell text-right">
                        {isPendingApproval ? (
                          <button
                            onClick={(e) => handleInlineApprove(e, incident.incident_id)}
                            disabled={approvingId === incident.incident_id}
                            className="btn-danger py-1 px-2 h-auto text-xs inline-flex items-center space-x-1"
                            title="Approve remediation"
                          >
                            <CheckSquare className="w-3.5 h-3.5" />
                            <span>{approvingId === incident.incident_id ? 'Approving...' : 'Approve'}</span>
                          </button>
                        ) : (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleRowClick(incident.incident_id)
                            }}
                            className="btn-ghost p-1 h-auto text-xs text-text-secondary group-hover:text-text-primary group-hover:border-border-strong inline-flex items-center"
                            title="View Details"
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
      )}
      
      {loading && (
        <div className="flex items-center justify-center text-text-muted text-xs py-2">
          <RefreshCw className="w-3.5 h-3.5 animate-spin mr-2" />
          Updating incident feed...
        </div>
      )}
    </div>
  )
}

function StatusBadge({ statusKey, label }) {
  let badgeStyle = 'bg-border-strong text-text-secondary'

  switch (statusKey) {
    case 'detected':
      badgeStyle = 'bg-border-strong text-text-secondary'
      break
    case 'diagnosed':
    case 'diagnosing':
      badgeStyle = 'bg-[#1D1B36] text-[#7C7CFF] border border-[#7C7CFF]/30'
      break
    case 'pending_approval':
      badgeStyle = 'badge-warning'
      break
    case 'approved':
    case 'executed':
    case 'resolved':
      badgeStyle = 'badge-success'
      break
    case 'not_resolved':
    case 'failed':
      badgeStyle = 'badge-critical'
      break
    case 'rejected':
      badgeStyle = 'bg-border-strong text-text-muted'
      break
    default:
      badgeStyle = 'badge-info'
  }

  return (
    <span className={`badge ${badgeStyle}`}>
      {label}
    </span>
  )
}

function IncidentFeedSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="pulse-loading h-8 w-32 rounded-button"></div>
          <div className="pulse-loading h-8 w-32 rounded-button"></div>
        </div>
        <div className="pulse-loading h-4 w-40"></div>
      </div>

      <div className="card p-0 overflow-hidden">
        <div className="table-header p-3">
          <div className="pulse-loading h-4 w-full"></div>
        </div>
        
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="border-b border-border-subtle p-3">
            <div className="flex justify-between items-center gap-3">
              <div className="pulse-loading h-6 w-16 rounded-badge"></div>
              <div className="pulse-loading h-4 w-20"></div>
              <div className="pulse-loading h-4 w-32"></div>
              <div className="pulse-loading h-4 w-28"></div>
              <div className="pulse-loading h-4 w-20"></div>
              <div className="pulse-loading h-6 w-24 rounded-badge"></div>
              <div className="pulse-loading h-6 w-20 rounded-badge"></div>
              <div className="pulse-loading h-6 w-8 rounded-button"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}