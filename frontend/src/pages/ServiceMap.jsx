import { useState, useEffect } from 'react'
import { AlertTriangle, RefreshCw, Info } from 'lucide-react'
import { apiClient } from '../config/api'
import { POLLING_INTERVALS } from '../utils/constants'
import { getIncidentStatus } from '../utils/helpers'

// Known service topology (static until backend /api/services endpoint is available)
const SERVICE_TOPOLOGY = [
  {
    id: 'service-a',
    label: 'Service A',
    description: 'Entry point Lambda',
    x: 80, y: 160,
    outputs: ['service-b'],
  },
  {
    id: 'service-b',
    label: 'Service B',
    description: 'Processing Lambda',
    x: 320, y: 160,
    outputs: ['service-c'],
  },
  {
    id: 'service-c',
    label: 'Service C',
    description: 'Downstream Lambda',
    x: 560, y: 160,
    outputs: [],
  },
]

const NODE_W = 160
const NODE_H = 72

export default function ServiceMap() {
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchIncidents = async () => {
    try {
      const data = await apiClient.getIncidents({ limit: 50 })
      setIncidents(data?.items || [])
      setError(null)
    } catch (err) {
      console.error('Failed to fetch incidents for service map:', err)
      setError('Could not load incident overlays')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchIncidents()
    const interval = setInterval(fetchIncidents, POLLING_INTERVALS.INCIDENTS_FEED)
    return () => clearInterval(interval)
  }, [])

  // Build a map: resource_id → active incidents
  const activeIncidentsByResource = {}
  incidents.forEach(inc => {
    const status = getIncidentStatus(inc)
    const isActive = !['resolved'].includes(status.status)
    if (!isActive) return
    const key = (inc.resource_id || '').toLowerCase()
    if (!activeIncidentsByResource[key]) activeIncidentsByResource[key] = []
    activeIncidentsByResource[key].push(inc)
  })

  // Determine if a service node has an active incident
  const getNodeIncidents = (serviceId) => {
    const label = SERVICE_TOPOLOGY.find(s => s.id === serviceId)?.label?.toLowerCase() || ''
    return Object.entries(activeIncidentsByResource)
      .filter(([key]) => key.includes(label.replace('service ', 'service').toLowerCase()))
      .flatMap(([, incs]) => incs)
  }

  // Build SVG edges
  const edges = []
  SERVICE_TOPOLOGY.forEach(node => {
    node.outputs.forEach(targetId => {
      const target = SERVICE_TOPOLOGY.find(s => s.id === targetId)
      if (!target) return
      const x1 = node.x + NODE_W
      const y1 = node.y + NODE_H / 2
      const x2 = target.x
      const y2 = target.y + NODE_H / 2
      edges.push({ x1, y1, x2, y2, key: `${node.id}-${targetId}` })
    })
  })

  const svgWidth = 760
  const svgHeight = 320

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Service Map</h1>
          <p className="text-xs text-text-muted mt-0.5">
            Static topology of the three known Lambda services
          </p>
        </div>
        <button onClick={fetchIncidents} className="btn-ghost" title="Refresh">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Backend notice */}
      <div className="flex items-start space-x-2 p-3 bg-amber-surface border border-amber/20 rounded-card">
        <Info className="w-4 h-4 text-amber flex-shrink-0 mt-0.5" />
        <p className="text-xs text-text-secondary">
          Live service health data requires the <span className="mono text-text-primary">GET /api/services</span> endpoint
          (additional backend work — see <span className="mono text-text-primary">BACKEND_SPEC.md</span>).
          This diagram shows a static topology with active incident overlays only.
        </p>
      </div>

      {error && (
        <div className="flex items-center space-x-2 p-3 bg-crimson-surface border border-crimson/20 rounded-card">
          <AlertTriangle className="w-4 h-4 text-crimson flex-shrink-0" />
          <p className="text-xs text-crimson">{error}</p>
        </div>
      )}

      {/* Map canvas */}
      <div className="card p-6 overflow-x-auto">
        <svg
          width={svgWidth}
          height={svgHeight}
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full"
          style={{ minWidth: 640 }}
        >
          {/* Arrow marker */}
          <defs>
            <marker
              id="arrowhead"
              markerWidth="8"
              markerHeight="6"
              refX="8"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 8 3, 0 6" fill="#3A3A3E" />
            </marker>
          </defs>

          {/* Edges */}
          {edges.map(e => (
            <line
              key={e.key}
              x1={e.x1}
              y1={e.y1}
              x2={e.x2}
              y2={e.y2}
              stroke="#3A3A3E"
              strokeWidth={2}
              markerEnd="url(#arrowhead)"
            />
          ))}

          {/* Nodes */}
          {SERVICE_TOPOLOGY.map(node => {
            const nodeIncidents = getNodeIncidents(node.id)
            const hasCritical = nodeIncidents.length > 0
            const borderColor = hasCritical ? '#D63C4B' : '#2A2A2D'
            const glowStyle = hasCritical ? { filter: 'drop-shadow(0 0 6px rgba(214,60,75,0.35))' } : {}

            return (
              <g key={node.id} style={glowStyle}>
                {/* Card background */}
                <rect
                  x={node.x}
                  y={node.y}
                  width={NODE_W}
                  height={NODE_H}
                  rx={6}
                  fill="#111113"
                  stroke={borderColor}
                  strokeWidth={hasCritical ? 1.5 : 1}
                />

                {/* Service label */}
                <text
                  x={node.x + NODE_W / 2}
                  y={node.y + 26}
                  textAnchor="middle"
                  fill="#F2F2F2"
                  fontSize={13}
                  fontFamily="Inter, system-ui, sans-serif"
                  fontWeight={600}
                >
                  {node.label}
                </text>

                {/* Description */}
                <text
                  x={node.x + NODE_W / 2}
                  y={node.y + 43}
                  textAnchor="middle"
                  fill="#55555D"
                  fontSize={10}
                  fontFamily="Inter, system-ui, sans-serif"
                >
                  {node.description}
                </text>

                {/* Status dot */}
                <circle
                  cx={node.x + NODE_W / 2}
                  cy={node.y + 58}
                  r={4}
                  fill={hasCritical ? '#D63C4B' : '#46B887'}
                />
                <text
                  x={node.x + NODE_W / 2 + 8}
                  y={node.y + 62}
                  fill={hasCritical ? '#D63C4B' : '#46B887'}
                  fontSize={9}
                  fontFamily="Inter, system-ui, sans-serif"
                >
                  {hasCritical ? `${nodeIncidents.length} active incident${nodeIncidents.length > 1 ? 's' : ''}` : 'Healthy'}
                </text>

                {/* Warning badge for active incidents */}
                {hasCritical && (
                  <g>
                    <circle cx={node.x + NODE_W - 10} cy={node.y + 10} r={9} fill="#321419" stroke="#D63C4B" strokeWidth={1} />
                    <text
                      x={node.x + NODE_W - 10}
                      y={node.y + 14}
                      textAnchor="middle"
                      fill="#D63C4B"
                      fontSize={9}
                      fontFamily="Inter, system-ui, sans-serif"
                      fontWeight={700}
                    >
                      !
                    </text>
                  </g>
                )}
              </g>
            )
          })}

          {/* Legend */}
          <g transform={`translate(${svgWidth - 180}, ${svgHeight - 70})`}>
            <rect x={0} y={0} width={170} height={60} rx={4} fill="#111113" stroke="#2A2A2D" />
            <circle cx={16} cy={18} r={5} fill="#46B887" />
            <text x={28} y={22} fill="#85858C" fontSize={10} fontFamily="Inter, system-ui, sans-serif">Healthy — no active incidents</text>
            <circle cx={16} cy={40} r={5} fill="#D63C4B" />
            <text x={28} y={44} fill="#85858C" fontSize={10} fontFamily="Inter, system-ui, sans-serif">Active incident detected</text>
          </g>
        </svg>
      </div>

      {/* Active Incidents Table */}
      {incidents.filter(inc => {
        const s = getIncidentStatus(inc)
        return s.status !== 'resolved'
      }).length > 0 && (
        <div className="card">
          <h3 className="text-sm font-medium text-text-primary mb-4">Active Incidents</h3>
          <div className="space-y-2">
            {incidents
              .filter(inc => getIncidentStatus(inc).status !== 'resolved')
              .slice(0, 5)
              .map(inc => {
                const s = getIncidentStatus(inc)
                return (
                  <div key={inc.incident_id} className="flex items-center justify-between p-2.5 bg-bg-elevated rounded">
                    <div className="flex items-center space-x-3">
                      <div className="w-2 h-2 rounded-full bg-crimson"></div>
                      <div>
                        <p className="text-xs text-text-primary mono">{inc.incident_id?.substring(0, 8)}</p>
                        <p className="text-xs text-text-muted">{inc.fault_class?.replace(/_/g, ' ')} — {inc.resource_id || '—'}</p>
                      </div>
                    </div>
                    <span className={`badge badge-warning`}>{s.label}</span>
                  </div>
                )
              })}
          </div>
        </div>
      )}
    </div>
  )
}
