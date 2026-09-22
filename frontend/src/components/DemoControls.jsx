import { useState, useEffect, useRef, useCallback } from 'react'
import { AlertCircle, Server, Unlock, Share2, Loader2, CheckCircle, XCircle, Play, Zap } from 'lucide-react'
import { apiClient } from '../config/api'

// Plain-language fault scenarios. The tone classes (rose/amber/violet) give
// each card its own color identity per the approved Light & Premium design;
// the script + alarm names are the real ones the demo Lambda uses.
const DEMO_ENV = 'staging'
const FAULTS = [
  {
    id: 'resource_exhaustion',
    tone: 'rose',
    num: 'FAULT 01',
    icon: Server,
    iconColor: 'text-crimson',
    name: 'Overload a Server',
    description: "We'll spike CPU on one of our demo services until it trips an alarm.",
    script: 'inject_resource_exhaustion.py',
    alarm: `incident-service-a-resource-exhaustion-${DEMO_ENV}`,
    actionLabel: 'Break it',
  },
  {
    id: 'misconfiguration',
    tone: 'amber',
    num: 'FAULT 02',
    icon: Unlock,
    iconColor: 'text-amber',
    name: 'Expose an S3 Bucket',
    description: "We'll remove the public access block on a demo bucket and let the config detector catch it.",
    script: 'inject_misconfiguration.py',
    alarm: `incident-public-s3-${DEMO_ENV}`,
    actionLabel: 'Expose it',
  },
  {
    id: 'service_cascade',
    tone: 'violet',
    num: 'FAULT 03',
    icon: Share2,
    iconColor: 'text-violet',
    name: 'Trigger a Cascade',
    description: "We'll fail a downstream service and watch retry storms ripple upstream.",
    script: 'inject_service_cascade.py',
    alarm: `incident-service-cascade-${DEMO_ENV}`,
    actionLabel: 'Trigger cascade',
  },
]

// Pipeline stages for the tracker
const PIPELINE_STAGES = [
  { key: 'detected', label: 'Detected' },
  { key: 'collecting', label: 'Collecting' },
  { key: 'diagnosing', label: 'Diagnosing' },
  { key: 'pending_approval', label: 'Awaiting Approval' },
  { key: 'remediating', label: 'Remediating' },
  { key: 'verifying', label: 'Verifying' },
  { key: 'resolved', label: 'Resolved' },
]

const STAGE_CAPTIONS = {
  0: 'An alarm fired — something unusual was detected in the cloud.',
  1: 'Gathering logs, metrics, and traces from the affected services.',
  2: 'An AI model is reading the incident data and a runbook to figure out what went wrong.',
  3: 'The AI has a recommended fix. A human needs to approve it before anything changes in AWS.',
  4: 'Executing the approved fix — restarting a service, scaling up, or locking a bucket.',
  5: 'Re-checking the same alarm/metric that caught the problem, to confirm the fix worked.',
  6: 'The signal is back to normal. Incident closed.',
}

export default function DemoControls() {
  const [activeIncident, setActiveIncident] = useState(null) // { fault_class, startedAt } or the polled incident
  const [latest, setLatest] = useState(null) // newest incident from the feed (status polling)
  const [recent, setRecent] = useState([]) // top few incidents, for correlating an injection to its incident
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [rejectReason, setRejectReason] = useState('')
  const [showRejectBox, setShowRejectBox] = useState(false)
  const [runningFault, setRunningFault] = useState(null) // fault id whose card shows "Running…"
  const [logs, setLogs] = useState([])

  const t0Ref = useRef(null)
  const consoleRef = useRef(null)
  const loggedRef = useRef({ incident: null, gate: null, terminal: null })

  const pushLog = useCallback((text, cls = '') => {
    const t0 = t0Ref.current || Date.now()
    const s = (Date.now() - t0) / 1000
    const m = Math.floor(s / 60)
    const stamp = `${String(m).padStart(2, '0')}:${(s % 60).toFixed(1).padStart(4, '0')}`
    setLogs(prev => [...prev.slice(-11), { t: stamp, text, cls }])
  }, [])

  useEffect(() => {
    if (consoleRef.current) consoleRef.current.scrollTop = consoleRef.current.scrollHeight
  }, [logs])

  // Poll the latest incidents — this is how the UI learns the injected fault
  // got correlated into a real incident and progressed through the pipeline.
  useEffect(() => {
    let cancelled = false
    const pollStatus = async () => {
      try {
        const data = await apiClient.getIncidents({ limit: 5, sort: 'detected_at', order: 'desc' })
        const items = data?.items || []
        if (!cancelled) {
          setLatest(items[0] || null)
          setRecent(items)
        }
      } catch (err) {
        console.error('Failed to poll incident status:', err)
      }
    }
    pollStatus()
    const interval = setInterval(pollStatus, 5000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  const isTerminalIncident = (inc) => {
    const r = inc?.remediation?.status
    const v = inc?.verification?.status
    return v === 'resolved' || r === 'rejected' || v === 'not_resolved' || v === 'inconclusive' || r === 'failed'
  }

  // Console narration for pipeline milestones. Each milestone logs once
  // (tracked in loggedRef, keyed by incident id).
  const narrate = useCallback((inc) => {
    if (!inc?.incident_id) return
    const id = inc.incident_id
    const rStatus = inc.remediation?.status
    const vStatus = inc.verification?.status
    if (loggedRef.current.incident !== id) {
      loggedRef.current.incident = id
      pushLog(`incident correlated · ${id.substring(0, 8)} · evidence → s3://…-${DEMO_ENV}/evidence/`, 'ok')
    }
    if (inc.diagnosis?.root_cause && !loggedRef.current.diagnosed) {
      loggedRef.current.diagnosed = true
      pushLog(`bedrock: diagnosis ready · confidence ${Math.round((inc.diagnosis.confidence || 0) * 100)}%`, 'hi')
    }
    if (rStatus === 'pending_approval' && loggedRef.current.gate !== id) {
      loggedRef.current.gate = id
      pushLog('⏸  HUMAN GATE — awaiting your decision below', 'hi')
    }
    const terminal =
      vStatus === 'resolved' ? 'resolved'
      : rStatus === 'rejected' ? 'rejected'
      : (vStatus === 'not_resolved' || vStatus === 'inconclusive' || rStatus === 'failed') ? 'failed'
      : null
    if (terminal && loggedRef.current.terminal !== id) {
      loggedRef.current.terminal = id
      if (terminal === 'resolved') pushLog('signal re-checked · RESOLVED ✓', 'ok')
      else if (terminal === 'rejected') pushLog('remediation halted · rejection reason recorded', 'bad')
      else pushLog('verification: NOT RESOLVED · flagged for human follow-up', 'warn')
    }
  }, [pushLog])

  // React to pipeline progress — ONLY after the user explicitly starts a
  // demo in this session. The dashboard is read-only visualization per the
  // project README: no demo tracker, banner, or "awaiting decision" state is
  // shown on page load. (In-flight approvals are acted on via Slack links or
  // the incident feed's explicit action buttons.)
  useEffect(() => {
    if (!latest) return

    // (a) Waiting for correlation after an explicit injection: adopt the
    // first recent incident of the SAME fault class detected AFTER the click.
    // Matching on fault_class + time avoids grabbing a stale incident.
    if (activeIncident && !activeIncident.incident_id && activeIncident.startedAt) {
      const match = recent.find(
        (i) =>
          i.fault_class === activeIncident.fault_class &&
          new Date(i.detected_at).getTime() >= activeIncident.startedAt - 5000 &&
          !isTerminalIncident(i)
      )
      if (match) {
        setActiveIncident(match)
        narrate(match)
      }
      return
    }

    // (b) Keep the tracker fed with the freshest status of its incident.
    if (activeIncident?.incident_id && latest.incident_id === activeIncident.incident_id) {
      setActiveIncident(latest)
      narrate(latest)
    }
  }, [latest, recent, activeIncident, narrate])

  const handleInjectFault = async (fault) => {
    if (loading || inFlight) return
    setLoading(true)
    setError(null)
    t0Ref.current = Date.now()
    loggedRef.current = { incident: null, gate: null, terminal: null, diagnosed: false }
    setLogs([])
    setRunningFault(fault.id)
    pushLog(`→ triggering fault · ./fault_injection/${fault.script}`)
    try {
      await apiClient.injectFault(fault.id)
      pushLog(`${fault.alarm} → ALARM (demo injection)`, 'warn')
      setTimeout(() => pushLog('collector: snapshotting metrics + logs + config…'), 1400)
      setActiveIncident({ fault_class: fault.id, startedAt: Date.now() })
    } catch (err) {
      setError(err.message || 'Failed to inject fault')
      setRunningFault(null)
      t0Ref.current = null
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!activeIncident?.incident_id) return
    setLoading(true)
    pushLog('✓ approved · executing remediation plan', 'ok')
    try {
      await apiClient.approveIncidentMain(activeIncident.incident_id)
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
    pushLog(`✗ rejected${rejectReason.trim() ? ' · reason recorded' : ''} · back to diagnosis`, 'bad')
    try {
      await apiClient.rejectIncidentMain(activeIncident.incident_id, rejectReason.trim())
      setShowRejectBox(false)
      setRejectReason('')
    } catch (err) {
      setError(err.message || 'Failed to reject')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setActiveIncident(null)
    setRunningFault(null)
    setLogs([])
    t0Ref.current = null
    loggedRef.current = { incident: null, gate: null, terminal: null, diagnosed: false }
  }

  // Derive tracker state from the freshest status of the active incident.
  const incidentStatus =
    activeIncident && latest && latest.incident_id === activeIncident.incident_id ? latest : activeIncident
  const remediationStatus = incidentStatus?.remediation?.status
  const verificationStatus = incidentStatus?.verification?.status
  const pendingApproval =
    activeIncident?.incident_id && remediationStatus === 'pending_approval'
  const terminal =
    verificationStatus === 'resolved' ? 'resolved'
    : remediationStatus === 'rejected' ? 'rejected'
    : (verificationStatus === 'not_resolved' || verificationStatus === 'inconclusive' || remediationStatus === 'failed') ? 'failed'
    : null
  const inFlight = Boolean(activeIncident) && !terminal
  const currentStageIndex = getCurrentStageIndex(incidentStatus)

  const phaseLabel = terminal
    ? (terminal === 'resolved' ? 'Resolved' : terminal === 'rejected' ? 'Rejected' : 'Needs attention')
    : pendingApproval ? 'Awaiting your decision'
    : inFlight ? 'Pipeline running'
    : 'Pipeline ready'

  return (
    <div className="hero">
      {/* Header row */}
      <div className="flex items-start gap-4">
        <div className="min-w-0">
          <div className="hero-kicker">
            <span className={`live-dot${inFlight ? ' !bg-amber' : ''}`} />
            Live AWS Demo
          </div>
          <h2 className="hero-title">Break it on purpose. Watch AI fix it.</h2>
          <p className="hero-sub">
            Trigger a real, sandboxed fault on staging. The pipeline detects it, collects evidence, diagnoses with
            Bedrock — and asks you before it touches anything.
          </p>
        </div>
        <div className="ml-auto flex-none">
          <span className={`live-pill${inFlight && !pendingApproval ? ' busy' : ''}`}>
            <span className="live-dot" />
            {phaseLabel}
          </span>
        </div>
      </div>

      {/* Fault cards — one color identity per fault */}
      <div className="fault-grid">
        {FAULTS.map((fault) => {
          const Icon = fault.icon
          const isDisabled = loading || inFlight
          const isRunning = runningFault === fault.id || (inFlight && activeIncident?.fault_class === fault.id)
          return (
            <button
              key={fault.id}
              className={`fault-card ${fault.tone}${isRunning ? ' running' : ''}`}
              disabled={isDisabled}
              onClick={() => handleInjectFault(fault)}
            >
              <span className="fault-num">{fault.num}</span>
              <span className="fault-ico">
                <Icon className={`w-[22px] h-[22px] ${fault.iconColor}`} />
              </span>
              <span>
                <span className="fault-name">{fault.name}</span>
                <span className="fault-desc">{fault.description}</span>
              </span>
              <span className="fault-meta">
                <span className="fault-script">{fault.script}</span>
                <span className="fault-run">
                  {isRunning ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Running…</>
                  ) : (
                    <>{fault.actionLabel} <Play className="w-2.5 h-2.5 fill-current" /></>
                  )}
                </span>
              </span>
            </button>
          )
        })}
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-4 px-4 py-3 bg-crimson-surface border border-crimson/20 rounded-card text-crimson text-sm fade-up">
          {error}
        </div>
      )}

      {/* Live console — narrates the real pipeline events */}
      <div className="console-frame">
        <div className="console-bar">
          <span className="console-dot" style={{ background: '#F26D6D' }} />
          <span className="console-dot" style={{ background: '#F2C14E' }} />
          <span className="console-dot" style={{ background: '#5EC26A' }} />
          <span className="console-title">pipeline — {incidentStatus?.incident_id ? incidentStatus.incident_id.substring(0, 8) : 'idle'}</span>
          {logs.length > 0 && <span className="console-live">● {terminal ? 'COMPLETE' : 'LIVE'}</span>}
        </div>
        {logs.length === 0 ? (
          <div className="console console-idle">
            Press <b>Break it</b>, <b>Expose it</b> or <b>Trigger cascade</b> — the pipeline narrates itself here.
          </div>
        ) : (
          <div className="console" ref={consoleRef}>
            {logs.map((l, i) => (
              <div key={i}><span className="t">{l.t}</span><span className={l.cls}>{l.text}</span></div>
            ))}
          </div>
        )}
      </div>

      {/* Stepper + decision banner — only when a demo incident is active */}
      {activeIncident && (
        <>
          <div className="stepper overflow-x-auto">
            {PIPELINE_STAGES.map((stage, i) => {
              const isComplete = terminal ? true : i < currentStageIndex
              const isCurrent = !terminal && i === currentStageIndex
              return (
                <div
                  key={stage.key}
                  className={`step${isComplete ? ' done' : ''}${isCurrent ? ' active' : ''}${isCurrent && inFlight && !pendingApproval ? ' pulse' : ''}`}
                  style={{ minWidth: 96 }}
                >
                  <div className="step-dot">
                    {isComplete ? (
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      i + 1
                    )}
                  </div>
                  <div className="step-label">{stage.label}</div>
                </div>
              )
            })}
          </div>

          {/* Human gate */}
          {pendingApproval && !terminal && (
            <div className="decision await">
              <div className="min-w-0">
                <div className="decision-txt">Human approval required</div>
                <div className="decision-sub">
                  {incidentStatus?.incident_id?.substring(0, 8)} — scoped, reversible fix proposed
                  {incidentStatus?.diagnosis?.confidence != null &&
                    ` at ${Math.round(incidentStatus.diagnosis.confidence * 100)}% confidence`}.
                  Nothing executes until you decide.
                </div>
              </div>
              {!showRejectBox && (
                <div className="decision-actions">
                  <button onClick={() => setShowRejectBox(true)} className="btn-danger">
                    <XCircle className="w-4 h-4" /> Reject
                  </button>
                  <button onClick={handleApprove} disabled={loading} className="btn-success">
                    {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />} Approve fix
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Reject reason box — saved to the incident record as remediation.rejected_reason */}
          {pendingApproval && showRejectBox && (
            <div className="mt-3 p-4 bg-white border border-border-strong rounded-card fade-up">
              <label htmlFor="reject-reason" className="block text-xs font-semibold text-text-secondary mb-2">
                Why are you rejecting this fix? (saved to the incident as <span className="mono">remediation.rejected_reason</span>)
              </label>
              <textarea
                id="reject-reason"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g. Wrong service diagnosed — the cascade started at Service B, not C"
                rows={3}
                className="w-full bg-bg-elevated border border-border-default rounded-button px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-indigo resize-none"
              />
              <div className="flex justify-end gap-2 mt-3">
                <button onClick={() => setShowRejectBox(false)} className="btn-ghost">Cancel</button>
                <button onClick={handleReject} disabled={loading} className="btn-danger">
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />} Confirm reject
                </button>
              </div>
            </div>
          )}

          {/* Remediation in progress */}
          {!terminal && remediationStatus && ['approved', 'executed', 'remediating'].includes(remediationStatus) && !pendingApproval && (
            <div className="decision done-ok">
              <div>
                <div className="decision-txt">✓ Approved — remediation running</div>
                <div className="decision-sub">Executing the proposed fix and re-checking signals.</div>
              </div>
            </div>
          )}

          {/* Current stage caption while the pipeline works */}
          {!terminal && !pendingApproval && !remediationStatus && (
            <div className="decision" style={{ background: '#FAFBFE', border: '1px solid #E7ECF3' }}>
              <div>
                <div className="decision-txt">
                  <Zap className="w-4 h-4 inline-block mr-1.5 -mt-0.5 text-indigo" />
                  Current stage: {PIPELINE_STAGES[currentStageIndex].label}
                </div>
                <div className="decision-sub">{STAGE_CAPTIONS[currentStageIndex]}</div>
              </div>
            </div>
          )}

          {/* Terminal outcomes */}
          {terminal === 'resolved' && (
            <div className="decision done-ok">
              <div>
                <div className="decision-txt">✓ Resolved — the original signal is back to normal</div>
                <div className="decision-sub">Pipeline complete. The incident is closed in the record.</div>
              </div>
              <div className="decision-actions">
                <button onClick={handleReset} className="btn-ghost">New run</button>
              </div>
            </div>
          )}
          {terminal === 'rejected' && (
            <div className="decision done-no">
              <div>
                <div className="decision-txt">✗ Rejected — reason recorded on the incident</div>
                <div className="decision-sub">The fix was not executed. The incident stays recorded with your reason.</div>
              </div>
              <div className="decision-actions">
                <button onClick={handleReset} className="btn-ghost">New run</button>
              </div>
            </div>
          )}
          {terminal === 'failed' && (
            <div className="decision done-no">
              <div>
                <div className="decision-txt">Remediation did not resolve the incident</div>
                <div className="decision-sub">See the incident detail for the verification result.</div>
              </div>
              <div className="decision-actions">
                <button onClick={handleReset} className="btn-ghost">New run</button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Safety footnote */}
      <div className="mt-5 flex items-center gap-2 text-xs text-text-muted">
        <AlertCircle className="w-3.5 h-3.5" />
        Faults are injected against the sandbox ({DEMO_ENV}) only — CloudWatch alarm states and Config rules, never
        your production services. Auto-invoke of real AWS remediation on approve is off by default locally.
      </div>
    </div>
  )
}

// Map remediation/verification status to pipeline stage index (0-6)
function getCurrentStageIndex(incident) {
  if (!incident) return 0
  const remediationStatus = incident.remediation?.status
  const verificationStatus = incident.verification?.status

  if (verificationStatus === 'resolved') return 6
  if (verificationStatus === 'not_resolved' || verificationStatus === 'inconclusive') return 6
  if (verificationStatus && verificationStatus !== 'not_run') return 5
  if (remediationStatus === 'executed') return 5
  if (remediationStatus === 'approved') return 4
  if (remediationStatus === 'pending_approval') return 3
  if (incident.diagnosis?.root_cause) return 2
  return 0
}
