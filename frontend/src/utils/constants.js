// Status mappings and constants for the dashboard
// Single source of truth for all shared constants across the frontend

export const FAULT_CLASSES = {
  RESOURCE_EXHAUSTION: 'resource_exhaustion',
  MISCONFIGURATION: 'misconfiguration',
  SERVICE_CASCADE: 'service_cascade'
}

export const FAULT_CLASS_LABELS = {
  [FAULT_CLASSES.RESOURCE_EXHAUSTION]: 'Resource Exhaustion',
  [FAULT_CLASSES.MISCONFIGURATION]: 'Misconfiguration',
  [FAULT_CLASSES.SERVICE_CASCADE]: 'Service Cascade'
}

export const FAULT_CLASS_DESCRIPTIONS = {
  [FAULT_CLASSES.RESOURCE_EXHAUSTION]: 'Forces Service A Lambda Duration alarm into ALARM state. Simulates memory or compute exhaustion causing function timeouts.',
  [FAULT_CLASSES.SERVICE_CASCADE]: 'Fires the cascade alarm. Simulates Service C failing and propagating errors upstream through Service B to Service A.',
  [FAULT_CLASSES.MISCONFIGURATION]: 'Triggers an AWS Config rule evaluation. Simulates a public S3 bucket or an overly-permissive IAM policy being detected.',
}

export const FAULT_CLASS_SEVERITY = {
  [FAULT_CLASSES.RESOURCE_EXHAUSTION]: { label: 'Critical', className: 'badge-critical' },
  [FAULT_CLASSES.SERVICE_CASCADE]: { label: 'High', className: 'badge-warning' },
  [FAULT_CLASSES.MISCONFIGURATION]: { label: 'Medium', className: 'badge-info' },
}

export const FAULT_CLASS_ICONS = {
  [FAULT_CLASSES.RESOURCE_EXHAUSTION]: '\u26a1',
  [FAULT_CLASSES.SERVICE_CASCADE]: '\uD83D\uDD17',
  [FAULT_CLASSES.MISCONFIGURATION]: '\uD83D\uDEE1\uFE0F',
}

export const REMEDIATION_STATUSES = {
  PENDING_APPROVAL: 'pending_approval',
  APPROVED: 'approved',
  EXECUTED: 'executed',
  REJECTED: 'rejected',
  FAILED: 'failed'
}

export const VERIFICATION_STATUSES = {
  NOT_RUN: 'not_run',
  RESOLVED: 'resolved',
  NOT_RESOLVED: 'not_resolved',
  INCONCLUSIVE: 'inconclusive'
}

export const PIPELINE_STAGES = [
  { key: 'detected', label: 'Detect' },
  { key: 'evidence_collected', label: 'Collect' },
  { key: 'diagnosed', label: 'Diagnose' },
  { key: 'pending_approval', label: 'Approve' },
  { key: 'executed', label: 'Remediate' },
  { key: 'verified', label: 'Verify' }
]

export const STAGE_LABELS = PIPELINE_STAGES.map(s => s.label)

export const PIPELINE_STAGE_DETAILS = [
  { key: 'detected', label: 'Detected', caption: 'An alarm fired — something unusual was detected in the cloud.' },
  { key: 'collecting', label: 'Collecting Data', caption: 'Gathering logs, metrics, and traces from the affected services.' },
  { key: 'diagnosing', label: 'Diagnosing', caption: 'An AI model is reading the incident data and a runbook to figure out what went wrong.' },
  { key: 'pending_approval', label: 'Awaiting Approval', caption: 'The AI has a recommended fix. A human needs to approve it before anything changes in AWS.' },
  { key: 'remediating', label: 'Remediating', caption: 'Executing the approved fix — restarting a service, scaling up, or locking a bucket.' },
  { key: 'verifying', label: 'Verifying', caption: 'Re-checking the same alarm/metric that caught the problem, to confirm the fix actually worked.' },
  { key: 'resolved', label: 'Resolved', caption: 'The signal is back to normal. Incident closed.' },
]

export const STATUS_ICONS = {
  complete: '✓',
  in_progress: '●',
  awaiting: '○',
  failed: '✗',
  not_started: '○'
}

export const CONFIDENCE_LEVELS = {
  HIGH: { min: 90, label: 'High', className: 'badge-success' },
  MEDIUM: { min: 70, label: 'Medium', className: 'badge-warning' },
  LOW: { min: 0, label: 'Low', className: 'badge-critical' }
}

export function getConfidenceLevel(confidence) {
  const score = typeof confidence === 'string' ? parseFloat(confidence) : confidence
  const percentage = score * 100
  
  if (percentage >= CONFIDENCE_LEVELS.HIGH.min) return CONFIDENCE_LEVELS.HIGH
  if (percentage >= CONFIDENCE_LEVELS.MEDIUM.min) return CONFIDENCE_LEVELS.MEDIUM
  return CONFIDENCE_LEVELS.LOW
}

export const SEVERITY_LEVELS = {
  CRITICAL: 'critical',
  WARNING: 'warning',
  INFO: 'info'
}

// Action risk levels and labels — must match backend/remediation/actions.py dispatch map keys
export const ACTION_RISK = {
  lock_s3_bucket: { level: 'High', className: 'badge-critical' },
  tighten_iam_policy: { level: 'High', className: 'badge-critical' },
  scale_up: { level: 'Medium', className: 'badge-warning' },
  restart_service: { level: 'Medium', className: 'badge-warning' },
  restart_downstream_service: { level: 'Medium', className: 'badge-warning' },
  manual_review_required: { level: 'Low', className: 'badge-info' },
}

export const ACTION_LABELS = {
  lock_s3_bucket: 'Lock S3 Bucket (Block Public Access)',
  tighten_iam_policy: 'Tighten IAM Policy',
  scale_up: 'Scale Up Lambda Concurrency',
  restart_service: 'Restart Service (Force Lambda Cold-Start)',
  restart_downstream_service: 'Restart Downstream Service (Force Lambda Cold-Start)',
  manual_review_required: 'Manual Review Required',
}

export const HIGH_RISK_ACTIONS = new Set(['lock_s3_bucket', 'tighten_iam_policy'])

// Polling intervals in milliseconds — matches FRONTEND_SPEC.md
export const POLLING_INTERVALS = {
  INCIDENTS_FEED: 8000, // 8 seconds for active incidents
  INCIDENT_DETAIL: 5000, // 5 seconds for active detail
  METRICS: 120000 // 2 minutes
}

// Date formatting
export const DATE_FORMATS = {
  FULL: 'PPpp', // Jan 1, 2024 at 1:00:00 PM
  SHORT: 'MMM d, HH:mm', // Jan 1, 13:00
  TIME_ONLY: 'HH:mm:ss', // 13:00:00
  RELATIVE: 'relative' // 5 minutes ago
}

// Demo mode action labels
export const DEMO_ACTION_LABELS = {
  [FAULT_CLASSES.RESOURCE_EXHAUSTION]: 'Break it',
  [FAULT_CLASSES.MISCONFIGURATION]: 'Expose it',
  [FAULT_CLASSES.SERVICE_CASCADE]: 'Trigger cascade',
}

// Replay mode speed options
export const SPEED_OPTIONS = [
  { label: '1s', value: 1000 },
  { label: '3s', value: 3000 },
  { label: '5s', value: 5000 }
]

// Chart colors — shared Obsidian palette for Recharts
export const CHART_COLORS = {
  primary: '#F2F2F2',
  crimson: '#D63C4B',
  amber: '#F0A23A',
  emerald: '#46B887',
  muted: '#55555D',
  secondary: '#85858C',
  gridLine: '#1E1E22',
  tooltip: '#1B1B1F',
  tooltipBorder: '#2A2A2D',
  rag: '#A8C5DA',
  noRag: '#85858C',
}