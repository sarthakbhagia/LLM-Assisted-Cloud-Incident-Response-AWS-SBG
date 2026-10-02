import { useState, useEffect } from 'react'
import { AlertTriangle, RefreshCw, Info } from 'lucide-react'
import { apiClient } from '../config/api'
import { POLLING_INTERVALS } from '../utils/constants'
import { getIncidentStatus } from '../utils/helpers'

// Static layout coordinates for known services (only x/y positions, not topology)
const SERVICE_LAYOUT = {
  'service-a': { x: 80, y: 160 },
  'service-b': { x: 320, y: 160 },
  'service-c': { x: 560, y: 160 },
}

const NODE_W = 160
const NODE_H = 72

export default function ServiceMap() {
  const [incidents, setIncidents] = useState([])
  const [servicesData, setServicesData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = async () => {
    try {
      const [incidentsRes, servicesRes] = await Promise.all([
        apiClient.getIncidents({ limit: 50 }),
        apiClient.getServices()
      ])
      setIncidents(incidentsRes?.items || [])
      setServicesData(servicesRes)
      setError(null)
    } catch (err) {
      console.error('Failed to fetch data for service map:', err)
      setError('Could not load service health data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, POLLING_INTERVALS.INCIDENTS_FEED)
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
  const getNodeIncidents = (serviceName) => {
    const serviceInfo = servicesData?.services?.find(s => s.name === serviceName)
    if (!serviceInfo) return []
    // Match incidents by resource_id patterns or fault class
    return Object.entries(activeIncidentsByResource)
      .filter(([key]) => {
        // Defensive: skip undefined/null keys
        if (!key || typeof key !== 'string') return false
        const resourceLower = key.toLowerCase()
        const serviceLabel = serviceName.toLowerCase()
        // Match by service name in resource_id (e.g., "service-a", "service-a-errors")
        if (resourceLower.includes(serviceLabel)) return true
        // Match by fault class association using outputs field
        const incidentFaultClasses = activeIncidentsByResource[key].map(i => i.fault_class)
        const serviceOutputs = serviceInfo.outputs || []
        return serviceOutputs.some(fc => incidentFaultClasses.includes(fc))
      })
      .flatMap(([, incs]) => incs)
  }

  // Build topology from API response + static layout
  const services = servicesData?.services || []
  const topology = services.map(svc => ({
    ...svc,
    ...SERVICE_LAYOUT[svc.id],
    description: svc.role || 'Lambda function',
  }))

  // Build SVG edges from outputs (derived from fault_classes or static knowledge)
  const edges = []
  topology.forEach(node => {
    // Determine downstream services based on fault class dependencies
    const downstream = topology.filter(target => 
      node.id === 'service-a' && target.id === 'service-b' ||
      node.id === 'service-b' && target.id === 'service-c'
    )
    downstream.forEach(target => {
      const x1 = node.x + NODE_W
      const y1 = node.y + NODE_H / 2
      const x2 = target.x
      const y2 = target.y + NODE_H / 2
      edges.push({ x1, y1, x2, y2, key: `${node.id}-${target.id}` })
    })
  })

  const svgWidth = 760
  const svgHeight = 320

  if (loading && !servicesData) {
    return (
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-lg font-semibold text-text-primary">Service Map</h1>
            <p className="text-xs text-text-muted mt-0.5">Loading live topology...</p>
          </div>
        </div>
        <div className="card p-6 overflow-x-auto">
          <svg width={svgWidth} height={svgHeight} viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full" style={{ minWidth: 640 }}>
            {Object.entries(SERVICE_LAYOUT).map(([name, pos]) => (
              <g key={name}>
                <rect x={pos.x} y={pos.y} width={NODE_W} height={NODE_H} rx={6} fill="#111113" stroke="#2A2A2D" />
                <text x={pos.x + NODE_W / 2} y={pos.y + 26} textAnchor="middle" fill="#55555D" fontSize={13} fontFamily="Inter" fontWeight={600}>Loading...</text>
              </g>
            ))}
          </svg>
        </div>
      </div>
    )
  }

  if (error && !servicesData) {
    return (
      <div className="space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-lg font-semibold text-text-primary">Service Map</h1>
            <p className="text-xs text-text-muted mt-0.5">Live health topology and active incident overlays for microservices</p>
          </div>
          <button onClick={fetchData} className="btn-ghost" title="Refresh">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        <div className="flex items-center space-x-2 p-3 bg-crimson-surface border border-crimson/20 rounded-card">
          <AlertTriangle className="w-4 h-4 text-crimson flex-shrink-0" />
          <p className="text-xs text-crimson">{error}</p>
        </div>
        <div className="card p-6 text-center">
          <p className="text-sm text-text-secondary">Unable to load service topology from backend.</p>
          <button onClick={fetchData} className="btn-primary mt-4">
            <RefreshCw className="w-4 h-4 mr-2" /> Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Service Map</h1>
          <p className="text-xs text-text-muted mt-0.5">
            Live health topology and active incident overlays for microservices
          </p>
        </div>
        <button onClick={fetchData} className="btn-ghost" title="Refresh">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && (
        <div className="flex items-center space-x-2 p-3 bg-amber-surface border border-amber/20 rounded-card">
          <AlertTriangle className="w-4 h-4 text-amber flex-shrink-0" />
          <p className="text-xs text-amber">{error} — showing cached data</p>
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
{topology.map(node => {
            const nodeIncidents = getNodeIncidents(node.id)
            const hasCritical = nodeIncidents.length > 0
            const borderColor = hasCritical ? '#D63C4B' : '#2A2A2D'
            const glowStyle = hasCritical ? { filter: 'drop-shadow(0 0 6px rgba(214,60,75,0.35))' } : {}

            // Get health status from API response
            const healthStatus = node.health?.status || 'unknown'
            const isHealthy = healthStatus === 'ok' || healthStatus === 'healthy'

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
                  fill={hasCritical ? '#D63C4B' : (isHealthy ? '#46B887' : '#D63C4B')}
                />
                <text
                  x={node.x + NODE_W / 2 + 8}
                  y={node.y + 62}
                  fill={hasCritical ? '#D63C4B' : (isHealthy ? '#46B887' : '#D63C4B')}
                  fontSize={9}
                  fontFamily="Inter, system-ui, sans-serif"
                >
                  {hasCritical 
                    ? `${nodeIncidents.length} active incident${nodeIncidents.length > 1 ? 's' : ''}` 
                    : (isHealthy ? 'Healthy' : 'Unhealthy')
                  }
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

                {/* Latency indicator if available */}
                {node.health?.latency_ms != null && (
                  <text
                    x={node.x + 8}
                    y={node.y + NODE_H - 8}
                    fill="#85858C"
                    fontSize={8}
                    fontFamily="JetBrains Mono, monospace"
                  >
                    {node.health.latency_ms}ms
                  </text>
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
