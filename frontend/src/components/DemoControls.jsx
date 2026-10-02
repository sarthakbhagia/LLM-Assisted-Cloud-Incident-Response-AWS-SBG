import { useState, useEffect, useCallback } from 'react'
import { AlertCircle, Server, Database, Share2, Loader2, CheckCircle, XCircle, Info, Shield } from 'lucide-react'
import { apiClient } from '../config/api'
import { 
  FAULT_CLASSES, 
  FAULT_CLASS_LABELS, 
  FAULT_CLASS_DESCRIPTIONS, 
  FAULT_CLASS_SEVERITY, 
  FAULT_CLASS_ICONS,
  DEMO_ACTION_LABELS,
  PIPELINE_STAGE_DETAILS,
  PIPELINE_STAGES,
} from '../utils/constants'

export default function DemoControls() {
  const [activeIncident, setActiveIncident] = useState(null)
  const [incidentStatus, setIncidentStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showTracker, setShowTracker] = useState(false)
  const [pendingApproval, setPendingApproval] = useState(false)

  // Poll for active incident status
  useEffect(() => {
    const pollStatus = async () => {
      try {
        const data = await apiClient.getIncidents({ limit: 1, sort: 'detected_at', order: 'desc' })
        const incidents = data?.items || []
        if (incidents.length > 0) {
          const latest = incidents[0]
          const remediationStatus = latest.remediation?.status
          const verificationStatus = latest.verification?.status
          
          // Determine if there's an active demo
          const isActive = remediationStatus && !['resolved', 'rejected'].includes(remediationStatus) &&
                          verificationStatus !== 'resolved'
          
          if (isActive && (!activeIncident || activeIncident.incident_id !== latest.incident_id)) {
            setActiveIncident(latest)
            setShowTracker(true)
          } else if (!isActive && activeIncident) {
            setActiveIncident(null)
            setShowTracker(false)
          }
          
          if (activeIncident && activeIncident.incident_id === latest.incident_id) {
            setIncidentStatus(latest)
          }
          
          // Check if approval is needed
          if (remediationStatus === 'pending_approval' && !pendingApproval) {
            setPendingApproval(true)
          } else if (remediationStatus !== 'pending_approval') {
            setPendingApproval(false)
          }
        }
      } catch (err) {
        console.error('Failed to poll incident status:', err)
      }
    }
    
    pollStatus()
    const interval = setInterval(pollStatus, 5000)
    return () => clearInterval(interval)
  }, [activeIncident, pendingApproval])

  const handleInjectFault = async (faultClass) => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.injectFault(faultClass)
      setActiveIncident({ fault_class: faultClass, ...response.data })
      setShowTracker(true)
    } catch (err) {
      setError(err.message || 'Failed to inject fault')
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!activeIncident?.incident_id) return
    setLoading(true)
    try {
      await apiClient.approveIncidentMain(activeIncident.incident_id)
      setPendingApproval(false)
    } catch (err) {
      setError(err.message || 'Failed to approve')
    } finally {
      setLoading(false)
    }
  }

  const getCurrentStageIndex = () => {
    if (!incidentStatus) return 0
    const remediationStatus = incidentStatus.remediation?.status
    const verificationStatus = incidentStatus.verification?.status
    
    if (verificationStatus === 'resolved') return 6
    if (verificationStatus === 'not_resolved' || verificationStatus === 'inconclusive') return 6
    if (verificationStatus && verificationStatus !== 'not_run') return 5
    if (remediationStatus === 'executed') return 5
    if (remediationStatus === 'approved') return 4
    if (remediationStatus === 'pending_approval') return 3
    if (incidentStatus.diagnosis?.root_cause) return 2
    return 0
  }

  const currentStageIndex = getCurrentStageIndex()

  return (
    <div className="space-y-6">
      {/* Safety Banner */}
      <div className="card bg-amber/5 border-amber/20 p-4">
        <div className="flex items-center space-x-3">
          <Shield className="w-5 h-5 text-amber flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber">Live AWS Demo</p>
            <p className="text-xs text-text-secondary">
              These buttons trigger real, sandboxed infrastructure changes that this system then detects and fixes itself.
            </p>
          </div>
        </div>
      </div>

      {/* Demo Controls */}
      <div className="card p-6">
        <h2 className="text-lg font-semibold text-text-primary mb-2">Trigger a Fault</h2>
        <p className="text-sm text-text-secondary mb-6">
          Choose a scenario below. Each button triggers a real AWS fault injection that the pipeline will detect, diagnose, and (with your approval) fix.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {Object.entries(FAULT_CLASSES).map(([key, faultClass]) => {
            const Icon = FAULT_CLASS_ICONS[faultClass] ? null : (key === 'resource_exhaustion' ? Server : key === 'misconfiguration' ? Database : Share2)
            const severity = FAULT_CLASS_SEVERITY[faultClass] || { label: 'Unknown', className: 'badge-info' }
            const description = FAULT_CLASS_DESCRIPTIONS[faultClass] || ''
            const actionLabel = DEMO_ACTION_LABELS[faultClass] || 'Inject'
            const isDisabled = loading || activeIncident
            
            // Determine color from severity
            const colorClass = severity.className.replace('badge-', 'text-')
            const bgColorClass = severity.className.replace('badge-', 'bg-').replace('critical', 'crimson/10').replace('warning', 'amber/10').replace('info', 'emerald/10')
            const borderColorClass = severity.className.replace('badge-', 'border-').replace('critical', 'crimson/20').replace('warning', 'amber/20').replace('info', 'emerald/20')
            
            return (
              <div
                key={faultClass}
                onClick={() => !isDisabled && handleInjectFault(faultClass)}
                className={`card p-5 relative ${bgColorClass} ${borderColorClass} ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-border-strong hover:bg-opacity-20 cursor-pointer'} transition-all group`}
              >
                <div className="flex items-center space-x-3 mb-3">
                  {Icon && (
                    <div className={`p-3 rounded-lg ${colorClass} bg-opacity-10`}>
                      <Icon className="w-6 h-6" />
                    </div>
                  )}
                  {FAULT_CLASS_ICONS[faultClass] && (
                    <div className="p-3 rounded-lg bg-bg-elevated">
                      <span className="text-2xl" role="img" aria-label={FAULT_CLASS_LABELS[faultClass]}>{FAULT_CLASS_ICONS[faultClass]}</span>
                    </div>
                  )}
                </div>
                <h3 className="text-base font-semibold text-text-primary mb-1">{FAULT_CLASS_LABELS[faultClass]}</h3>
                <p className="text-xs text-text-secondary mb-4 flex-1">{description}</p>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    if (!isDisabled) handleInjectFault(faultClass)
                  }}
                  disabled={isDisabled}
                  className="w-full btn-primary text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading && activeIncident?.fault_class === faultClass ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      Injecting...
                    </>
                  ) : (
                    actionLabel
                  )}
                </button>
                {isDisabled && activeIncident && (
                  <div className="absolute bottom-3 left-3 right-3 text-xs text-text-muted text-center">
                    A demo is already running — see tracker below
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-3 bg-crimson/10 border border-crimson/20 rounded-card text-crimson text-sm">
            {error}
          </div>
        )}
      </div>

      {/* Pipeline Tracker - always visible when demo is active */}
      {showTracker && activeIncident && (
        <PipelineTracker
          incident={incidentStatus || activeIncident}
          currentStage={currentStageIndex}
          stages={PIPELINE_STAGES}
          onApprove={pendingApproval ? handleApprove : null}
          isApproving={loading && pendingApproval}
        />
      )}
    </div>
  )
}

function PipelineTracker({ incident, currentStage, stages, onApprove, isApproving }) {
  const faultClassLabel = FAULT_CLASS_LABELS[incident.fault_class] || incident.fault_class
  // Use shared pipeline stage details from constants
  const stageDetails = PIPELINE_STAGE_DETAILS

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-crimson/10 rounded-lg">
            <AlertCircle className="w-5 h-5 text-crimson" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-text-primary">Pipeline Tracker</h3>
            <p className="text-xs text-text-secondary">{faultClassLabel} • {incident.incident_id?.substring(0, 8)}</p>
          </div>
        </div>
        {incident.remediation?.status === 'pending_approval' && onApprove && (
          <button onClick={onApprove} className="btn-primary text-sm flex items-center space-x-2">
            {isApproving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
            <span>Approve Fix</span>
          </button>
        )}
      </div>

      {/* Horizontal Stepper */}
      <div className="overflow-x-auto">
        <div className="flex items-start min-w-max" style={{ minWidth: stageDetails.length * 180 }}>
          {stageDetails.map((stage, index) => {
            const isComplete = index < currentStage
            const isCurrent = index === currentStage
            const isFuture = index > currentStage

            return (
              <div key={stage.key} className="flex flex-col items-center flex-shrink-0" style={{ minWidth: 180 }}>
                {/* Vertical connector */}
                <div className="flex flex-col items-center">
                  {/* Step Circle */}
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center mx-auto transition-all duration-300 ${
                    isComplete ? 'bg-emerald text-white' :
                    isCurrent ? 'bg-amber text-white animate-pulse' :
                    'bg-bg-base border-2 border-dashed border-border-subtle'
                  }`}>
                    {isComplete ? (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
                    ) : isCurrent ? (
                      <div className="w-3 h-3 bg-white rounded-full animate-pulse" />
                    ) : (
                      <span className="text-xs text-text-muted font-mono">{index + 1}</span>
                    )}
                  </div>
                  
                  {/* Connector line */}
                  {index < stageDetails.length - 1 && (
                    <div className={`w-px h-16 mt-2 ${
                      isComplete || isCurrent ? 'bg-emerald' : 'bg-border-subtle'
                    }`} />
                  )}
                </div>

                {/* Stage Label & Caption */}
                <div className="mt-3 text-center px-2">
                  <div className={`text-sm font-medium ${isCurrent ? 'text-text-primary' : isComplete ? 'text-emerald' : 'text-text-muted'}`}>
                    {stage.label}
                  </div>
                  <p className="text-[11px] text-text-muted mt-1 leading-tight">
                    {stage.caption}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Current Stage Detail */}
      {currentStage < stageDetails.length && (
        <div className="mt-6 p-4 bg-bg-elevated rounded-card border border-border-subtle">
          <h4 className="text-sm font-medium text-text-primary mb-2">
            Current Stage: {stageDetails[currentStage].label}
          </h4>
          <p className="text-sm text-text-secondary">{stageDetails[currentStage].caption}</p>
          
          {currentStage === 3 && (
            <div className="mt-4 p-3 bg-amber/10 border border-amber/20 rounded-card">
              <p className="text-xs text-amber font-medium">Action Required: Human approval needed to proceed with remediation.</p>
            </div>
          )}
          
          {currentStage === 5 && (
            <div className="mt-4 p-3 bg-emerald/10 border border-emerald/20 rounded-card">
              <p className="text-xs text-emerald font-medium">Verifying the fix worked by re-checking the original alarm signal.</p>
            </div>
          )}
          
          {currentStage === 6 && (
            <div className="mt-4 p-3 bg-emerald/10 border border-emerald/20 rounded-card">
              <p className="text-xs text-emerald font-medium">Incident resolved — the signal is back to normal.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}