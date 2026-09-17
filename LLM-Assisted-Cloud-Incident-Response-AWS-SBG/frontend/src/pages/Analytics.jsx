import { useState, useEffect } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  LineChart, Line, ScatterChart, Scatter, ZAxis,
  ResponsiveContainer, ReferenceLine
} from 'recharts'
import { apiClient } from '../config/api'
import { POLLING_INTERVALS, FAULT_CLASS_LABELS } from '../utils/constants'
import { formatMTTR } from '../utils/helpers'

// Obsidian palette for charts
const CHART_COLORS = {
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

const CUSTOM_TOOLTIP_STYLE = {
  backgroundColor: CHART_COLORS.tooltip,
  border: `1px solid ${CHART_COLORS.tooltipBorder}`,
  borderRadius: '6px',
  padding: '12px',
  fontSize: '11px',
  fontFamily: 'JetBrains Mono, monospace',
  color: CHART_COLORS.primary,
}

export default function Analytics() {
  const [results, setResults] = useState(null)
  const [incidents, setIncidents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = async () => {
    try {
      const [analyticsData, incidentsData] = await Promise.all([
        apiClient.getAnalytics(),
        apiClient.getIncidents({ limit: 100 })
      ])
      setResults(analyticsData)
      setIncidents(incidentsData.incidents || [])
      setError(null)
    } catch (err) {
      console.error('Failed to fetch analytics data:', err)
      setError('Failed to load analytics data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, POLLING_INTERVALS.METRICS)
    return () => clearInterval(interval)
  }, [])

  if (loading) return <AnalyticsSkeleton />

  if (error) {
    return (
      <div className="card text-center py-12">
        <AlertTriangle className="mx-auto h-10 w-10 text-crimson mb-3" />
        <p className="text-text-secondary mb-4">{error}</p>
        <button onClick={fetchData} className="btn-primary">
          <RefreshCw className="w-4 h-4 mr-2 inline" /> Retry
        </button>
      </div>
    )
  }

  // Derive chart data from incidents list
  const summary = results?.summary || computeSummaryFromIncidents(incidents)
  const mttrData = buildMTTRDistribution(incidents)
  const timelineData = buildTimelineData(incidents)
  const confidenceData = buildConfidenceData(incidents)
  const drGapData = buildDRGapData(incidents)
  const failureTaxonomyData = buildFailureTaxonomyData(incidents)
  const ragComparisonData = buildRAGComparisonData(incidents)

  return (
    <div className="space-y-6">
      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricKPI
          label="Avg MTTR"
          value={summary.average_mttr_minutes > 0 ? formatMTTR(summary.average_mttr_minutes) : '—'}
          sub="Mean Time to Recover"
          color="text-text-primary"
        />
        <MetricKPI
          label="Diagnosis Accuracy"
          value={summary.diagnosis_accuracy > 0 ? `${summary.diagnosis_accuracy}%` : '—'}
          sub="RCA correctness rate"
          color={summary.diagnosis_accuracy >= 80 ? 'text-emerald' : 'text-amber'}
        />
        <MetricKPI
          label="Verification Success"
          value={summary.verification_success_rate > 0 ? `${summary.verification_success_rate}%` : '—'}
          sub="Resolved after remediation"
          color={summary.verification_success_rate >= 80 ? 'text-emerald' : 'text-crimson'}
        />
        <MetricKPI
          label="D-R Gap"
          value={summary.diagnosis_recovery_gap > 0 ? `${summary.diagnosis_recovery_gap}%` : '—'}
          sub="High confidence → not resolved"
          color="text-crimson"
        />
      </div>

      {/* Row 2: Timeline + MTTR Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Incident Timeline" sub="Incidents per day by fault class">
          {timelineData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={timelineData} barSize={14}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} vertical={false} />
                <XAxis dataKey="date" tick={{ fill: CHART_COLORS.muted, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                <YAxis tick={{ fill: CHART_COLORS.muted, fontSize: 11, fontFamily: 'JetBrains Mono' }} allowDecimals={false} />
                <Tooltip contentStyle={CUSTOM_TOOLTIP_STYLE} cursor={{ fill: '#1B1B1F' }} />
                <Legend wrapperStyle={{ fontSize: 11, color: CHART_COLORS.secondary }} />
                <Bar dataKey="resource_exhaustion" name="Resource Exhaustion" stackId="a" fill={CHART_COLORS.crimson} />
                <Bar dataKey="misconfiguration" name="Misconfiguration" stackId="a" fill={CHART_COLORS.amber} />
                <Bar dataKey="service_cascade" name="Service Cascade" stackId="a" fill={CHART_COLORS.emerald} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <ChartEmpty message="No incident history yet" />}
        </ChartCard>

        <ChartCard title="MTTR Distribution" sub="Minutes to recover per incident">
          {mttrData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={mttrData} barSize={18}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} vertical={false} />
                <XAxis dataKey="bucket" tick={{ fill: CHART_COLORS.muted, fontSize: 11, fontFamily: 'JetBrains Mono' }} label={{ value: 'minutes', position: 'insideBottom', offset: -2, fill: CHART_COLORS.muted, fontSize: 11 }} />
                <YAxis tick={{ fill: CHART_COLORS.muted, fontSize: 11, fontFamily: 'JetBrains Mono' }} allowDecimals={false} />
                <Tooltip contentStyle={CUSTOM_TOOLTIP_STYLE} cursor={{ fill: '#1B1B1F' }} formatter={(v) => [v, 'Incidents']} />
                <Bar dataKey="count" name="Incidents" fill={CHART_COLORS.primary} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <ChartEmpty message="No resolved incidents yet" />}
        </ChartCard>
      </div>

      {/* Row 3: Confidence vs Correctness + D-R Gap */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Confidence vs Correctness" sub="AI confidence score against actual RCA accuracy">
          {confidenceData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} />
                <XAxis dataKey="confidence" name="Confidence" type="number" domain={[0, 100]} unit="%" tick={{ fill: CHART_COLORS.muted, fontSize: 11, fontFamily: 'JetBrains Mono' }} label={{ value: 'Confidence %', position: 'insideBottom', offset: -2, fill: CHART_COLORS.muted, fontSize: 11 }} />
                <YAxis dataKey="correct" name="Correct" type="number" domain={[0, 1]} ticks={[0, 1]} tickFormatter={(v) => v === 1 ? 'Correct' : 'Wrong'} tick={{ fill: CHART_COLORS.muted, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                <ZAxis range={[40, 40]} />
                <Tooltip contentStyle={CUSTOM_TOOLTIP_STYLE} cursor={{ strokeDasharray: '3 3', stroke: CHART_COLORS.secondary }} formatter={(v, n) => [n === 'Confidence' ? `${v}%` : (v === 1 ? 'Correct' : 'Wrong'), n]} />
                <ReferenceLine x={70} stroke={CHART_COLORS.amber} strokeDasharray="4 4" label={{ value: '70% threshold', fill: CHART_COLORS.amber, fontSize: 10 }} />
                <Scatter name="Diagnoses" data={confidenceData} fill={CHART_COLORS.primary} opacity={0.7} />
              </ScatterChart>
            </ResponsiveContainer>
          ) : <ChartEmpty message="No evaluated diagnosis data yet" />}
        </ChartCard>

        <ChartCard
          title="Diagnosis-Recovery Gap"
          sub="High confidence diagnoses (>70%) where remediation didn't resolve the incident"
          highlight
        >
          {drGapData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={drGapData} barSize={28} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} horizontal={false} />
                <XAxis type="number" tick={{ fill: CHART_COLORS.muted, fontSize: 11, fontFamily: 'JetBrains Mono' }} allowDecimals={false} />
                <YAxis dataKey="label" type="category" width={110} tick={{ fill: CHART_COLORS.secondary, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                <Tooltip contentStyle={CUSTOM_TOOLTIP_STYLE} cursor={{ fill: '#1B1B1F' }} />
                <Bar dataKey="resolved" name="Resolved" stackId="a" fill={CHART_COLORS.emerald} />
                <Bar dataKey="not_resolved" name="Not Resolved" stackId="a" fill={CHART_COLORS.crimson} radius={[0, 2, 2, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <ChartEmpty message="No remediation data to compare yet" />}
        </ChartCard>
      </div>

      {/* Row 4: Failure Taxonomy + RAG vs No-RAG */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="Failure Mode Taxonomy" sub="How the LLM's reasoning went wrong when it did">
          {failureTaxonomyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={failureTaxonomyData} barSize={22} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} horizontal={false} />
                <XAxis type="number" tick={{ fill: CHART_COLORS.muted, fontSize: 11, fontFamily: 'JetBrains Mono' }} allowDecimals={false} />
                <YAxis dataKey="mode" type="category" width={160} tick={{ fill: CHART_COLORS.secondary, fontSize: 10, fontFamily: 'JetBrains Mono' }} />
                <Tooltip contentStyle={CUSTOM_TOOLTIP_STYLE} cursor={{ fill: '#1B1B1F' }} />
                <Bar dataKey="count" name="Incidents" fill={CHART_COLORS.amber} radius={[0, 2, 2, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <ChartEmpty message="No failure mode data yet. Run evaluation harness." />}
        </ChartCard>

        <ChartCard title="RAG vs No-RAG" sub="Diagnosis accuracy with and without runbook context injection">
          {ragComparisonData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={ragComparisonData} barSize={32} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.gridLine} vertical={false} />
                <XAxis dataKey="fault_class" tick={{ fill: CHART_COLORS.muted, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                <YAxis domain={[0, 100]} unit="%" tick={{ fill: CHART_COLORS.muted, fontSize: 11, fontFamily: 'JetBrains Mono' }} />
                <Tooltip contentStyle={CUSTOM_TOOLTIP_STYLE} cursor={{ fill: '#1B1B1F' }} formatter={(v) => [`${v}%`]} />
                <Legend wrapperStyle={{ fontSize: 11, color: CHART_COLORS.secondary }} />
                <Bar dataKey="rag" name="With RAG" fill={CHART_COLORS.rag} radius={[2, 2, 0, 0]} />
                <Bar dataKey="no_rag" name="No RAG" fill={CHART_COLORS.muted} radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <ChartEmpty message="Run evaluation with used_rag=false to see comparison" />}
        </ChartCard>
      </div>
    </div>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function MetricKPI({ label, value, sub, color }) {
  return (
    <div className="card">
      <p className="text-xs text-text-secondary uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-2xl font-semibold mb-1 ${color}`}>{value || '—'}</p>
      <p className="text-xs text-text-muted">{sub}</p>
    </div>
  )
}

function ChartCard({ title, sub, children, highlight = false }) {
  return (
    <div className={`card ${highlight ? 'border-crimson/30' : ''}`}>
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
        <p className="text-xs text-text-muted mt-0.5">{sub}</p>
      </div>
      {children}
    </div>
  )
}

function ChartEmpty({ message }) {
  return (
    <div className="flex items-center justify-center h-48 text-center">
      <div>
        <div className="w-8 h-8 mx-auto mb-3 opacity-30 text-text-muted">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
            <path d="M3 3v18h18M7 16l4-4 4 4 4-6" />
          </svg>
        </div>
        <p className="text-xs text-text-muted max-w-48">{message}</p>
      </div>
    </div>
  )
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card">
            <div className="pulse-loading h-3 w-24 mb-2"></div>
            <div className="pulse-loading h-8 w-16 mb-1"></div>
            <div className="pulse-loading h-3 w-32"></div>
          </div>
        ))}
      </div>
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {Array.from({ length: 2 }).map((_, j) => (
            <div key={j} className="card">
              <div className="pulse-loading h-4 w-32 mb-1"></div>
              <div className="pulse-loading h-3 w-48 mb-4"></div>
              <div className="pulse-loading h-48 w-full rounded"></div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

// ─── Data transformation helpers ─────────────────────────────────────────────

function computeSummaryFromIncidents(incidents) {
  if (!incidents.length) return {}

  const resolved = incidents.filter(i => i.verification?.status === 'resolved')
  const total = incidents.length

  // Average MTTR
  let totalMins = 0, mttrCount = 0
  for (const inc of resolved) {
    if (inc.detected_at && inc.verification?.checked_at) {
      const diff = (new Date(inc.verification.checked_at) - new Date(inc.detected_at)) / 60000
      totalMins += diff
      mttrCount++
    }
  }

  // Verification success rate
  const verificationSuccessRate = total > 0 ? Math.round((resolved.length / total) * 100) : 0

  // D-R gap: high confidence but not resolved
  const highConfidenceIncidents = incidents.filter(i => {
    const conf = parseFloat(i.diagnosis?.confidence || 0)
    return conf >= 0.7
  })
  const drGap = highConfidenceIncidents.length > 0
    ? Math.round(
        (highConfidenceIncidents.filter(i => i.verification?.status === 'not_resolved').length /
          highConfidenceIncidents.length) * 100
      )
    : 0

  return {
    average_mttr_minutes: mttrCount > 0 ? Math.round(totalMins / mttrCount) : 0,
    verification_success_rate: verificationSuccessRate,
    diagnosis_recovery_gap: drGap,
  }
}

function buildTimelineData(incidents) {
  if (!incidents.length) return []

  const byDay = {}
  for (const inc of incidents) {
    if (!inc.detected_at) continue
    const day = inc.detected_at.substring(0, 10)
    if (!byDay[day]) byDay[day] = { date: day, resource_exhaustion: 0, misconfiguration: 0, service_cascade: 0 }
    const fc = inc.fault_class || 'resource_exhaustion'
    byDay[day][fc] = (byDay[day][fc] || 0) + 1
  }

  return Object.values(byDay).sort((a, b) => a.date.localeCompare(b.date)).slice(-14)
}

function buildMTTRDistribution(incidents) {
  const buckets = [
    { bucket: '0–5', min: 0, max: 5, count: 0 },
    { bucket: '5–15', min: 5, max: 15, count: 0 },
    { bucket: '15–30', min: 15, max: 30, count: 0 },
    { bucket: '30–60', min: 30, max: 60, count: 0 },
    { bucket: '60–120', min: 60, max: 120, count: 0 },
    { bucket: '120+', min: 120, max: Infinity, count: 0 },
  ]

  for (const inc of incidents) {
    if (!inc.detected_at || !inc.verification?.checked_at) continue
    const mins = (new Date(inc.verification.checked_at) - new Date(inc.detected_at)) / 60000
    const bucket = buckets.find(b => mins >= b.min && mins < b.max)
    if (bucket) bucket.count++
  }

  return buckets.filter(b => b.count > 0)
}

function buildConfidenceData(incidents) {
  return incidents
    .filter(i => i.diagnosis?.confidence != null && i.verification?.status)
    .map(i => ({
      confidence: Math.round(parseFloat(i.diagnosis.confidence) * 100),
      correct: i.verification.status === 'resolved' ? 1 : 0,
      id: i.incident_id?.substring(0, 8),
    }))
}

function buildDRGapData(incidents) {
  const byClass = {}

  for (const inc of incidents) {
    const conf = parseFloat(inc.diagnosis?.confidence || 0)
    if (conf < 0.7) continue  // Only high-confidence diagnoses

    const fc = FAULT_CLASS_LABELS[inc.fault_class] || inc.fault_class || 'Unknown'
    if (!byClass[fc]) byClass[fc] = { label: fc, resolved: 0, not_resolved: 0 }

    if (inc.verification?.status === 'resolved') byClass[fc].resolved++
    else if (inc.verification?.status === 'not_resolved') byClass[fc].not_resolved++
  }

  return Object.values(byClass)
}

function buildFailureTaxonomyData(incidents) {
  const counts = {}

  for (const inc of incidents) {
    const mode = inc.diagnosis?.failure_mode
    if (!mode || mode === 'none') continue
    counts[mode] = (counts[mode] || 0) + 1
  }

  return Object.entries(counts)
    .map(([mode, count]) => ({ mode: mode.replace(/_/g, ' '), count }))
    .sort((a, b) => b.count - a.count)
}

function buildRAGComparisonData(incidents) {
  const data = {}

  for (const inc of incidents) {
    const fc = FAULT_CLASS_LABELS[inc.fault_class] || inc.fault_class
    if (!data[fc]) data[fc] = { fault_class: fc, rag_correct: 0, rag_total: 0, no_rag_correct: 0, no_rag_total: 0 }

    const correct = inc.verification?.status === 'resolved' ? 1 : 0
    if (inc.diagnosis?.used_rag) {
      data[fc].rag_total++
      data[fc].rag_correct += correct
    } else {
      data[fc].no_rag_total++
      data[fc].no_rag_correct += correct
    }
  }

  return Object.values(data)
    .filter(d => d.rag_total > 0 || d.no_rag_total > 0)
    .map(d => ({
      fault_class: d.fault_class,
      rag: d.rag_total > 0 ? Math.round((d.rag_correct / d.rag_total) * 100) : 0,
      no_rag: d.no_rag_total > 0 ? Math.round((d.no_rag_correct / d.no_rag_total) * 100) : 0,
    }))
}