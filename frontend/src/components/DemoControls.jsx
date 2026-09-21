import { useState, useEffect, useCallback, Fragment } from 'react'
import { AlertCircle, Server, Database, Share2, Loader2, CheckCircle, XCircle, Info, Shield } from 'lucide-react'
import { apiClient } from '../config/api'

// Plain-language fault class configurations
const FAULT_CLASSES = [
  {
    id: 'resource_exhaustion',
    label: 'Overload a Server',
    description: 'We\'ll spike CPU on one of our demo services until it trips an alarm.',
    icon: Server,
    color: 'text-crimson',
    bgColor: 'bg-crimson/10 border-crimson/20',
    actionLabel: 'Break it',
  },
  {
    id: 'misconfiguration',
    label: 'Leave a Storage Bucket Open to the Internet',
    description: 'We\'ll remove the public access block on a demo S3 bucket to simulate a misconfiguration.',
    icon: Database,
    color: 'text-amber',
    bgColor: 'bg-amber/10 border-amber/20',
    actionLabel: 'Expose it',
  },
  {
    id: 'service_cascade',
    label: 'Crash a Service and Watch it Break its Neighbors',
    description: 'We\'ll kill a downstream service to trigger cascading failures upstream.',
    icon: Share2,
    color: 'text-emerald',
    bgColor: 'bg-emerald/10 border-emerald/20',
    actionLabel: 'Trigger cascade',
  },
]

// Pipeline stages for the tracker
const PIPELINE_STAGES = [
  { key: 'detected', label: 'Detected', caption: 'An alarm fired — something unusual was detected in the cloud.' },
  { key: 'collecting', label: 'Collecting Data', caption: 'Gathering logs, metrics, and traces from the affected services.' },
  { key: 'diagnosing', label: 'Diagnosing', caption: 'An AI model is reading the incident data and a runbook to figure out what went wrong.' },
  { key: 'pending_approval', label: 'Awaiting Approval', caption: 'The AI has a recommended fix. A human needs to approve it before anything changes in AWS.' },
  { key: 'remediating', label: 'Remediating', caption: 'Executing the approved fix — restarting a service, scaling up, or locking a bucket.' },
  { key: 'verifying', label: 'Verifying', caption: 'Re-checking the same alarm/metric that caught the problem, to confirm the fix actually worked.' },
  { key: 'resolved', label: 'Resolved', caption: 'The signal is back to normal. Incident closed.' },
]

// Map remediation/verification status to pipeline stage
const STATUS_TO_STAGE = {
  // Collector statuses
  detected: 0,
  // Diagnosis statuses
  diagnosing: 2,
  // Approval statuses
  pending_approval: 3,
  approved: 4,
  // Remediation statuses
  remediating: 4,
  executed: 5,
  failed: 5,
  // Verification statuses
  verifying: 5,
  resolved: 6,
  not_resolved: 6,
  inconclusive: 6,
}

export default function DemoControls() {
  const [activeIncident, setActiveIncident] = useState(null)
  const [incidentStatus, setIncidentStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showTracker, setShowTracker] = useState(false)
  const [pendingApproval, setPendingApproval] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectBox, setShowRejectBox] = useState(false)

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

  // The approval handler persists the reason as remediation.rejected_reason
  // (BACKEND_SPEC 5.2), so send it along when the reviewer provides one.
  const handleReject = async () => {
    if (!activeIncident?.incident_id) return
    setLoading(true)
    try {
      await apiClient.rejectIncidentMain(activeIncident.incident_id, rejectReason.trim())
      setShowRejectBox(false)
      setRejectReason('')
      setPendingApproval(false)
    } catch (err) {
      setError(err.message || 'Failed to reject')
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
          {FAULT_CLASSES.map((fault) => {
            const Icon = fault.icon
            const isDisabled = loading || activeIncident
            return (
              <div
                key={fault.id}
                onClick={() => !isDisabled && handleInjectFault(fault.id)}
                className={`card p-5 relative ${fault.bgColor} ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-border-strong hover:bg-opacity-20 cursor-pointer'} transition-all group`}
              >
                <div className="flex items-center space-x-3 mb-3">
                  <div className={`p-3 rounded-lg ${fault.color} bg-opacity-10`}>
                    <Icon className="w-6 h-6" />
                  </div>
                </div>
                <h3 className="text-base font-semibold text-text-primary mb-1">{fault.label}</h3>
                <p className="text-xs text-text-secondary mb-4 flex-1">{fault.description}</p>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    if (!isDisabled) handleInjectFault(fault.id)
                  }}
                  disabled={isDisabled}
                  className="w-full btn-primary text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading && activeIncident?.fault_class === fault.id ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      Injecting...
                    </>
                  ) : (
                    fault.actionLabel
                  )}
                </button>
                {isDisabled && activeIncident && (
                  <div className="mt-2 text-[11px] text-text-muted text-center">
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
          onReject={pendingApproval ? handleReject : null}
          isApproving={loading && pendingApproval}
          isRejecting={loading && showRejectBox}
          showRejectBox={showRejectBox}
          rejectReason={rejectReason}
          onRejectReasonChange={setRejectReason}
          onToggleRejectBox={() => setShowRejectBox((v) => !v)}
        />
      )}
    </div>
  )
}

function PipelineTracker({
  incident,
  currentStage,
  stages,
  onApprove,
  onReject,
  isApproving,
  isRejecting,
  showRejectBox,
  rejectReason,
  onRejectReasonChange,
  onToggleRejectBox,
}) {
  const faultClassLabel = {
    resource_exhaustion: 'Resource Exhaustion',
    misconfiguration: 'Misconfiguration',
    service_cascade: 'Service Cascade',
  }[incident.fault_class] || incident.fault_class

  // Terminal outcomes: stop the stepper animation and show a final banner
  // instead of leaving "Resolved" as a perpetually-pulsing current stage.
  const verificationStatus = incident.verification?.status
  const remediationStatus = incident.remediation?.status
  const terminal =
    verificationStatus === 'resolved' ? 'resolved'
    : remediationStatus === 'rejected' ? 'rejected'
    : (verificationStatus === 'not_resolved' || remediationStatus === 'failed') ? 'failed'
    : null
  const isTerminal = terminal !== null
  const effectiveStage = isTerminal ? stages.length : currentStage

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6 gap-3 flex-wrap">
        <div className="flex items-center space-x-3 min-w-0">
          <div className="p-2 bg-crimson/10 rounded-lg flex-shrink-0">
            <AlertCircle className="w-5 h-5 text-crimson" />
          </div>
          <div className="min-w-0">
            <h3 className="text-lg font-semibold text-text-primary">Pipeline Tracker</h3>
            <p className="text-xs text-text-secondary truncate">{faultClassLabel} • {incident.incident_id?.substring(0, 8)}</p>
          </div>
        </div>
        {incident.remediation?.status === 'pending_approval' && onApprove && (
          <div className="flex items-center space-x-2 flex-shrink-0">
            {showRejectBox ? (
              <>
                <button onClick={onReject} disabled={isRejecting} className="btn-danger text-sm flex items-center space-x-2 whitespace-nowrap">
                  {isRejecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                  <span>Confirm Reject</span>
                </button>
                <button onClick={onToggleRejectBox} className="btn-ghost text-sm">Cancel</button>
              </>
            ) : (
              <>
                <button onClick={onToggleRejectBox} className="btn-danger text-sm flex items-center space-x-2 whitespace-nowrap">
                  <XCircle className="w-4 h-4" />
                  <span>Reject</span>
                </button>
                <button onClick={onApprove} disabled={isApproving} className="btn-success text-sm flex items-center space-x-2 whitespace-nowrap">
                  {isApproving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
                  <span>Approve Fix</span>
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {/* Reject reason input — shown under the header buttons */}
      {showRejectBox && onReject && (
        <div className="mb-6 p-4 bg-bg-elevated border border-border-subtle rounded-card">
          <label htmlFor="reject-reason" className="block text-xs font-medium text-text-secondary mb-2">
            Why are you rejecting this fix? (saved to the incident record as <span className="mono">remediation.rejected_reason</span>)
          </label>
          <textarea
            id="reject-reason"
            value={rejectReason}
            onChange={(e) => onRejectReasonChange(e.target.value)}
            placeholder="e.g. Wrong service diagnosed — the cascade started at Service B, not C"
            rows={3}
            className="w-full bg-bg-input border border-border-default rounded-button px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-border-strong resize-none"
          />
        </div>
      )}

      {/* Horizontal Stepper — one continuous connector line running through
          all nodes (the old version drew a dead-end line under each circle).
          Stage captions live in the "Current Stage" panel below, so the nodes
          stay compact and the whole line fits the card width. */}
      <div className="overflow-x-auto -mx-1 px-1">
        <div className="flex items-start w-full min-w-[600px]">
        {stages.map((stage, index) => {
          const isComplete = index < effectiveStage
          const isCurrent = index === effectiveStage && !isTerminal
          const isFuture = index > effectiveStage

          return (
            <Fragment key={stage.key}>
              {/* Node + label */}
              <div className="flex flex-col items-center flex-shrink-0 w-20 sm:w-24">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-300 ${
                  isComplete ? 'bg-emerald text-white' :
                  isCurrent ? 'bg-amber text-white' :
                  isTerminal && index === stages.length - 1 && terminal === 'rejected' ? 'bg-border-strong text-text-muted' :
                  'bg-bg-base border-2 border-dashed border-border-subtle'
                } ${isCurrent ? 'ring-4 ring-amber/20' : ''}`}>
                  {isComplete ? (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
                  ) : isCurrent ? (
                    <div className="w-2.5 h-2.5 bg-white rounded-full animate-pulse" />
                  ) : (
                    <span className="text-[11px] text-text-muted font-mono">{index + 1}</span>
                  )}
                </div>
                <div className={`mt-2 text-[11px] leading-tight text-center px-1 ${
                  isCurrent ? 'text-text-primary font-medium' :
                  isComplete ? 'text-emerald' :
                  'text-text-muted'
                }`}>
                  {stage.label}
                </div>
              </div>

              {/* Connector segment between nodes — solid emerald behind us,
                  dashed ahead (per DESIGN_SPEC §5.7) */}
              {index < stages.length - 1 && (
                <div className="flex-1 min-w-3 flex justify-center" style={{ marginTop: 17 }}>
                  <div className={`h-px w-full ${
                    index < effectiveStage - 1 || (isComplete && effectiveStage >= stages.length)
                      ? 'bg-emerald'
                      : index === effectiveStage - 1
                      ? 'bg-gradient-to-r from-emerald to-border-subtle'
                      : 'border-t border-dashed border-border-subtle'
                  }`} />
                </div>
              )}
            </Fragment>
          )
        })}
        </div>
      </div>

      {/* Terminal outcome banner */}
      {isTerminal && (
        <div className={`mt-6 p-4 rounded-card border ${
          terminal === 'resolved' ? 'bg-emerald/10 border-emerald/20' :
          terminal === 'rejected' ? 'bg-bg-elevated border-border-subtle' :
          'bg-crimson/10 border-crimson/20'
        }`}>
          <p className={`text-xs font-medium ${
            terminal === 'resolved' ? 'text-emerald' :
            terminal === 'rejected' ? 'text-text-secondary' : 'text-crimson'
          }`}>
            {terminal === 'resolved' && 'Incident resolved — the original signal is back to normal. Pipeline complete.'}
            {terminal === 'rejected' && 'Fix rejected by a human reviewer. The incident stays recorded with the rejection reason.'}
            {terminal === 'failed' && 'Remediation did not resolve the incident — see the incident detail for the verification result.'}
          </p>
        </div>
      )}

      {/* Current Stage Detail */}
      {!isTerminal && effectiveStage < stages.length && (
        <div className="mt-6 p-4 bg-bg-elevated rounded-card border border-border-subtle">
          <h4 className="text-sm font-medium text-text-primary mb-2">
            Current Stage: {stages[effectiveStage].label}
          </h4>
          <p className="text-sm text-text-secondary">{stages[effectiveStage].caption}</p>
          
          {effectiveStage === 3 && (
            <div className="mt-4 p-3 bg-amber/10 border border-amber/20 rounded-card">
              <p className="text-xs text-amber font-medium">Action Required: Human approval needed to proceed with remediation.</p>
            </div>
          )}
          
          {effectiveStage === 5 && (
            <div className="mt-4 p-3 bg-emerald/10 border border-emerald/20 rounded-card">
              <p className="text-xs text-emerald font-medium">Verifying the fix worked by re-checking the original alarm signal.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}