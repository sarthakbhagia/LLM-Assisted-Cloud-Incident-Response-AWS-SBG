import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Play,
  Pause,
  RotateCcw,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  Clock,
  Eye,
  Search,
  ExternalLink
} from 'lucide-react'
import { apiClient } from '../config/api'
import { PIPELINE_STAGES, getConfidenceLevel } from '../utils/constants'
import {
  formatDate,
  getSeverityFromFaultClass
} from '../utils/helpers'

// Stage reveal sequence: what becomes visible at each step
const STAGE_LABELS = [
  'Detect',
  'Collect',
  'Diagnose',
  'Approve',
  'Remediate',
  'Verify'
]

const SPEED_OPTIONS = [
  { label: '1s', value: 1000 },
  { label: '3s', value: 3000 },
  { label: '5s', value: 5000 }
]

export default function ReplayMode() {
  const { incidentId: routeIncidentId } = useParams()
  const navigate = useNavigate()

  const [incidents, setIncidents] = useState([])
  const [selectedId, setSelectedId] = useState(routeIncidentId || '')
  const [incident, setIncident] = useState(null)
  const [rawData, setRawData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [listLoading, setListLoading] = useState(true)
  const [error, setError] = useState(null)

  // Replay state
  const [currentStage, setCurrentStage] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [speed, setSpeed] = useState(3000)
  const timerRef = useRef(null)

  // Evidence tab state
  const [activeTab, setActiveTab] = useState('metrics')
  const [expandedStages, setExpandedStages] = useState({})

  // Fetch incidents list
  useEffect(() => {
    const fetchIncidents = async () => {
      try {
        setListLoading(true)
        const data = await apiClient.getIncidents({ limit: 100 })
        setIncidents(data.incidents || [])
      } catch (err) {
        console.error('Failed to fetch incidents:', err)
      } finally {
        setListLoading(false)
      }
    }
    fetchIncidents()
  }, [])

  // Load incident detail when selected
  useEffect(() => {
    if (!selectedId) return

    const fetchDetail = async () => {
      try {
        setLoading(true)
        setError(null)
        const data = await apiClient.getIncidentDetail(selectedId)
        setIncident(data.incident)
        setRawData(data.raw_data)
        setCurrentStage(0)
        setIsPlaying(false)
      } catch (err) {
        console.error('Failed to fetch incident detail:', err)
        setError('Failed to load incident details')
        setIncident(null)
        setRawData(null)
      } finally {
        setLoading(false)
      }
    }
    fetchDetail()
  }, [selectedId])

  // Auto-load from route param
  useEffect(() => {
    if (routeIncidentId && routeIncidentId !== selectedId) {
      setSelectedId(routeIncidentId)
    }
  }, [routeIncidentId])

  // Play/pause timer
  useEffect(() => {
    if (isPlaying && incident) {
      timerRef.current = setInterval(() => {
        setCurrentStage(prev => {
          if (prev >= 5) {
            setIsPlaying(false)
            return 5
          }
          return prev + 1
        })
      }, speed)
    }

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
  }, [isPlaying, speed, incident])

  // Stop playing if we reached the end
  useEffect(() => {
    if (currentStage >= 5) {
      setIsPlaying(false)
    }
  }, [currentStage])

  const handlePlay = useCallback(() => {
    if (currentStage >= 5) {
      setCurrentStage(0)
    }
    setIsPlaying(true)
  }, [currentStage])

  const handlePause = useCallback(() => {
    setIsPlaying(false)
  }, [])

  const handleReset = useCallback(() => {
    setIsPlaying(false)
    setCurrentStage(0)
  }, [])

  const handleSelectIncident = (id) => {
    setSelectedId(id)
    navigate(`/replay/${id}`, { replace: true })
  }

  const toggleStageExpansion = (stageKey) => {
    setExpandedStages(prev => ({
      ...prev,
      [stageKey]: !prev[stageKey]
    }))
  }

  // If no incident selected, show picker
  if (!selectedId || !incident) {
    return (
      <div className="space-y-6">
        <div className="card p-6">
          <h1 className="text-lg font-semibold text-text-primary mb-1">Replay Mode</h1>
          <p className="text-sm text-text-secondary">
            Step through a past incident's pipeline stages at a controlled pace.
          </p>
        </div>

        <IncidentPicker
          incidents={incidents}
          loading={listLoading}
          loadError={error}
          onSelect={handleSelectIncident}
          detailLoading={loading}
        />
      </div>
    )
  }

  if (loading) {
    return <ReplayModeSkeleton />
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="card text-center py-12">
          <AlertTriangle className="mx-auto h-12 w-12 text-crimson mb-4" />
          <h3 className="text-lg font-medium text-text-primary mb-2">{error}</h3>
          <button onClick={() => setSelectedId('')} className="btn-primary">
            Choose Another Incident
          </button>
        </div>
      </div>
    )
  }

  const severity = getSeverityFromFaultClass(incident.fault_class)

  return (
    <div className="space-y-6">
      {/* Replay Header & Controls */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-lg font-semibold text-text-primary mb-1">Replay Mode</h1>
            <div className="flex items-center space-x-3 text-sm text-text-secondary">
              <span className="mono">{incident.incident_id}</span>
              <span>•</span>
              <span className="capitalize">{incident.fault_class?.replace(/_/g, ' ')}</span>
            </div>
          </div>
          <button
            onClick={() => {
              setSelectedId('')
              setIncident(null)
              navigate('/replay', { replace: true })
            }}
            className="btn-ghost"
          >
            Change Incident
          </button>
        </div>

        <ReplayControls
          currentStage={currentStage}
          isPlaying={isPlaying}
          speed={speed}
          onPlay={handlePlay}
          onPause={handlePause}
          onReset={handleReset}
          onSpeedChange={setSpeed}
          onStageClick={setCurrentStage}
        />
      </div>

      {/* Frozen Detail View */}
      <ReplayStageView
        incident={incident}
        rawData={rawData}
        currentStage={currentStage}
        severity={severity}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        expandedStages={expandedStages}
        onToggleStage={toggleStageExpansion}
      />
    </div>
  )
}

// --- IncidentPicker ---
function IncidentPicker({ incidents, loading, loadError, onSelect, detailLoading }) {
  const [searchTerm, setSearchTerm] = useState('')

  const filtered = incidents.filter(inc => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      inc.incident_id?.toLowerCase().includes(term) ||
      inc.fault_class?.toLowerCase().includes(term) ||
      inc.diagnosis?.root_cause?.toLowerCase().includes(term)
    )
  })

  if (loading) {
    return (
      <div className="card">
        <div className="pulse-loading h-4 w-40 mb-4"></div>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="pulse-loading h-12 w-full mb-2 rounded-card"></div>
        ))}
      </div>
    )
  }

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-4">Select an Incident</h3>

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
        <input
          type="text"
          placeholder="Search by ID, fault class, or root cause..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full pl-9 pr-4 py-2 bg-bg-input border border-border-default rounded-button text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-border-strong"
        />
      </div>

      {/* Incident List */}
      {filtered.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-sm text-text-secondary">
            {incidents.length === 0 ? 'No incidents found' : 'No matching incidents'}
          </p>
        </div>
      ) : (
        <div className="space-y-1 max-h-96 overflow-y-auto">
          {filtered.map(inc => {
            const severity = getSeverityFromFaultClass(inc.fault_class)
            return (
              <button
                key={inc.incident_id}
                onClick={() => onSelect(inc.incident_id)}
                disabled={detailLoading}
                className="w-full text-left p-3 rounded-card border border-border-subtle hover:border-border-default hover:bg-bg-elevated transition-colors duration-75 flex items-center justify-between group"
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <span className={`badge ${severity === 'critical' ? 'badge-critical' : 'badge-warning'} flex-shrink-0`}>
                    {severity === 'critical' ? 'Crit' : 'Warn'}
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm text-text-primary truncate">
                      {inc.diagnosis?.root_cause || 'Investigating...'}
                    </div>
                    <div className="text-xs text-text-muted mono truncate">
                      {inc.incident_id}
                    </div>
                  </div>
                </div>
                <div className="text-xs text-text-muted flex-shrink-0 ml-2">
                  {formatDate(inc.detected_at)}
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

// --- ReplayControls ---
function ReplayControls({ currentStage, isPlaying, speed, onPlay, onPause, onReset, onSpeedChange, onStageClick }) {
  return (
    <div className="space-y-4">
      {/* Controls Row */}
      <div className="flex items-center space-x-3">
        {isPlaying ? (
          <button onClick={onPause} className="btn-ghost flex items-center" title="Pause">
            <Pause className="w-4 h-4 mr-1" />
            Pause
          </button>
        ) : (
          <button onClick={onPlay} className="btn-primary flex items-center" title="Play">
            <Play className="w-4 h-4 mr-1" />
            Play
          </button>
        )}

        <button onClick={onReset} className="btn-ghost flex items-center" title="Reset to stage 1">
          <RotateCcw className="w-4 h-4 mr-1" />
          Reset
        </button>

        <div className="flex items-center space-x-2 ml-auto">
          <label className="text-xs text-text-secondary">Speed:</label>
          <select
            value={speed}
            onChange={(e) => onSpeedChange(Number(e.target.value))}
            className="bg-bg-input border border-border-default rounded-button px-2 py-1 text-xs text-text-primary focus:outline-none focus:border-border-strong"
          >
            {SPEED_OPTIONS.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Stage Progress Bar */}
      <div className="flex items-center space-x-1">
        {STAGE_LABELS.map((label, index) => {
          const isComplete = index < currentStage
          const isCurrent = index === currentStage
          const isFuture = index > currentStage

          return (
            <button
              key={label}
              onClick={() => {
                onStageClick(index)
              }}
              className={`flex-1 flex flex-col items-center py-2 px-1 rounded-card transition-colors duration-75 ${
                isCurrent
                  ? 'bg-bg-elevated border border-border-strong'
                  : 'border border-transparent hover:bg-bg-elevated'
              }`}
              title={`Jump to stage ${index + 1}: ${label}`}
            >
              {/* Dot */}
              <div className={`w-3 h-3 rounded-full mb-1 flex items-center justify-center ${
                isComplete
                  ? 'bg-emerald'
                  : isCurrent
                  ? 'bg-amber animate-pulse'
                  : 'border border-border-default bg-bg-base'
              }`}>
                {isComplete && <CheckCircle className="w-2 h-2 text-white" />}
              </div>
              {/* Label */}
              <span className={`text-xs ${
                isCurrent ? 'text-text-primary font-medium' : isComplete ? 'text-emerald' : 'text-text-muted'
              }`}>
                {label}
              </span>
            </button>
          )
        })}
      </div>

      {/* Progress text */}
      <div className="text-xs text-text-muted text-center">
        Stage {currentStage + 1} of 6 — {STAGE_LABELS[currentStage]}
      </div>
    </div>
  )
}

// --- ReplayStageView ---
function ReplayStageView({ incident, rawData, currentStage, severity, activeTab, onTabChange, expandedStages, onToggleStage }) {
  return (
    <div className="space-y-6">
      {/* Incident Header — always visible (stage >= 0) */}
      <ReplayHeader incident={incident} severity={severity} currentStage={currentStage} />

      {/* Main Content - 3 Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column - Lifecycle Timeline (30%) */}
        <div className="lg:col-span-4">
          <FrozenLifecycleTimeline
            incident={incident}
            currentStage={currentStage}
            expandedStages={expandedStages}
            onToggleStage={onToggleStage}
          />
        </div>

        {/* Center Column - AI Diagnosis & Evidence (45%) */}
        <div className="lg:col-span-5 space-y-6">
          {/* DiagnosisPanel — visible at stage >= 2 (Diagnose) */}
          {currentStage >= 2 ? (
            <FrozenDiagnosisPanel incident={incident} />
          ) : (
            <div className="card">
              <h3 className="text-sm font-medium text-text-primary mb-6">AI Diagnosis</h3>
              <div className="text-center py-8">
                <Clock className="mx-auto w-8 h-8 text-text-muted mb-3" />
                <p className="text-sm text-text-secondary">Not Started</p>
              </div>
            </div>
          )}

          {/* EvidenceExplorer — visible at stage >= 1 (Collect) */}
          {currentStage >= 1 ? (
            <FrozenEvidenceExplorer
              rawData={rawData}
              activeTab={activeTab}
              onTabChange={onTabChange}
            />
          ) : (
            <div className="card">
              <h3 className="text-sm font-medium text-text-primary mb-4">Evidence Explorer</h3>
              <div className="text-center py-8">
                <Eye className="mx-auto w-8 h-8 text-text-muted mb-3" />
                <p className="text-sm text-text-secondary">Not Started</p>
              </div>
            </div>
          )}
        </div>

        {/* Right Column - Approval & Verification (25%) */}
        <div className="lg:col-span-3 space-y-6">
          {/* ApprovalCard — visible at stage >= 3 (Approve) */}
          {currentStage >= 3 ? (
            <FrozenApprovalCard incident={incident} currentStage={currentStage} />
          ) : (
            <div className="card">
              <h3 className="text-sm font-medium text-text-primary mb-4">Approval</h3>
              <div className="text-center py-6">
                <Clock className="mx-auto w-6 h-6 text-text-muted mb-2" />
                <p className="text-xs text-text-secondary">Not Started</p>
              </div>
            </div>
          )}

          {/* VerificationCard — visible at stage >= 5 (Verify) */}
          {currentStage >= 5 ? (
            <FrozenVerificationCard incident={incident} />
          ) : (
            <div className="card">
              <h3 className="text-sm font-medium text-text-primary mb-4">Verification</h3>
              <div className="text-center py-6">
                <Clock className="mx-auto w-6 h-6 text-text-muted mb-2" />
                <p className="text-xs text-text-secondary">Not Started</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// --- Frozen sub-components ---

function ReplayHeader({ incident, severity, currentStage }) {
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <span className={`badge ${severity === 'critical' ? 'badge-critical' : 'badge-warning'}`}>
            {severity === 'critical' ? 'Critical' : 'Warning'}
          </span>
          <div>
            <h1 className="text-xl font-semibold text-text-primary">
              {currentStage >= 2
                ? (incident.diagnosis?.root_cause || 'Investigating Incident')
                : 'Investigating Incident'}
            </h1>
            <div className="flex items-center space-x-4 mt-1 text-sm text-text-secondary">
              <span className="mono">{incident.incident_id}</span>
              <span>•</span>
              <span>Detected {formatDate(incident.detected_at, 'relative')}</span>
              <span>•</span>
              <span className="capitalize">{incident.fault_class?.replace(/_/g, ' ')}</span>
            </div>
          </div>
        </div>

        <span className="badge badge-info">
          {STAGE_LABELS[currentStage]}
        </span>
      </div>
    </div>
  )
}

function FrozenLifecycleTimeline({ incident, currentStage, expandedStages, onToggleStage }) {
  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-6">Incident Lifecycle</h3>

      <div className="space-y-4">
        {PIPELINE_STAGES.map((stage, index) => {
          // Determine frozen status based on currentStage
          let stageStatus
          if (index < currentStage) {
            stageStatus = 'complete'
          } else if (index === currentStage) {
            stageStatus = 'in_progress'
          } else {
            stageStatus = 'not_started'
          }

          const isExpanded = expandedStages[stage.key]
          const hasDetails = index <= currentStage && getFrozenStageDetails(incident, stage.key, currentStage)

          return (
            <div key={stage.key} className="flex space-x-3">
              {/* Status Icon */}
              <div className="flex flex-col items-center">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center ${getFrozenStageIconStyle(stageStatus)}`}>
                  {getFrozenStageIcon(stageStatus)}
                </div>
                {index < PIPELINE_STAGES.length - 1 && (
                  <div className={`w-px h-8 mt-2 ${
                    stageStatus === 'not_started' ? 'border-l border-dashed border-border-subtle' : 'bg-border-subtle'
                  }`} />
                )}
              </div>

              {/* Stage Content */}
              <div className="flex-1 pb-6">
                <div
                  className={`flex items-center justify-between ${hasDetails ? 'cursor-pointer' : ''}`}
                  onClick={hasDetails ? () => onToggleStage(stage.key) : undefined}
                >
                  <div>
                    <div className="text-sm font-medium text-text-primary">
                      {stage.label}
                    </div>
                    <div className="text-xs text-text-muted mono">
                      {index <= currentStage
                        ? getFrozenStageTimestamp(incident, stage.key, currentStage)
                        : ''}
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
                    <FrozenStageDetailsContent incident={incident} stage={stage.key} />
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

function FrozenDiagnosisPanel({ incident }) {
  const diagnosis = incident.diagnosis || {}
  const confidence = getConfidenceLevel(diagnosis.confidence || 0)

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-6">AI Diagnosis</h3>

      {diagnosis.root_cause ? (
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
              <p className="text-sm text-text-primary mt-1 mono">
                {diagnosis.suggested_action.replace(/_/g, ' ')}
              </p>
            </div>
          )}

          {diagnosis.reasoning_trace && (
            <div>
              <label className="text-xs text-text-secondary uppercase tracking-wide">Reasoning Trace</label>
              <div className="mt-2 p-3 bg-bg-input rounded-card">
                <pre className="text-xs text-text-code font-mono whitespace-pre-wrap">
                  {diagnosis.reasoning_trace}
                </pre>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-8">
          <Clock className="mx-auto w-8 h-8 text-text-muted mb-3" />
          <p className="text-sm text-text-secondary">Diagnosis in progress...</p>
        </div>
      )}
    </div>
  )
}

function FrozenEvidenceExplorer({ rawData, activeTab, onTabChange }) {
  const tabs = ['metrics', 'logs', 'xray', 'json']

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
                ? 'bg-bg-surface text-text-primary'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="bg-bg-input rounded-card p-4 min-h-48">
        {rawData ? (
          <FrozenEvidenceTabContent tab={activeTab} data={rawData} />
        ) : (
          <div className="text-center py-12">
            <Eye className="mx-auto w-8 h-8 text-text-muted mb-3" />
            <p className="text-sm text-text-secondary">No evidence data available</p>
          </div>
        )}
      </div>
    </div>
  )
}

function FrozenEvidenceTabContent({ tab, data }) {
  switch (tab) {
    case 'json':
      return (
        <pre className="text-xs text-text-code font-mono whitespace-pre-wrap overflow-auto">
          {JSON.stringify(data, null, 2)}
        </pre>
      )
    case 'metrics':
      return (
        <div className="text-xs text-text-secondary">
          <p>CloudWatch metrics and alarm data would be displayed here</p>
        </div>
      )
    case 'logs':
      return (
        <div className="text-xs text-text-secondary">
          <p>Log entries would be displayed here</p>
        </div>
      )
    case 'xray':
      return (
        <div className="text-xs text-text-secondary">
          <p>X-Ray trace data would be displayed here</p>
        </div>
      )
    default:
      return null
  }
}

function FrozenApprovalCard({ incident, currentStage }) {
  const remediation = incident.remediation || {}

  // At stage 3 (Approve), show pending state regardless of actual status
  if (currentStage === 3) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium text-text-primary mb-4">Approval</h3>
        <div className="space-y-4">
          <div className="p-3 bg-amber-surface rounded-card border border-amber/20">
            <p className="text-xs text-amber">Awaiting manual approval</p>
          </div>
          <div className="space-y-2">
            <button className="btn-danger w-full opacity-40 cursor-not-allowed" disabled>
              Approve Remediation
            </button>
            <button className="btn-ghost w-full opacity-40 cursor-not-allowed" disabled>
              Reject
            </button>
          </div>
          <p className="text-xs text-text-muted text-center">
            Approval actions are disabled in replay mode.
          </p>
        </div>
      </div>
    )
  }

  // Stage 4+ (Remediate/Verify) — show approved & executed
  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-4">Approval</h3>
      <div className="text-center py-6">
        <div className="w-8 h-8 rounded-full mx-auto mb-2 flex items-center justify-center bg-emerald-surface">
          <CheckCircle className="w-4 h-4 text-emerald" />
        </div>
        <p className="text-xs text-text-secondary">
          {currentStage >= 4 ? 'Approved & Executed' : 'Approved'}
        </p>
      </div>
    </div>
  )
}

function FrozenVerificationCard({ incident }) {
  const verification = incident.verification || {}

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-text-primary mb-4">Verification</h3>

      {verification.status ? (
        <div className="space-y-3">
          <div className={`p-3 rounded-card border ${
            verification.status === 'resolved'
              ? 'bg-emerald-surface border-emerald/20'
              : verification.status === 'not_resolved'
              ? 'bg-crimson-surface border-crimson/20'
              : 'bg-amber-surface border-amber/20'
          }`}>
            <p className={`text-xs ${
              verification.status === 'resolved' ? 'text-emerald' :
              verification.status === 'not_resolved' ? 'text-crimson' : 'text-amber'
            }`}>
              Signal check: {verification.status.replace(/_/g, ' ')}
            </p>
          </div>

          {verification.checked_at && (
            <p className="text-xs text-text-muted mono">
              Verified {formatDate(verification.checked_at, 'relative')}
            </p>
          )}

          {verification.notes && (
            <p className="text-xs text-text-secondary">
              {verification.notes}
            </p>
          )}
        </div>
      ) : (
        <div className="text-center py-6">
          <CheckCircle className="mx-auto w-6 h-6 text-emerald mb-2" />
          <p className="text-xs text-text-secondary">Verification complete</p>
        </div>
      )}
    </div>
  )
}

// --- Frozen timeline helpers ---

function getFrozenStageIconStyle(status) {
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

function getFrozenStageIcon(status) {
  switch (status) {
    case 'complete':
      return <CheckCircle className="w-3 h-3" />
    case 'in_progress':
      return <div className="w-2 h-2 bg-white rounded-full" />
    default:
      return <div className="w-2 h-2 border border-text-muted rounded-full" />
  }
}

function getFrozenStageTimestamp(incident, stage, currentStage) {
  switch (stage) {
    case 'detected':
      return incident.detected_at ? formatDate(incident.detected_at) : ''
    case 'evidence_collected':
      return currentStage >= 1 ? 'Completed' : ''
    case 'diagnosed':
      return currentStage >= 2 && incident.diagnosis?.root_cause ? 'Completed' : ''
    case 'pending_approval':
      return currentStage >= 3 ? (currentStage === 3 ? 'Pending' : 'Approved') : ''
    case 'executed':
      return currentStage >= 4 ? (incident.remediation?.executed_at ? formatDate(incident.remediation.executed_at) : 'Executed') : ''
    case 'verified':
      return currentStage >= 5 ? (incident.verification?.checked_at ? formatDate(incident.verification.checked_at) : 'Verified') : ''
    default:
      return ''
  }
}

function getFrozenStageDetails(incident, stage, currentStage) {
  switch (stage) {
    case 'diagnosed':
      return currentStage >= 2 && incident.diagnosis?.root_cause
    case 'executed':
      return currentStage >= 4 && incident.remediation?.action_taken
    case 'verified':
      return currentStage >= 5 && incident.verification?.notes
    default:
      return false
  }
}

function FrozenStageDetailsContent({ incident, stage }) {
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

// --- Skeleton ---
function ReplayModeSkeleton() {
  return (
    <div className="space-y-6">
      <div className="card p-6">
        <div className="pulse-loading h-6 w-40 mb-2"></div>
        <div className="pulse-loading h-4 w-64 mb-4"></div>
        <div className="pulse-loading h-10 w-full rounded-card"></div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-4">
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

        <div className="lg:col-span-5 space-y-6">
          <div className="card">
            <div className="pulse-loading h-4 w-24 mb-6"></div>
            <div className="pulse-loading h-20 w-full"></div>
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
