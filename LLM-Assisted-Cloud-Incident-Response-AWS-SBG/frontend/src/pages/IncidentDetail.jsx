import { useState, useEffect } from 'react'
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
  AlertCircle
} from 'lucide-react'
import { apiClient } from '../config/api'
import { POLLING_INTERVALS, PIPELINE_STAGES, getConfidenceLevel } from '../utils/constants'
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

  const fetchIncidentDetail = async () => {
    try {
      const data = await apiClient.getIncidentDetail(incidentId)
      setIncident(data.incident)
      setRawData(data.raw_data)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch incident detail:', err)
      setError('Failed to load incident details')
    } finally {
      setLoading(false)
    }
  }

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

        {/* Center Column - AI Diagnosis & Evidence (50%) */}
        <div className="lg:col-span-6 space-y-6">
          <DiagnosisPanel 
            incident={incident} 
            onRetrigger={handleRetriggerDiagnosis}
            retriggering={retriggering}
            retriggerMessage={retriggerMessage}
          />
          <EvidenceExplorer 
            rawData={rawData}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
        </div>

        {/* Right Column - Approval & Verification (25%) */}
        <div className="lg:col-span-3 space-y-6">
          <ApprovalCard incident={incident} />
          <VerificationCard incident={incident} />
        </div>
      </div>
    </div>
  )
}

function IncidentHeader({ incident, status, severity, onBack, onRefresh }) {
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <button onClick={onBack} className="btn-ghost">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Overview
        </button>
        <button onClick={onRefresh} className="btn-ghost">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-4">
          <span className={`badge ${severity === 'critical' ? 'badge-critical' : 'badge-warning'}`}>
            {severity === 'critical' ? 'Critical' : 'Warning'}
          </span>
          <div>
            <h1 className="text-xl font-semibold text-text-primary">
              {incident.diagnosis?.root_cause || 'Investigating Incident'}
            </h1>
            <div className="flex flex-wrap items-center space-x-3 mt-1 text-xs text-text-secondary">
              <span className="mono text-text-primary">{incident.incident_id?.substring(0, 8)}</span>
              <span>•</span>
              <span>Detected {formatDate(incident.detected_at, 'relative')}</span>
              <span>•</span>
              <span className="capitalize">{incident.fault_class?.replace(/_/g, ' ')}</span>
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
  
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-text-primary">AI Diagnosis</h3>
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
          <div>
            <label className="text-xs text-text-secondary uppercase tracking-wide">Root Cause</label>
            <p className="text-sm text-text-primary mt-1">{diagnosis.root_cause}</p>
          </div>
          
          <div className="flex items-center justify-between">
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
              <label className="text-xs text-text-secondary uppercase tracking-wide">Used RAG</label>
              <div className="text-sm text-text-primary mt-1">
                {diagnosis.used_rag ? 'Yes' : 'No'}
              </div>
            </div>
          </div>
          
          {diagnosis.suggested_action && (
            <div>
              <label className="text-xs text-text-secondary uppercase tracking-wide">Suggested Action</label>
              <p className="text-xs text-text-primary mt-1 mono bg-bg-input p-2 rounded">
                {diagnosis.suggested_action.replace(/_/g, ' ')}
              </p>
            </div>
          )}
          
          {diagnosis.reasoning_trace && (
            <div>
              <label className="text-xs text-text-secondary uppercase tracking-wide">Reasoning Trace</label>
              <div className="mt-2 p-3 bg-bg-input rounded-card max-h-48 overflow-y-auto">
                <pre className="text-xs text-text-code font-mono whitespace-pre-wrap">
                  {diagnosis.reasoning_trace}
                </pre>
              </div>
            </div>
          )}
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

function EvidenceExplorer({ rawData, activeTab, onTabChange }) {
  const tabs = ['metrics', 'logs', 'xray', 'raw json']
  
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-text-primary">Evidence Explorer</h3>
      </div>
      
      {/* Tab Navigation */}
      <div className="flex space-x-1 mb-4 bg-bg-elevated rounded p-1">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => onTabChange(tab)}
            className={`px-3 py-1 text-xs font-medium rounded capitalize transition-colors ${
              activeTab === tab
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
        <EvidenceTabContent tab={activeTab} data={rawData} />
      </div>
    </div>
  )
}

function EvidenceTabContent({ tab, data }) {
  if (!data) {
    return (
      <div className="text-center py-8">
        <Eye className="mx-auto w-8 h-8 text-text-muted mb-2 opacity-50" />
        <p className="text-xs text-text-secondary">No evidence data collected yet</p>
      </div>
    )
  }

  const evidence = data.evidence || {}

  switch (tab) {
    case 'raw json':
      return (
        <pre className="text-xs text-text-code font-mono whitespace-pre-wrap overflow-auto max-h-80">
          {JSON.stringify(data, null, 2)}
        </pre>
      )
    case 'metrics':
      const metrics = evidence.cloudwatch_metrics || data.cloudwatch_metrics
      return metrics && Object.keys(metrics).length > 0 ? (
        <pre className="text-xs text-text-code font-mono whitespace-pre-wrap overflow-auto max-h-80">
          {JSON.stringify(metrics, null, 2)}
        </pre>
      ) : (
        <div className="text-center py-8">
          <Eye className="mx-auto w-6 h-6 text-text-muted mb-2 opacity-50" />
          <p className="text-xs text-text-secondary">No metrics data available for this incident</p>
        </div>
      )
    case 'logs':
      const logs = evidence.log_data || data.log_data
      return logs && (Array.isArray(logs) ? logs.length > 0 : Object.keys(logs).length > 0) ? (
        <pre className="text-xs text-text-code font-mono whitespace-pre-wrap overflow-auto max-h-80">
          {typeof logs === 'string' ? logs : JSON.stringify(logs, null, 2)}
        </pre>
      ) : (
        <div className="text-center py-8">
          <Eye className="mx-auto w-6 h-6 text-text-muted mb-2 opacity-50" />
          <p className="text-xs text-text-secondary">No log data collected</p>
        </div>
      )
    case 'xray':
      const xray = evidence.xray_traces || data.xray_traces
      return xray && (Array.isArray(xray) ? xray.length > 0 : Object.keys(xray).length > 0) ? (
        <pre className="text-xs text-text-code font-mono whitespace-pre-wrap overflow-auto max-h-80">
          {JSON.stringify(xray, null, 2)}
        </pre>
      ) : (
        <div className="text-center py-8">
          <Eye className="mx-auto w-6 h-6 text-text-muted mb-2 opacity-50" />
          <p className="text-xs text-text-secondary">No X-Ray trace data collected</p>
        </div>
      )
    default:
      return null
  }
}

function ApprovalCard({ incident }) {
  const remediation = incident.remediation || {}
  const hasDiagnosis = Boolean(incident.diagnosis?.root_cause)
  const isPending = remediation.status === 'pending_approval'
  const isApproved = remediation.status === 'approved' || remediation.status === 'executed'
  const isRejected = remediation.status === 'rejected'
  
  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-4">Approval</h3>
      
      {!hasDiagnosis ? (
        <div className="text-center py-6">
          <Clock className="mx-auto w-6 h-6 text-text-muted mb-2 opacity-50" />
          <p className="text-xs text-text-secondary">Waiting for diagnosis</p>
        </div>
      ) : isPending ? (
        <div className="space-y-4">
          <div className="p-3 bg-amber-surface rounded-card border border-amber/20">
            <p className="text-xs text-amber font-medium">Awaiting manual approval</p>
          </div>
          
          <div className="space-y-2">
            <button
              className="btn-danger w-full"
              title="Opens Phase 5 approval endpoint in a new tab"
              onClick={() => {
                const url = `https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod/approval?incident_id=${encodeURIComponent(incident.incident_id)}&action=approve`
                window.open(url, '_blank', 'noopener,noreferrer')
              }}
            >
              Approve Remediation
            </button>
            <button
              className="btn-ghost w-full"
              title="Opens Phase 5 rejection endpoint in a new tab"
              onClick={() => {
                const url = `https://0jqdaxn8k1.execute-api.ap-south-1.amazonaws.com/Prod/approval?incident_id=${encodeURIComponent(incident.incident_id)}&action=reject`
                window.open(url, '_blank', 'noopener,noreferrer')
              }}
            >
              Reject
            </button>
          </div>
          <p className="text-xs text-text-muted text-center mt-2">
            Approval is processed by the Phase 5 endpoint. This dashboard is read-only.
          </p>
        </div>
      ) : isApproved ? (
        <div className="text-center py-6">
          <div className="w-8 h-8 rounded-full mx-auto mb-2 flex items-center justify-center bg-emerald-surface">
            <CheckCircle className="w-4 h-4 text-emerald" />
          </div>
          <p className="text-xs text-text-secondary font-medium">
            {remediation.status === 'executed' ? 'Approved & Executed' : 'Approved'}
          </p>
        </div>
      ) : isRejected ? (
        <div className="text-center py-6">
          <div className="w-8 h-8 rounded-full mx-auto mb-2 flex items-center justify-center bg-bg-elevated">
            <Clock className="w-4 h-4 text-text-muted" />
          </div>
          <p className="text-xs text-text-secondary">Rejected</p>
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
          {verification.notes && (
            <p className="text-xs text-text-secondary">{verification.notes}</p>
          )}
        </div>
      ) : verification.status === 'not_resolved' ? (
        <div className="space-y-3">
          <div className="p-3 bg-crimson-surface rounded-card border border-crimson/20">
            <p className="text-xs text-crimson font-medium">
              Signal still firing — remediation did not resolve the incident
            </p>
          </div>
          {verification.notes && (
            <p className="text-xs text-text-secondary">{verification.notes}</p>
          )}
        </div>
      ) : verification.status === 'inconclusive' ? (
        <div className="space-y-3">
          <div className="p-3 bg-amber-surface rounded-card border border-amber/20">
            <p className="text-xs text-amber font-medium">
              Inconclusive — check manually
            </p>
          </div>
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
      return <div className="w-2 h-2 bg-white" />
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
          <p className="text-text-secondary">Root Cause:</p>
          <p className="text-text-primary">{incident.diagnosis?.root_cause}</p>
        </div>
      )
    case 'executed':
      return (
        <div className="text-xs">
          <p className="text-text-secondary">Action:</p>
          <p className="text-text-primary mono">{incident.remediation?.action_taken}</p>
        </div>
      )
    case 'verified':
      return (
        <div className="text-xs">
          <p className="text-text-secondary">Notes:</p>
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