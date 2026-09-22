// Status mappings and constants for the dashboard

// Display identity shown in the UI (sidebar, topbar, greeting) until a real
// auth/profile system exists. Swap this single constant when that lands.
export const CURRENT_USER = {
  name: 'John Doe',
  firstName: 'John',
  initials: 'JD',
  role: 'Responder'
}

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

// Polling intervals in milliseconds
export const POLLING_INTERVALS = {
  INCIDENTS_FEED: 30000, // 30 seconds
  INCIDENT_DETAIL: 60000, // 60 seconds
  METRICS: 120000 // 2 minutes
}

// Date formatting
export const DATE_FORMATS = {
  FULL: 'PPpp', // Jan 1, 2024 at 1:00:00 PM
  SHORT: 'MMM d, HH:mm', // Jan 1, 13:00
  TIME_ONLY: 'HH:mm:ss', // 13:00:00
  RELATIVE: 'relative' // 5 minutes ago
}