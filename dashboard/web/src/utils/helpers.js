import { format, formatDistanceToNow, parseISO } from 'date-fns'
import { DATE_FORMATS, REMEDIATION_STATUSES, VERIFICATION_STATUSES } from './constants'

export function formatDate(dateString, formatType = DATE_FORMATS.SHORT) {
  if (!dateString) return 'N/A'
  
  try {
    const date = parseISO(dateString)
    
    if (formatType === DATE_FORMATS.RELATIVE) {
      return formatDistanceToNow(date, { addSuffix: true })
    }
    
    return format(date, formatType)
  } catch (error) {
    console.warn('Invalid date format:', dateString)
    return 'Invalid date'
  }
}

export function getIncidentStatus(incident) {
  const remediation = incident.remediation || {}
  const verification = incident.verification || {}
  
  // Check verification status first (final state)
  if (verification.status === VERIFICATION_STATUSES.RESOLVED) {
    return { status: 'resolved', className: 'status-resolved', label: 'Resolved' }
  }
  
  if (verification.status === VERIFICATION_STATUSES.NOT_RESOLVED) {
    return { status: 'not_resolved', className: 'status-not-resolved', label: 'Not Resolved' }
  }
  
  if (verification.status === VERIFICATION_STATUSES.INCONCLUSIVE) {
    return { status: 'inconclusive', className: 'status-warning', label: 'Inconclusive' }
  }
  
  // Check remediation status
  switch (remediation.status) {
    case REMEDIATION_STATUSES.EXECUTED:
      return { status: 'executed', className: 'status-executed', label: 'Executed' }
    case REMEDIATION_STATUSES.APPROVED:
      return { status: 'approved', className: 'status-approved', label: 'Approved' }
    case REMEDIATION_STATUSES.PENDING_APPROVAL:
      return { status: 'pending_approval', className: 'status-pending-approval', label: 'Pending Approval' }
    case REMEDIATION_STATUSES.REJECTED:
      return { status: 'rejected', className: 'status-rejected', label: 'Rejected' }
    case REMEDIATION_STATUSES.FAILED:
      return { status: 'failed', className: 'status-failed', label: 'Failed' }
  }
  
  // Check if diagnosed
  if (incident.diagnosis && incident.diagnosis.root_cause) {
    return { status: 'diagnosed', className: 'status-diagnosing', label: 'Diagnosed' }
  }
  
  // Default to detected
  return { status: 'detected', className: 'status-detected', label: 'Detected' }
}

export function getPipelineStageStatus(incident, stage) {
  const remediation = incident.remediation || {}
  const verification = incident.verification || {}
  const diagnosis = incident.diagnosis || {}
  
  switch (stage) {
    case 'detected':
      return incident.detected_at ? 'complete' : 'not_started'
      
    case 'evidence_collected':
      return incident.raw_data_s3_key ? 'complete' : 'not_started'
      
    case 'diagnosed':
      return diagnosis.root_cause ? 'complete' : 'not_started'
      
    case 'pending_approval':
      if (remediation.status === REMEDIATION_STATUSES.PENDING_APPROVAL) return 'in_progress'
      if (remediation.status === REMEDIATION_STATUSES.APPROVED || 
          remediation.status === REMEDIATION_STATUSES.EXECUTED) return 'complete'
      if (remediation.status === REMEDIATION_STATUSES.REJECTED) return 'failed'
      return 'awaiting'
      
    case 'executed':
      if (remediation.status === REMEDIATION_STATUSES.EXECUTED) return 'complete'
      if (remediation.status === REMEDIATION_STATUSES.FAILED) return 'failed'
      if (remediation.status === REMEDIATION_STATUSES.APPROVED) return 'in_progress'
      return 'awaiting'
      
    case 'verified':
      if (verification.status === VERIFICATION_STATUSES.RESOLVED) return 'complete'
      if (verification.status === VERIFICATION_STATUSES.NOT_RESOLVED || 
          verification.status === VERIFICATION_STATUSES.INCONCLUSIVE) return 'failed'
      if (remediation.status === REMEDIATION_STATUSES.EXECUTED) return 'in_progress'
      return 'not_started'
      
    default:
      return 'not_started'
  }
}

export function getSeverityFromFaultClass(faultClass) {
  switch (faultClass) {
    case 'resource_exhaustion':
      return 'critical'
    case 'service_cascade':
      return 'critical'
    case 'misconfiguration':
      return 'warning'
    default:
      return 'info'
  }
}

export function truncateText(text, maxLength = 100) {
  if (!text || text.length <= maxLength) return text
  return text.substring(0, maxLength) + '...'
}

export function calculateMTTR(detectedAt, resolvedAt) {
  if (!detectedAt || !resolvedAt) return null
  
  try {
    const detected = parseISO(detectedAt)
    const resolved = parseISO(resolvedAt)
    const diffMinutes = (resolved - detected) / (1000 * 60)
    return Math.round(diffMinutes)
  } catch (error) {
    console.warn('Error calculating MTTR:', error)
    return null
  }
}

export function formatMTTR(minutes) {
  if (!minutes) return 'N/A'
  
  if (minutes < 60) {
    return `${minutes}m`
  }
  
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  
  if (hours < 24) {
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`
  }
  
  const days = Math.floor(hours / 24)
  const remainingHours = hours % 24
  return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`
}

export function debounce(func, wait) {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}