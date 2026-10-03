import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  Eye,
  ChevronDown,
  ChevronRight,
  Loader2,
  Zap,
  Check,
  AlertCircle,
  X,
  BookOpen,
  Shield
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ReferenceLine, ResponsiveContainer
} from 'recharts'
import { apiClient } from '../config/api'
import { 
  POLLING_INTERVALS, 
  PIPELINE_STAGES, 
  getConfidenceLevel,
  ACTION_RISK,
  ACTION_LABELS,
  HIGH_RISK_ACTIONS,
  CHART_COLORS
} from '../utils/constants'
import { 
  formatDate, 
  getIncidentStatus, 
  getPipelineStageStatus, 
  getSeverityFromFaultClass
} from '../utils/helpers'

export default function IncidentDetail() {
  const { incidentId } = useParams()
  const navigate = useNavigate()
  const [incident, setIncident] = useState(null)
  const [rawData, setRawData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedStages, setExpandedStages] = useState({})
  const [activeTab, setActiveTab] = useState('metrics')
  const [retriggering, setRetriggering] = useState(false)
  const [retriggerMessage, setRetriggerMessage] = useState(null)
  const [evidenceError, setEvidenceError] = useState(null)
  // Track the remediation status at page load to detect stale state
  const [initialRemStatus, setInitialRemStatus] = useState(null)

  const fetchIncidentDetail = useCallback(async () => {
    try {
      // Fetch the incident record and the evidence bundle in parallel.
      // Evidence may not exist yet (404 if collector hasn't run), so use allSettled.
      const [detailResult, evidenceResult] = await Promise.allSettled([
        apiClient.getIncidentDetail(incidentId),
        apiClient.getIncidentEvidence(incidentId),
      ])

      if (detailResult.status === 'fulfilled') {
        const data = detailResult.value
        // After envelope unwrap, GET /api/incidents/:id returns the incident object directly
        const incidentObj = data?.incident_id ? data : (data?.incident ?? data)
        setIncident(incidentObj)
        if (initialRemStatus === null && incidentObj?.remediation?.status) {
          setInitialRemStatus(incidentObj.remediation.status)
        }
      } else {
        throw detailResult.reason
      }

      if (evidenceResult.status === 'fulfilled') {
        // Store the full response: { incident_id, fault_class, s3_key, evidence: {...} }
        // EvidenceTabContent reads data.evidence internally
        setRawData(evidenceResult.value)
        setEvidenceError(null)
      } else {
        const errMsg = evidenceResult.reason?.message || String(evidenceResult.reason)
        // 404 means the collector hasn't run yet — silently show empty state.
        // Any other error (e.g. wrong API URL, 500) is surfaced so operators can diagnose it.
        const is404 = errMsg.includes('404') || errMsg.toLowerCase().includes('not found') || errMsg.toLowerCase().includes('not yet collected')
        if (!is404) {
          setEvidenceError(errMsg)
        }
      }

      setError(null)
    } catch (err) {
      console.error('Failed to fetch incident detail:', err)
      setError('Failed to load incident details')
    } finally {
      setLoading(false)
    }
  }, [incidentId, initialRemStatus])

  useEffect(() => {
    fetchIncidentDetail()
    const interval = setInterval(fetchIncidentDetail, POLLING_INTERVALS.INCIDENT_DETAIL)
    return () => clearInterval(interval)
  }, [incidentId])

  const handleRetriggerDiagnosis = async () => {
    if (retriggering || !incidentId) return
    setRetriggering(true)
    setRetriggerMessage(null)

    try {
      await apiClient.triggerDiagnosis(incidentId)
      setRetriggerMessage({ type: 'success', text: 'Diagnosis re-triggered. Polling for results...' })
      setTimeout(fetchIncidentDetail, 3000)
    } catch (err) {
      console.error('Failed to re-trigger diagnosis:', err)
      setRetriggerMessage({ type: 'error', text: err.message || 'Failed to re-trigger diagnosis' })
    } finally {
      setRetriggering(false)
    }
  }

  const toggleStageExpansion = (stageKey) => {
    setExpandedStages(prev => ({
      ...prev,
      [stageKey]: !prev[stageKey]
    }))
  }

  if (loading) {
    return <IncidentDetailSkeleton />
  }

  if (error || !incident) {
    return (
      <div className="space-y-4">
        <button 
          onClick={() => navigate('/')}
          className="btn-ghost"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Overview
        </button>
        <div className="card text-center py-12">
          <AlertTriangle className="mx-auto h-12 w-12 text-crimson mb-4" />
          <h3 className="text-lg font-medium text-text-primary mb-2">
            {error || 'Incident not found'}
          </h3>
          <button onClick={fetchIncidentDetail} className="btn-primary">
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </button>
        </div>
      </div>
    )
  }

  const status = getIncidentStatus(incident)
  const severity = getSeverityFromFaultClass(incident.fault_class)

  return (
    <div className="space-y-6">
      {/* Header */}
      <IncidentHeader 
        incident={incident} 
        status={status} 
        severity={severity}
        onBack={() => navigate('/')}
        onRefresh={fetchIncidentDetail}
      />

      {/* Main Content - 3 Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column - Lifecycle Timeline (25%) */}
        <div className="lg:col-span-3">
          <LifecycleTimeline 
            incident={incident}
            expandedStages={expandedStages}
            onToggleStage={toggleStageExpansion}
          />
        </div>

        {/* Center Column - AI Diagnosis + Evidence (50%) */}
        <div className="lg:col-span-6 space-y-6">
          <DiagnosisPanel 
            incident={incident} 
            onRetrigger={handleRetriggerDiagnosis}
            retriggering={retriggering}
            retriggerMessage={retriggerMessage}
          />
          <EvidenceExplorer 
            rawData={rawData}
            faultClass={incident.fault_class}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            fetchError={evidenceError}
          />
        </div>

        {/* Right Column - Approval + Verification (25%) */}
        <div className="lg:col-span-3 space-y-6">
          <ApprovalCard
            incident={incident}
            initialRemStatus={initialRemStatus}
            onApproved={fetchIncidentDetail}
          />
          <VerificationCard incident={incident} />
        </div>
      </div>
    </div>
  )
}

function IncidentHeader({ incident, status, severity, onBack, onRefresh }) {
  const [copied, setCopied] = useState(false)

  const copyId = () => {
    navigator.clipboard.writeText(incident.incident_id || '')
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <button onClick={onBack} className="btn-ghost">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Overview
        </button>
        <button onClick={onRefresh} className="btn-ghost" title="Refresh">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start space-x-4">
          <span className={`badge mt-0.5 ${severity === 'critical' ? 'badge-critical' : 'badge-warning'}`}>
            {severity === 'critical' ? 'Critical' : 'Warning'}
          </span>
          <div>
            <h1 className="text-xl font-semibold text-text-primary">
              {incident.diagnosis?.root_cause || 'Investigating Incident'}
            </h1>
            <div className="flex flex-wrap items-center gap-2 mt-1.5 text-xs text-text-secondary">
              <button
                onClick={copyId}
                className="mono text-text-primary hover:text-text-secondary transition-colors flex items-center space-x-1"
                title="Copy incident ID"
              >
                <span>{incident.incident_id}</span>
                {copied && <Check className="w-3 h-3 text-emerald" />}
              </button>
              <span className="text-text-muted">•</span>
              <span>Detected {formatDate(incident.detected_at, 'relative')}</span>
              <span className="text-text-muted">•</span>
              <span className="capitalize">{incident.fault_class?.replace(/_/g, ' ')}</span>
              {incident.detection_source && (
                <>
                  <span className="text-text-muted">•</span>
                  <span>{incident.detection_source}</span>
                </>
              )}
              {incident.resource_id && (
                <>
                  <span className="text-text-muted">•</span>
                  <span className="mono">{incident.resource_id}</span>
                </>
              )}
            </div>
          </div>
        </div>
        
        <span className={`badge ${status.className}`}>
          {status.label}
        </span>
      </div>
    </div>
  )
}

function LifecycleTimeline({ incident, expandedStages, onToggleStage }) {
  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-6">Incident Lifecycle</h3>
      
      <div className="space-y-4">
        {PIPELINE_STAGES.map((stage, index) => {
          const stageStatus = getPipelineStageStatus(incident, stage.key)
          const isExpanded = expandedStages[stage.key]
          const hasDetails = getStageDetails(incident, stage.key)
          
          return (
            <div key={stage.key} className="flex space-x-3">
              {/* Status Icon */}
              <div className="flex flex-col items-center">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center ${getStageIconStyle(stageStatus)}`}>
                  {getStageIcon(stageStatus)}
                </div>
                {index < PIPELINE_STAGES.length - 1 && (
                  <div className={`w-px h-8 mt-2 ${
                    stageStatus === 'not_started' ? 'border-l border-dashed border-border-subtle' : 'bg-border-subtle'
                  }`} />
                )}
              </div>

              {/* Stage Content */}
              <div className="flex-1 pb-4">
                <div 
                  className={`flex items-center justify-between ${hasDetails ? 'cursor-pointer' : ''}`}
                  onClick={hasDetails ? () => onToggleStage(stage.key) : undefined}
                >
                  <div>
                    <div className="text-sm font-medium text-text-primary">
                      {stage.label}
                    </div>
                    <div className="text-xs text-text-muted mono">
                      {getStageTimestamp(incident, stage.key)}
                    </div>
                  </div>
                  
                  {hasDetails && (
                    <div className="ml-2">
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-text-secondary" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-text-secondary" />
                      )}
                    </div>
                  )}
                </div>

                {isExpanded && hasDetails && (
                  <div className="mt-3 p-3 bg-bg-elevated rounded-card">
                    <StageDetails incident={incident} stage={stage.key} />
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function DiagnosisPanel({ incident, onRetrigger, retriggering, retriggerMessage }) {
  const diagnosis = incident.diagnosis || {}
  const hasRootCause = Boolean(diagnosis.root_cause)
  const confidence = getConfidenceLevel(diagnosis.confidence || 0)
  const [traceExpanded, setTraceExpanded] = useState(false)
  const incidentId = incident.incident_id
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
<div className="flex items-center space-x-2">
        <h3 className="text-sm font-medium text-text-primary">AI Diagnosis</h3>
        {hasRootCause && diagnosis.model_used && (
          <span className="badge badge-info text-xs">{diagnosis.model_used}</span>
        )}
        {hasRootCause && !diagnosis.failure_mode && (
          <span className="badge badge-success text-xs">Schema validated</span>
        )}
      </div>
        {!hasRootCause && (
          <button
            onClick={onRetrigger}
            disabled={retriggering}
            className="btn-ghost text-xs flex items-center space-x-1.5"
          >
            {retriggering ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-amber" />
                <span>Running...</span>
              </>
            ) : (
              <>
                <Zap className="w-3.5 h-3.5 text-amber" />
                <span>Re-trigger Diagnosis</span>
              </>
            )}
          </button>
        )}
      </div>

      {/* Failure mode banner - shows full failure detail, not just the type prefix */}
      {diagnosis.failure_mode && (
        <div className="mb-4 p-3 bg-crimson-surface border border-crimson/30 rounded-card flex items-start space-x-2">
          <AlertCircle className="w-4 h-4 text-crimson flex-shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-xs text-crimson font-medium">
              Diagnosis Failure Mode: {diagnosis.failure_mode.split(':')[0].replace(/_/g, ' ')}
            </p>
            {diagnosis.failure_mode.includes(':') && (
              <p className="text-xs text-text-secondary mt-0.5 font-mono break-all">
                {diagnosis.failure_mode.split(':').slice(1).join(':').trim()}
              </p>
            )}
          </div>
        </div>
      )}

      {/* SE-2: Heuristic diagnosis warning - shown when LLM was unavailable and a
          pattern-matched fallback was used. Confidence is fixed at 30% in this case.
          This banner makes the distinction visible instead of showing 85-90% bars. */}
      {diagnosis.is_heuristic && (
        <div className="mb-4 p-3 bg-amber-surface border border-amber/30 rounded-card flex items-start space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs text-amber font-medium">Heuristic Diagnosis</p>
            <p className="text-xs text-text-secondary mt-0.5">
              LLM was unavailable or produced unparseable output. This diagnosis was
              pattern-matched from the fault class only - not from evidence. Confidence
              is low (30%) and manual review is recommended before approving.
            </p>
          </div>
        </div>
      )}

      {/* SE-14: Notify failed warning - Slack alert was not sent */}
      {diagnosis.notify_failed && (
        <div className="mb-4 p-3 bg-amber-surface border border-amber/30 rounded-card flex items-start space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs text-amber font-medium">Slack Notification Failed</p>
            <p className="text-xs text-text-secondary mt-0.5">
              The on-call Slack message could not be sent. No engineer was automatically
              notified. Manual approval is required from this dashboard.
            </p>
          </div>
        </div>
      )}

      {retriggerMessage && (
        <div className={`mb-4 p-2.5 rounded text-xs flex items-center space-x-2 ${
          retriggerMessage.type === 'success' ? 'bg-emerald-surface text-emerald' : 'bg-crimson-surface text-crimson'
        }`}>
          {retriggerMessage.type === 'success' ? <Check className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
          <span>{retriggerMessage.text}</span>
        </div>
      )}
      
      {hasRootCause ? (
        <div className="space-y-4">
          {/* Root Cause */}
          <div>
            <label className="text-xs text-text-secondary uppercase tracking-wide">Root Cause</label>
            <p className="text-sm text-text-primary mt-1 font-medium">{diagnosis.root_cause}</p>
            {diagnosis.explanation && (
              <p className="text-xs text-text-secondary mt-2 leading-relaxed">{diagnosis.explanation}</p>
            )}
          </div>
          
          {/* Confidence + RAG row */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <label className="text-xs text-text-secondary uppercase tracking-wide">Confidence</label>
              <div className="flex items-center space-x-2 mt-1">
                <span className={`badge ${confidence.className}`}>
                  {confidence.label}
                </span>
                <span className="mono text-xs text-text-muted">
                  {Math.round((diagnosis.confidence || 0) * 100)}%
                </span>
              </div>
            </div>
            
            <div className="text-right">
              <label className="text-xs text-text-secondary uppercase tracking-wide">Runbook Context</label>
              <div className="flex items-center space-x-1 mt-1 justify-end">
                <BookOpen className="w-3.5 h-3.5 text-text-muted" />
                <span className="text-xs text-text-primary">
                  {diagnosis.used_rag
                    ? `Yes — ${incident.fault_class?.replace(/_/g, ' ')}`
                    : 'No'}
                </span>
              </div>
            </div>
          </div>
          
          {/* Suggested Action */}
          {diagnosis.suggested_action && (
            <div>
              <label className="text-xs text-text-secondary uppercase tracking-wide">Suggested Action</label>
              <div className="mt-1 flex items-center space-x-2">
                <p className="text-xs text-text-primary mono bg-bg-input px-2 py-1.5 rounded inline-block">
                  {diagnosis.suggested_action}
                </p>
                <span className="text-xs text-text-secondary">
                  {ACTION_LABELS[diagnosis.suggested_action] || diagnosis.suggested_action.replace(/_/g, ' ')}
                </span>
              </div>
            </div>
          )}
          
          {/* Reasoning Trace */}
          {diagnosis.reasoning_trace && (
            <div>
              <button
                onClick={() => setTraceExpanded(p => !p)}
                className="flex items-center space-x-1 text-xs text-text-secondary uppercase tracking-wide hover:text-text-primary transition-colors"
              >
                {traceExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                <span>Reasoning Trace</span>
              </button>
              {traceExpanded && (
                <div className="mt-2 p-3 bg-bg-input rounded-card max-h-48 overflow-y-auto">
                  <pre className="text-xs text-text-code font-mono whitespace-pre-wrap">
                    {diagnosis.reasoning_trace}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Pipeline Trace debug panel */}
          <PipelineTracePanel incidentId={incidentId} />

        </div>
      ) : (
        <div className="text-center py-8">
          <div className="flex items-center justify-center space-x-2 text-amber mb-3">
            <span className="w-3 h-3 rounded-full bg-amber animate-pulse"></span>
            <span className="text-sm font-medium">Diagnosis Pending...</span>
          </div>
          <p className="text-xs text-text-secondary mb-4">
            The LLM diagnosis pipeline is analyzing collected evidence.
          </p>
          <button
            onClick={onRetrigger}
            disabled={retriggering}
            className="btn-primary text-xs"
          >
            {retriggering ? 'Invoking Diagnosis...' : 'Re-trigger Diagnosis'}
          </button>
        </div>
      )}
    </div>
  )
}

function PipelineTracePanel({ incidentId }) {
  const [open, setOpen] = useState(false)
  const [trace, setTrace] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [artifactContent, setArtifactContent] = useState({}) // key -> content string

  const fetchTrace = async () => {
    if (open && trace) { setOpen(false); return }
    setOpen(true)
    setLoading(true)
    setError(null)
    try {
      const data = await apiClient.getIncidentTrace(incidentId)
      setTrace(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchArtifact = async (key) => {
    if (artifactContent[key]) {
      setArtifactContent(prev => ({ ...prev, [key]: prev[key] === '__hide__' ? null : '__hide__' }))
      return
    }
    try {
      const data = await apiClient.getIncidentTraceArtifact(incidentId, key)
      const content = data?.content
      setArtifactContent(prev => ({
        ...prev,
        [key]: typeof content === 'string' ? content : JSON.stringify(content, null, 2)
      }))
    } catch (err) {
      setArtifactContent(prev => ({ ...prev, [key]: `Error: ${err.message}` }))
    }
  }

  const summary = trace?.pipeline_summary || {}

  return (
    <div className="border-t border-border-default pt-3 mt-1">
      <button
        onClick={fetchTrace}
        className="flex items-center space-x-1 text-xs text-text-muted uppercase tracking-wide hover:text-text-primary transition-colors"
      >
        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        <span>Pipeline Trace</span>
        <span className="text-text-muted normal-case tracking-normal">(debug)</span>
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {loading && <p className="text-xs text-text-muted">Loading trace...</p>}
          {error && <p className="text-xs text-crimson font-mono">{error}</p>}
          {trace && (
            <>
              {/* Pipeline summary table */}
              <div className="grid grid-cols-2 gap-1.5 text-xs">
                {[
                  ['Diagnosis Status', summary.diagnosis_status],
                  ['Model Used', summary.model_used],
                  ['Is Heuristic', summary.is_heuristic ? 'YES' : 'No'],
                  ['Confidence', summary.confidence != null ? `${Math.round(summary.confidence * 100)}%` : '-'],
                  ['Suggested Action', summary.suggested_action],
                  ['Notify Failed', summary.notify_failed ? 'YES' : 'No'],
                  ['Remediation Status', summary.remediation_status],
                  ['Verification Status', summary.verification_status],
                ].map(([label, val]) => (
                  <div key={label} className="contents">
                    <span className="text-text-muted">{label}</span>
                    <span className={`font-mono text-text-primary break-all ${
                      (val === 'YES' || val === 'parse_failed') ? 'text-crimson' : ''
                    }`}>{val ?? '-'}</span>
                  </div>
                ))}
              </div>

              {/* Full failure_mode string */}
              {summary.failure_mode_full && (
                <div className="p-2 bg-crimson-surface border border-crimson/20 rounded-card">
                  <p className="text-xs text-text-muted mb-1">Full Failure Mode</p>
                  <p className="text-xs font-mono text-crimson break-all">{summary.failure_mode_full}</p>
                </div>
              )}

              {/* S3 artifacts */}
              {trace.s3_artifacts?.length > 0 && (
                <div>
                  <p className="text-xs text-text-muted mb-1.5">S3 Artifacts ({trace.s3_artifacts.length})</p>
                  <div className="space-y-1.5">
                    {trace.s3_artifacts.map(a => (
                      <div key={a.key} className="border border-border-default rounded-card overflow-hidden">
                        <div className="flex items-center justify-between px-2 py-1.5 bg-bg-elevated">
                          <span className="text-xs font-mono text-text-secondary truncate max-w-xs" title={a.key}>
                            {a.key.split('/').pop()}
                          </span>
                          <div className="flex items-center space-x-2 flex-shrink-0">
                            <span className="text-xs text-text-muted">{(a.size_bytes / 1024).toFixed(1)}kb</span>
                            <button
                              onClick={() => fetchArtifact(a.key)}
                              className="text-xs text-accent hover:underline"
                            >
                              {artifactContent[a.key] && artifactContent[a.key] !== '__hide__' ? 'Hide' : 'View'}
                            </button>
                          </div>
                        </div>
                        {artifactContent[a.key] && artifactContent[a.key] !== '__hide__' && (
                          <div className="max-h-64 overflow-y-auto bg-bg-input p-2">
                            <pre className="text-xs font-mono text-text-code whitespace-pre-wrap break-all">
                              {artifactContent[a.key]}
                            </pre>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {trace.s3_artifacts?.length === 0 && (
                <p className="text-xs text-text-muted">No S3 artifacts found for this incident.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export function EvidenceExplorer({ rawData, faultClass, activeTab, onTabChange, fetchError }) {
  // Determine available tabs based on fault_class
  const tabs = ['raw json']
  if (faultClass === 'resource_exhaustion' || faultClass === 'service_cascade') {
    tabs.unshift('logs', 'metrics')
  }
  if (faultClass === 'service_cascade') {
    tabs.splice(tabs.indexOf('logs') + 1, 0, 'x-ray')
  }
  if (faultClass === 'misconfiguration') {
    tabs.unshift('config')
    if (rawData?.evidence?.evidence?.guardduty_finding) tabs.splice(1, 0, 'guardduty')
    // NOTE: logs tab is intentionally NOT added for misconfiguration.
    // Misconfiguration incidents are AWS Config findings, not Lambda failures.
    // The Config tab is the primary evidence view; adding logs would make an
    // intentionally-empty tab the default (since unshift puts it first).
  }

  // Ensure active tab is valid for this fault class
  const validTab = tabs.includes(activeTab) ? activeTab : tabs[0]

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-text-primary">Evidence Explorer</h3>
      </div>

      {/* SE: Show error when the evidence API itself fails (e.g. wrong VITE_API_BASE_URL) */}
      {fetchError && (
        <div className="mb-4 p-3 bg-crimson-surface border border-crimson/30 rounded-card flex items-start space-x-2">
          <AlertTriangle className="w-4 h-4 text-crimson flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs text-crimson font-medium">Evidence API Error</p>
            <p className="text-xs text-text-secondary mt-0.5">
              {fetchError} — Check that VITE_API_BASE_URL ends at /Prod (not /Prod/api).
            </p>
          </div>
        </div>
      )}

      {/* Collector-side evidence_error: collection ran but threw an exception before producing data */}
      {rawData?.evidence?.evidence_error && (
        <div className="mb-4 p-3 bg-amber-surface border border-amber/30 rounded-card flex items-start space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs text-amber font-medium">Evidence Collection Error</p>
            <p className="text-xs text-text-secondary mt-0.5">
              The collector ran but encountered an error before producing evidence data.
              Check the collector Lambda logs for the full stack trace.
            </p>
            <p className="text-xs text-text-tertiary mt-1 font-mono break-all">
              {rawData.evidence.evidence_error}
            </p>
          </div>
        </div>
      )}

      {/* SE-5: Show warning when function name resolution failed and logs/metrics are missing */}
      {rawData?.evidence?.evidence?.evidence_collection_partial && (
        <div className="mb-4 p-3 bg-amber-surface border border-amber/30 rounded-card flex items-start space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs text-amber font-medium">Partial Evidence Collection</p>
            <p className="text-xs text-text-secondary mt-0.5">
              {rawData?.evidence?.evidence?.evidence_collection_reason || 'Lambda function name could not be resolved. Logs and Metrics are unavailable. Use Raw Json tab to inspect full evidence.'}
            </p>
          </div>
        </div>
      )}

      {/* Demo synthetic data notice — shown when the collector generated illustrative data */}
      {rawData?.evidence?.evidence?.demo_synthetic && (
        <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-card flex items-start space-x-2">
          <Zap className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-xs text-blue-400 font-medium">Demo Synthetic Data</p>
            <p className="text-xs text-text-secondary mt-0.5">
              {rawData?.evidence?.evidence?.demo_synthetic_reason ||
                'This incident was injected by demo mode. The metrics and logs shown are illustrative synthetic data, not real CloudWatch telemetry.'}
            </p>
          </div>
        </div>
      )}

      
      {/* Tab Navigation */}
      <div className="flex space-x-1 mb-4 bg-bg-elevated rounded p-1 flex-wrap gap-1">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => onTabChange(tab)}
            className={`px-3 py-1 text-xs font-medium rounded capitalize transition-colors ${
              validTab === tab
                ? 'bg-bg-surface text-text-primary border border-border-default'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>
      
      {/* Tab Content */}
      <div className="bg-bg-input rounded-card p-4 min-h-48">
        <EvidenceTabContent tab={validTab} data={rawData} faultClass={faultClass} />
      </div>
    </div>
  )
}

function EvidenceTabContent({ tab, data, faultClass }) {
  const [logFilter, setLogFilter] = useState('')

  if (!data) {
    return (
      <div className="text-center py-8">
        <Eye className="mx-auto w-8 h-8 text-text-muted mb-2 opacity-50" />
        <p className="text-xs text-text-secondary">No evidence data collected yet</p>
      </div>
    )
  }

  // API response shape: data = { incident_id, fault_class, s3_key, evidence: { ..., evidence: { metrics, logs_insights, ... } } }
  // The outer data.evidence holds metadata; the inner data.evidence.evidence holds the actual telemetry.
  const outerEvidence = data.evidence || {}
  const evidence = outerEvidence.evidence || outerEvidence

  switch (tab) {
    case 'raw json':
      return (
        <pre className="text-xs text-text-code font-mono whitespace-pre-wrap overflow-auto max-h-96">
          {JSON.stringify(data, null, 2)}
        </pre>
      )

    case 'metrics': {
      // Backend collector writes evidence.metrics with keys: duration, errors, throttles, invocations
      const metricsObj = evidence.metrics || {}
      const metricNames = Object.keys(metricsObj).filter(k => Array.isArray(metricsObj[k]))
      if (metricNames.length === 0) {
        return <EvidenceEmpty message="No CloudWatch metrics data available for this incident" />
      }

      // Build time-series chart data
      // Each metric entry is [{timestamp, value}, ...]
      const allTimestamps = new Set()
      metricNames.forEach(name => {
        const pts = metricsObj[name]
        if (Array.isArray(pts)) pts.forEach(p => allTimestamps.add(p.timestamp || p.Timestamp))
      })

      const sortedTs = Array.from(allTimestamps).filter(Boolean).sort()
      const chartData = sortedTs.map(ts => {
        const row = { ts: new Date(ts).toLocaleTimeString() }
        metricNames.forEach(name => {
          const pts = metricsObj[name]
          if (Array.isArray(pts)) {
            const pt = pts.find(p => (p.timestamp || p.Timestamp) === ts)
            row[name] = pt ? (pt.value ?? pt.Average ?? pt.Sum ?? pt.Maximum ?? null) : null
          }
        })
        return row
      })

      if (chartData.length === 0) {
        return <EvidenceEmpty message="No CloudWatch metrics data available for this incident. This usually happens if the function received no traffic in the 15-minute window preceding the incident." />
      }

      const lineColors = [CHART_COLORS.primary, CHART_COLORS.amber, CHART_COLORS.emerald, CHART_COLORS.crimson]
      
      // Get thresholds from evidence bundle (written by collector from CloudWatch alarm definitions)
      // The collector writes alarm_thresholds as the full alarm definition object:
      // { threshold: 50000, metric_name: 'Duration', comparison_operator: 'GreaterThanThreshold', ... }
      // We need to extract the threshold value and map it to the metric name used in the chart.
      const rawAlarmThresholds = evidence.alarm_thresholds || {}
      const alarmThresholds = {}
      if (rawAlarmThresholds && typeof rawAlarmThresholds === 'object') {
        // If it's the full alarm object with a 'threshold' field, use that
        if (rawAlarmThresholds.threshold != null && rawAlarmThresholds.metric_name) {
          const metricKey = String(rawAlarmThresholds.metric_name).toLowerCase()
          alarmThresholds[metricKey] = Number(rawAlarmThresholds.threshold)
        } else {
          // Otherwise assume it's already a flat object { metric_name: threshold_value, ... }
          for (const [key, value] of Object.entries(rawAlarmThresholds)) {
            if (typeof value === 'number' || (typeof value === 'string' && !isNaN(Number(value)))) {
              alarmThresholds[String(key).toLowerCase()] = Number(value)
            }
          }
        }
      }
      // Also check component_alarm_thresholds for service_cascade
      const componentThresholds = evidence.component_alarm_thresholds || {}
      for (const [alarmName, alarmDef] of Object.entries(componentThresholds)) {
        if (alarmDef && typeof alarmDef === 'object' && alarmDef.threshold != null && alarmDef.metric_name) {
          const metricKey = String(alarmDef.metric_name).toLowerCase()
          alarmThresholds[metricKey] = Number(alarmDef.threshold)
        }
      }

      return (
        <div className="space-y-3">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} vertical={false} />
              <XAxis dataKey="ts" tick={{ fill: CHART_COLORS.muted, fontSize: 10, fontFamily: 'JetBrains Mono' }} />
              <YAxis tick={{ fill: CHART_COLORS.muted, fontSize: 10, fontFamily: 'JetBrains Mono' }} />
              <Tooltip
                contentStyle={{ backgroundColor: CHART_COLORS.tooltip, border: `1px solid ${CHART_COLORS.tooltipBorder}`, borderRadius: 6, fontSize: 11, fontFamily: 'JetBrains Mono', color: CHART_COLORS.primary }}
                cursor={{ stroke: CHART_COLORS.secondary, strokeDasharray: '3 3' }}
              />
              <Legend wrapperStyle={{ fontSize: 10, color: CHART_COLORS.secondary }} />
              {metricNames.map((name, i) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={lineColors[i % lineColors.length]}
                  strokeWidth={1.5}
                  dot={chartData.length === 1 ? { r: 4 } : false}
                  connectNulls
                />
              ))}
              {metricNames.map(name => alarmThresholds[name] != null && (
                <ReferenceLine
                  key={`threshold-${name}`}
                  y={alarmThresholds[name]}
                  stroke={CHART_COLORS.crimson}
                  strokeDasharray="4 4"
                  label={{ value: `${name} threshold`, fill: CHART_COLORS.crimson, fontSize: 10 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )
    }

    case 'logs': {
      const logData = evidence.logs_insights || evidence.log_data
      const rows = Array.isArray(logData?.rows) ? logData.rows
        : Array.isArray(logData) ? logData
        : typeof logData === 'string' ? logData.split('\n').filter(Boolean).map(l => ({ '@message': l }))
        : []

      if (rows.length === 0) {
        // For misconfiguration, logs are not collected from CloudWatch (no Lambda log group)
        // Show the config rule / resource context as a helpful message instead
        const configRule = evidence.config_rule
        const resourceId = evidence.resource_id
        if (faultClass === 'misconfiguration') {
          return (
            <div className="text-center py-8">
              <Eye className="mx-auto w-6 h-6 text-text-muted mb-2 opacity-50" />
              <p className="text-xs text-text-secondary mb-1">No CloudWatch logs for misconfiguration events</p>
              {configRule && (
                <p className="text-xs text-text-muted mono">
                  Config rule: {configRule}
                  {resourceId ? ` | Resource: ${resourceId}` : ''}
                </p>
              )}
              <p className="text-xs text-text-muted mt-2">Switch to the Config tab to view compliance evidence</p>
            </div>
          )
        }
        return <EvidenceEmpty message="No log data collected" />
      }

      const filtered = logFilter
        ? rows.filter(r => {
            const msg = r['@message'] || r.message || JSON.stringify(r)
            return msg.toUpperCase().includes(logFilter.toUpperCase())
          })
        : rows

      return (
        <div className="space-y-2">
          <div className="flex items-center space-x-2 mb-3">
            <input
              type="text"
              placeholder="Filter: ERROR, WARN..."
              value={logFilter}
              onChange={e => setLogFilter(e.target.value)}
              className="bg-bg-elevated border border-border-default rounded-button px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-border-strong w-40"
            />
            {logFilter && (
              <button onClick={() => setLogFilter('')} className="text-text-muted hover:text-text-secondary">
                <X className="w-3.5 h-3.5" />
              </button>
            )}
            <span className="text-xs text-text-muted">{filtered.length} rows</span>
          </div>
          <div className="max-h-72 overflow-y-auto space-y-1">
            {filtered.slice(0, 200).map((row, i) => {
              const msg = row['@message'] || row.message || JSON.stringify(row)
              const ts = row['@timestamp'] || row.timestamp || ''
              const isError = /error|exception|failed/i.test(msg)
              const isWarn = /warn/i.test(msg)
              return (
                <div key={i} className={`text-xs font-mono flex space-x-3 px-2 py-1 rounded ${
                  isError ? 'bg-crimson-surface/30' : isWarn ? 'bg-amber-surface/30' : ''
                }`}>
                  {ts && <span className="text-text-muted shrink-0">{new Date(ts).toLocaleTimeString()}</span>}
                  <span className={`${isError ? 'text-crimson' : isWarn ? 'text-amber' : 'text-text-code'} break-all`}>{msg}</span>
                </div>
              )
            })}
            {filtered.length > 200 && (
              <p className="text-xs text-text-muted text-center pt-2">Showing first 200 of {filtered.length} rows</p>
            )}
          </div>
        </div>
      )
    }

    case 'x-ray': {
      const summaries = evidence.xray_trace_summaries || []
      const graph = evidence.xray_service_graph || []

      if (summaries.length === 0 && graph.length === 0) {
        return <EvidenceEmpty message="No X-Ray trace data collected" />
      }

      return (
        <div className="space-y-4">
          {summaries.length > 0 && (
            <div>
              <p className="text-xs text-text-secondary uppercase tracking-wide mb-2">Trace Summaries</p>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {summaries.map((t, i) => (
                  <div key={i} className="p-2 bg-bg-elevated rounded text-xs font-mono">
                    <div className="flex items-center space-x-3">
                      <span className="text-text-muted">ID</span>
                      <span className="text-text-code truncate">{t.id || '—'}</span>
                      {t.duration != null && <span className="text-text-secondary">{t.duration}s</span>}
                      {t.has_fault && <span className="badge badge-critical">Fault</span>}
                      {t.has_error && <span className="badge badge-warning">Error</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {graph.length > 0 && (
            <div>
              <p className="text-xs text-text-secondary uppercase tracking-wide mb-2">Service Graph</p>
              <div className="space-y-1">
                {graph.map((svc, i) => (
                  <div key={i} className="text-xs font-mono text-text-code">
                    <span className="text-text-primary">{svc.name || '(unknown)'}</span>
                    {svc.type && <span className="text-text-muted ml-1">({svc.type})</span>}
                    {Array.isArray(svc.edges) && svc.edges.map((edge, j) => (
                      <div key={j} className="ml-4 text-text-secondary">
                        → ref #{edge.ReferenceId ?? edge.reference_id}
                        {edge.ResponseTimeHistogram && (
                          <span className="text-text-muted ml-2">({edge.ResponseTimeHistogram.length} samples)</span>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )
    }

    case 'config': {
      const compliance = evidence.config_compliance || {}
      const historyRaw = evidence.resource_config_history || {}
      // Collector stores history as { items: [...] } or directly as []
      const history = Array.isArray(historyRaw) ? historyRaw : (historyRaw.items || [])
      const results = compliance.results || []

      if (results.length === 0 && history.length === 0) {
        return <EvidenceEmpty message="No AWS Config compliance data collected. The Config rule evaluation may not have found non-compliant resources yet." />
      }

      return (
        <div className="space-y-4">
          {results.length > 0 && (
            <div>
              <p className="text-xs text-text-secondary uppercase tracking-wide mb-2">Compliance Results</p>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border-subtle text-text-muted">
                    <th className="py-1 text-left">Resource ID</th>
                    <th className="py-1 text-left">Compliance</th>
                    <th className="py-1 text-left">Annotation</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => {
                    // Collector stores flattened snake_case fields
                    const resourceId = r.resource_id ||
                      r.EvaluationResultIdentifier?.EvaluationResultQualifier?.ResourceId ||
                      '—'
                    const complianceType = r.compliance_type || r.ComplianceType || '—'
                    const annotation = r.annotation || r.Annotation || '—'
                    const isNonCompliant = complianceType === 'NON_COMPLIANT'
                    return (
                      <tr key={i} className="border-b border-border-subtle">
                        <td className="py-1 mono text-text-code">{resourceId}</td>
                        <td className="py-1">
                          <span className={`badge ${isNonCompliant ? 'badge-critical' : 'badge-success'}`}>
                            {complianceType}
                          </span>
                        </td>
                        <td className="py-1 text-text-secondary">{annotation}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          {history.length > 0 && (
            <details>
              <summary className="text-xs text-text-secondary cursor-pointer hover:text-text-primary">Config History ({history.length} items)</summary>
              <pre className="mt-2 text-xs text-text-code font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
                {JSON.stringify(history, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )
    }

    case 'guardduty': {
      const finding = evidence.guardduty_finding
      if (!finding) return <EvidenceEmpty message="No GuardDuty finding data" />
      return (
        <pre className="text-xs text-text-code font-mono whitespace-pre-wrap overflow-auto max-h-80">
          {JSON.stringify(finding, null, 2)}
        </pre>
      )
    }

    default:
      return null
  }
}

function EvidenceEmpty({ message }) {
  return (
    <div className="text-center py-8">
      <Eye className="mx-auto w-6 h-6 text-text-muted mb-2 opacity-50" />
      <p className="text-xs text-text-secondary">{message}</p>
    </div>
  )
}

function ApprovalCard({ incident, initialRemStatus, onApproved }) {
  const remediation = incident.remediation || {}
  const hasDiagnosis = Boolean(incident.diagnosis?.root_cause)
  const isPending = remediation.status === 'pending_approval'
  const isApproved = remediation.status === 'approved' || remediation.status === 'executed'
  const isRejected = remediation.status === 'rejected'
  const isFailed = remediation.status === 'failed'

  const suggestedAction = incident.diagnosis?.suggested_action
  const riskInfo = ACTION_RISK[suggestedAction] || { level: 'Unknown', className: 'badge-info' }
  const isHighRisk = HIGH_RISK_ACTIONS.has(suggestedAction)

  const [checklist, setChecklist] = useState([false, false, false])
  const [showReject, setShowReject] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [showConfirm, setShowConfirm] = useState(false)

  // Stale state detection
  const stateChanged = initialRemStatus !== null && initialRemStatus !== remediation.status && isPending === false

  const allChecked = checklist.every(Boolean)

  const toggleCheck = (i) => setChecklist(prev => prev.map((v, idx) => idx === i ? !v : v))

  const handleApprove = async () => {
    if (isHighRisk) {
      setShowConfirm(true)
      return
    }
    await submitApprove()
  }

  const submitApprove = async () => {
    setShowConfirm(false)
    setSubmitting(true)
    setActionError(null)
    try {
      await apiClient.approveIncidentMain(incident.incident_id)
      onApproved()
    } catch (err) {
      setActionError(err.message || 'Approval failed')
    } finally {
      setSubmitting(false)
    }
  }

  const handleReject = async () => {
    setSubmitting(true)
    setActionError(null)
    try {
      await apiClient.rejectIncidentMain(incident.incident_id, rejectReason)
      onApproved()
    } catch (err) {
      setActionError(err.message || 'Rejection failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-4">Approval</h3>
      
      {!hasDiagnosis ? (
        <div className="text-center py-6">
          <Clock className="mx-auto w-6 h-6 text-text-muted mb-2 opacity-50" />
          <p className="text-xs text-text-secondary">Waiting for diagnosis</p>
        </div>
      ) : stateChanged ? (
        <div className="p-3 bg-amber-surface border border-amber/30 rounded-card">
          <p className="text-xs text-amber font-medium">State has changed — refresh before acting.</p>
        </div>
      ) : isPending ? (
        <div className="space-y-4">
          {/* Incident ID + status */}
          <div className="p-2.5 bg-amber-surface border border-amber/20 rounded-card">
            <p className="text-xs text-amber font-medium">Awaiting manual approval</p>
            <p className="text-xs text-text-muted mono mt-0.5">{incident.incident_id?.substring(0, 8)}</p>
          </div>

          {/* Proposed action */}
          <div>
            <label className="text-xs text-text-secondary uppercase tracking-wide">Proposed Action</label>
            <p className="text-xs text-text-primary mt-1">
              {ACTION_LABELS[suggestedAction] || suggestedAction?.replace(/_/g, ' ') || '—'}
            </p>
          </div>

          {/* Target resources */}
          {incident.diagnosis?.affected_resources?.length > 0 && (
            <div>
              <label className="text-xs text-text-secondary uppercase tracking-wide">Target Resources</label>
              <div className="mt-1 space-y-0.5">
                {incident.diagnosis.affected_resources.map((r, i) => (
                  <p key={i} className="text-xs mono text-text-code">{r}</p>
                ))}
              </div>
            </div>
          )}

          {/* Risk level */}
          <div className="flex items-center space-x-2">
            <label className="text-xs text-text-secondary uppercase tracking-wide">Risk</label>
            <span className={`badge ${riskInfo.className}`}>{riskInfo.level}</span>
          </div>

          {/* Pre-flight checklist */}
          <div className="space-y-2">
            {[
              'I have reviewed the AI diagnosis and confidence score.',
              'I have reviewed the supporting evidence.',
              'I confirm the target resource and environment.',
            ].map((item, i) => (
              <label key={i} className="flex items-start space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={checklist[i]}
                  onChange={() => toggleCheck(i)}
                  className="mt-0.5 flex-shrink-0 accent-emerald"
                />
                <span className="text-xs text-text-secondary">{item}</span>
              </label>
            ))}
          </div>

          {actionError && (
            <p className="text-xs text-crimson">{actionError}</p>
          )}

          {/* Confirm dialog for high-risk actions */}
          {showConfirm && (
            <div className="p-3 bg-crimson-surface border border-crimson/30 rounded-card space-y-3">
              <div className="flex items-start space-x-2">
                <Shield className="w-4 h-4 text-crimson flex-shrink-0 mt-0.5" />
                <p className="text-xs text-crimson font-medium">
                  This is a High-Risk action: {ACTION_LABELS[suggestedAction]}. Confirm?
                </p>
              </div>
              <div className="flex space-x-2">
                <button onClick={submitApprove} disabled={submitting} className="btn-danger text-xs px-3 py-1 h-auto">
                  {submitting ? 'Submitting...' : 'Confirm Approve'}
                </button>
                <button onClick={() => setShowConfirm(false)} className="btn-ghost text-xs px-3 py-1 h-auto">Cancel</button>
              </div>
            </div>
          )}

          {!showConfirm && (
            <div className="space-y-2">
              <button
                className="btn-danger w-full"
                disabled={!allChecked || submitting}
                onClick={handleApprove}
                title={!allChecked ? 'Complete all checklist items first' : undefined}
              >
                {submitting ? 'Submitting...' : 'Approve Remediation'}
              </button>

              {!showReject ? (
                <button
                  className="btn-ghost w-full"
                  onClick={() => setShowReject(true)}
                >
                  Reject
                </button>
              ) : (
                <div className="space-y-2">
                  <textarea
                    value={rejectReason}
                    onChange={e => setRejectReason(e.target.value)}
                    placeholder="Reason for rejection..."
                    rows={2}
                    className="w-full bg-bg-input border border-border-default rounded text-xs text-text-primary p-2 focus:outline-none focus:border-border-strong resize-none"
                  />
                  <div className="flex space-x-2">
                    <button
                      onClick={handleReject}
                      disabled={submitting}
                      className="btn-ghost text-xs px-3 py-1 h-auto flex-1"
                    >
                      {submitting ? 'Rejecting...' : 'Confirm Reject'}
                    </button>
                    <button
                      onClick={() => { setShowReject(false); setRejectReason('') }}
                      className="btn-ghost text-xs px-2 py-1 h-auto"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ) : isApproved ? (
        <div className="text-center py-6">
          <div className="w-8 h-8 rounded-full mx-auto mb-2 flex items-center justify-center bg-emerald-surface">
            <CheckCircle className="w-4 h-4 text-emerald" />
          </div>
          <p className="text-xs text-text-secondary font-medium">
            {remediation.status === 'executed' ? 'Approved and executing' : 'Approved'}
          </p>
          {remediation.executed_at && (
            <p className="text-xs text-text-muted mono mt-1">{formatDate(remediation.executed_at, 'relative')}</p>
          )}
          {remediation.action_taken && (
            <p className="text-xs text-text-muted mt-1">{remediation.action_taken.replace(/_/g, ' ')}</p>
          )}
        </div>
      ) : isRejected ? (
        <div className="text-center py-6">
          <div className="w-8 h-8 rounded-full mx-auto mb-2 flex items-center justify-center bg-bg-elevated">
            <X className="w-4 h-4 text-text-muted" />
          </div>
          <p className="text-xs text-text-secondary font-medium">Rejected</p>
        </div>
      ) : isFailed ? (
        <div className="p-3 bg-crimson-surface border border-crimson/20 rounded-card">
          <p className="text-xs text-crimson font-medium">Remediation failed</p>
        </div>
      ) : (
        <div className="text-center py-6">
          <p className="text-xs text-text-secondary">Not required</p>
        </div>
      )}
    </div>
  )
}

function VerificationCard({ incident }) {
  const verification = incident.verification || {}
  const remediation = incident.remediation || {}
  const isExecuted = remediation.status === 'executed'
  
  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-4">Verification</h3>
      
      {verification.status === 'resolved' ? (
        <div className="space-y-3">
          <div className="p-3 bg-emerald-surface rounded-card border border-emerald/20">
            <p className="text-xs text-emerald font-medium">
              Signal resolved — incident closed
            </p>
          </div>
          {verification.checked_at && (
            <p className="text-xs text-text-muted mono">
              Verified {formatDate(verification.checked_at, 'relative')}
            </p>
          )}
          {verification.signal_rechecked && (
            <p className="text-xs text-text-secondary">{verification.signal_rechecked}</p>
          )}
          {verification.notes && (
            <p className="text-xs text-text-secondary leading-relaxed">{verification.notes}</p>
          )}
        </div>
      ) : verification.status === 'not_resolved' ? (
        <div className="space-y-3">
          <div className="p-3 bg-crimson-surface rounded-card border border-crimson/20">
            <p className="text-xs text-crimson font-medium">
              Signal still firing — remediation did not resolve the incident
            </p>
          </div>
          {verification.signal_rechecked && (
            <p className="text-xs text-text-secondary">{verification.signal_rechecked}</p>
          )}
          {verification.notes && (
            <p className="text-xs text-text-secondary leading-relaxed">{verification.notes}</p>
          )}
        </div>
      ) : verification.status === 'inconclusive' ? (
        <div className="space-y-3">
          <div className="p-3 bg-amber-surface rounded-card border border-amber/20">
            <p className="text-xs text-amber font-medium">
              Inconclusive — check manually
            </p>
          </div>
          {verification.notes && (
            <p className="text-xs text-text-secondary leading-relaxed">{verification.notes}</p>
          )}
        </div>
      ) : (
        <div className="text-center py-6">
          <Clock className="mx-auto w-6 h-6 text-text-muted mb-2 opacity-50" />
          <p className="text-xs text-text-secondary">
            {isExecuted ? 'Verification running...' : 'Verification will run automatically after remediation'}
          </p>
        </div>
      )}
    </div>
  )
}

function getStageIconStyle(status) {
  switch (status) {
    case 'complete':
      return 'bg-emerald text-white'
    case 'in_progress':
      return 'bg-amber text-white animate-pulse'
    case 'failed':
      return 'bg-crimson text-white'
    default:
      return 'border-2 border-dashed border-border-subtle bg-bg-base'
  }
}

function getStageIcon(status) {
  switch (status) {
    case 'complete':
      return <CheckCircle className="w-3 h-3" />
    case 'in_progress':
      return <div className="w-2 h-2 bg-white rounded-full" />
    case 'failed':
      return <X className="w-3 h-3" />
    default:
      return <div className="w-2 h-2 border border-text-muted rounded-full" />
  }
}

function getStageTimestamp(incident, stage) {
  switch (stage) {
    case 'detected':
      return incident.detected_at ? formatDate(incident.detected_at) : ''
    case 'diagnosed':
      return incident.diagnosis?.root_cause ? 'Completed' : ''
    case 'pending_approval':
    case 'executed':
      return incident.remediation?.executed_at ? formatDate(incident.remediation.executed_at) : ''
    case 'verified':
      return incident.verification?.checked_at ? formatDate(incident.verification.checked_at) : ''
    default:
      return ''
  }
}

function getStageDetails(incident, stage) {
  switch (stage) {
    case 'diagnosed':
      return incident.diagnosis?.root_cause
    case 'executed':
      return incident.remediation?.action_taken
    case 'verified':
      return incident.verification?.notes
    default:
      return false
  }
}

function StageDetails({ incident, stage }) {
  switch (stage) {
    case 'diagnosed':
      return (
        <div className="text-xs">
          <p className="text-text-secondary">Root Cause</p>
          <p className="text-text-primary">{incident.diagnosis?.root_cause}</p>
          {incident.diagnosis?.confidence != null && (
            <p className="text-text-muted mt-1">
              Confidence: {Math.round(incident.diagnosis.confidence * 100)}%
            </p>
          )}
        </div>
      )
    case 'executed':
      return (
        <div className="text-xs">
          <p className="text-text-secondary">Action</p>
          <p className="text-text-primary mono">{incident.remediation?.action_taken}</p>
        </div>
      )
    case 'verified':
      return (
        <div className="text-xs">
          <p className="text-text-secondary">Notes</p>
          <p className="text-text-primary">{incident.verification?.notes}</p>
        </div>
      )
    default:
      return null
  }
}

function IncidentDetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="pulse-loading h-8 w-32 rounded-button"></div>
          <div className="pulse-loading h-8 w-8 rounded-button"></div>
        </div>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="pulse-loading h-6 w-20 rounded-badge"></div>
            <div>
              <div className="pulse-loading h-6 w-64 mb-2"></div>
              <div className="pulse-loading h-4 w-96"></div>
            </div>
          </div>
          <div className="pulse-loading h-6 w-24 rounded-badge"></div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-3">
          <div className="card">
            <div className="pulse-loading h-4 w-32 mb-6"></div>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex space-x-3 mb-4">
                <div className="pulse-loading w-5 h-5 rounded-full"></div>
                <div className="flex-1">
                  <div className="pulse-loading h-4 w-20 mb-1"></div>
                  <div className="pulse-loading h-3 w-16"></div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        <div className="lg:col-span-6 space-y-6">
          <div className="card">
            <div className="pulse-loading h-4 w-24 mb-6"></div>
            <div className="space-y-4">
              <div className="pulse-loading h-20 w-full"></div>
              <div className="pulse-loading h-16 w-full"></div>
            </div>
          </div>
          
          <div className="card">
            <div className="pulse-loading h-4 w-32 mb-4"></div>
            <div className="pulse-loading h-40 w-full"></div>
          </div>
        </div>
        
        <div className="lg:col-span-3 space-y-6">
          <div className="card">
            <div className="pulse-loading h-4 w-20 mb-4"></div>
            <div className="pulse-loading h-24 w-full"></div>
          </div>
          
          <div className="card">
            <div className="pulse-loading h-4 w-24 mb-4"></div>
            <div className="pulse-loading h-20 w-full"></div>
          </div>
        </div>
      </div>
    </div>
  )
}