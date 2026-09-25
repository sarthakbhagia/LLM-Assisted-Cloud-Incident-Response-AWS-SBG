import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '../config/api'
import {
  CheckCircle2, XCircle, Clock, RefreshCw, Zap,
  Database, Cloud, BrainCircuit, Activity, Server,
  Settings, Shield, AlertTriangle
} from 'lucide-react'

const SERVICE_META = {
  sts_credentials:    { label: 'AWS Identity (STS)',      icon: Shield,        description: 'IAM credentials and assumed role' },
  dynamodb_table:     { label: 'DynamoDB Table',          icon: Database,      description: 'Incidents data store' },
  s3_bucket:          { label: 'S3 Data Lake',            icon: Cloud,         description: 'Evidence and analytics storage' },
  bedrock_runtime:    { label: 'Bedrock LLM',             icon: BrainCircuit,  description: 'Nova Micro model (ping test)' },
  cloudwatch_alarms:  { label: 'CloudWatch Alarms',       icon: Activity,      description: 'Alarm detection source' },
  lambda_functions:   { label: 'Lambda Functions',        icon: Zap,           description: 'Pipeline execution runtime' },
  ssm_parameters:     { label: 'SSM Parameter Store',     icon: Settings,      description: 'Secrets and config (non-critical)' },
}

const HANDLER_META = {
  collector:    { label: 'Collector',    description: 'Evidence collection' },
  diagnosis:    { label: 'Diagnosis',   description: 'Bedrock LLM diagnosis' },
  notify:       { label: 'Notify',      description: 'Slack notifications' },
  approval:     { label: 'Approval',    description: 'HMAC approval handler' },
  remediation:  { label: 'Remediation', description: 'AWS remediation actions' },
  verification: { label: 'Verification',description: 'Post-fix signal re-check' },
}

function StatusDot({ status, pulse = false }) {
  const color = status === 'ok' || status === 'loaded'
    ? 'bg-emerald'
    : status === 'checking'
    ? 'bg-amber'
    : 'bg-crimson'

  return (
    <span className="relative flex items-center justify-center w-3 h-3">
      {pulse && status === 'checking' && (
        <span className={`absolute inline-flex w-full h-full rounded-full ${color} opacity-40 animate-ping`} />
      )}
      <span className={`relative inline-flex rounded-full w-2.5 h-2.5 ${color}`} />
    </span>
  )
}

function LatencyBar({ ms, max = 3000 }) {
  if (ms == null) return null
  const pct = Math.min((ms / max) * 100, 100)
  const color = ms < 300 ? 'bg-emerald' : ms < 1000 ? 'bg-amber' : 'bg-crimson'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-bg-elevated rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-text-muted font-mono w-14 text-right">{ms} ms</span>
    </div>
  )
}

function ServiceRow({ svc }) {
  const meta = SERVICE_META[svc.service] || { label: svc.service, icon: Server, description: '' }
  const Icon = meta.icon
  const isOk = svc.status === 'ok'

  return (
    <div className={`
      flex items-start gap-4 p-4 rounded-lg border transition-colors
      ${isOk
        ? 'bg-bg-surface border-border-default'
        : 'bg-crimson-surface/20 border-crimson/30'
      }
    `}>
      <div className={`
        w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0
        ${isOk ? 'bg-bg-elevated' : 'bg-crimson-surface'}
      `}>
        <Icon className={`w-4 h-4 ${isOk ? 'text-text-secondary' : 'text-crimson'}`} />
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-sm font-medium text-text-primary">{meta.label}</span>
          {!svc.critical && (
            <span className="text-xs text-text-muted bg-bg-elevated px-1.5 py-0.5 rounded">non-critical</span>
          )}
          <StatusDot status={svc.status} />
        </div>
        <p className="text-xs text-text-muted mb-1">{meta.description}</p>
        {svc.detail && (
          <p className={`text-xs font-mono break-all ${isOk ? 'text-text-secondary' : 'text-crimson'}`}>
            {svc.detail}
          </p>
        )}
        {svc.latency_ms != null && (
          <div className="mt-2">
            <LatencyBar ms={svc.latency_ms} />
          </div>
        )}
      </div>

      <div className="flex-shrink-0 mt-0.5">
        {isOk
          ? <CheckCircle2 className="w-5 h-5 text-emerald" />
          : <XCircle className="w-5 h-5 text-crimson" />
        }
      </div>
    </div>
  )
}

function HandlerPill({ name, status }) {
  const meta = HANDLER_META[name] || { label: name, description: name }
  const isLoaded = status === 'loaded'
  return (
    <div className={`
      flex flex-col gap-0.5 px-3 py-2.5 rounded-lg border text-center
      ${isLoaded ? 'bg-bg-surface border-border-default' : 'bg-crimson-surface/20 border-crimson/30'}
    `}>
      <div className="flex items-center justify-center gap-1.5">
        <StatusDot status={isLoaded ? 'ok' : 'error'} />
        <span className={`text-xs font-medium ${isLoaded ? 'text-text-primary' : 'text-crimson'}`}>
          {meta.label}
        </span>
      </div>
      <span className="text-xs text-text-muted">{meta.description}</span>
    </div>
  )
}

export default function SystemHealth() {
  const [health, setHealth]       = useState(null)
  const [checking, setChecking]   = useState(false)
  const [lastCheck, setLastCheck] = useState(null)
  const [error, setError]         = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(false)

  const runCheck = useCallback(async () => {
    setChecking(true)
    setError(null)
    try {
      const data = await apiClient.getHealth()
      setHealth(data)
      setLastCheck(new Date())
    } catch (err) {
      setError(err.message)
    } finally {
      setChecking(false)
    }
  }, [])

  // Run once on mount
  useEffect(() => { runCheck() }, [runCheck])

  // Auto-refresh every 30s if enabled
  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(runCheck, 30000)
    return () => clearInterval(id)
  }, [autoRefresh, runCheck])

  const allOk = health?.overall === 'ok'
  const criticalFailures = health?.critical_failures ?? 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">System Health</h1>
          <p className="text-sm text-text-muted mt-0.5">
            Live status of all AWS services and pipeline handlers
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <div
              onClick={() => setAutoRefresh(v => !v)}
              className={`
                relative w-9 h-5 rounded-full transition-colors cursor-pointer
                ${autoRefresh ? 'bg-emerald' : 'bg-bg-elevated border border-border-strong'}
              `}
            >
              <div className={`
                absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform
                ${autoRefresh ? 'translate-x-4' : 'translate-x-0.5'}
              `} />
            </div>
            <span className="text-xs text-text-secondary">Auto-refresh 30s</span>
          </label>
          <button
            id="run-health-check-btn"
            onClick={runCheck}
            disabled={checking}
            className="btn-primary flex items-center gap-2"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${checking ? 'animate-spin' : ''}`} />
            {checking ? 'Checking...' : 'Run Check'}
          </button>
        </div>
      </div>

      {/* Overall status banner */}
      {health && (
        <div className={`
          flex items-center gap-4 p-4 rounded-lg border
          ${allOk
            ? 'bg-emerald/5 border-emerald/30'
            : 'bg-crimson-surface/30 border-crimson/40'
          }
        `}>
          {allOk
            ? <CheckCircle2 className="w-6 h-6 text-emerald flex-shrink-0" />
            : <AlertTriangle className="w-6 h-6 text-crimson flex-shrink-0" />
          }
          <div className="flex-1">
            <div className={`text-sm font-semibold ${allOk ? 'text-emerald' : 'text-crimson'}`}>
              {allOk ? 'All systems operational' : `${criticalFailures} critical service(s) unavailable`}
            </div>
            <div className="text-xs text-text-muted mt-0.5">
              Region: {health.region} &nbsp;&bull;&nbsp;
              Checked: {lastCheck ? lastCheck.toLocaleTimeString() : '—'} &nbsp;&bull;&nbsp;
              {health.services?.length ?? 0} services probed
            </div>
          </div>
          <div className={`
            text-xs font-mono px-3 py-1.5 rounded-full font-semibold
            ${allOk ? 'bg-emerald/10 text-emerald' : 'bg-crimson-surface text-crimson'}
          `}>
            {allOk ? 'HEALTHY' : 'DEGRADED'}
          </div>
        </div>
      )}

      {/* Error state */}
      {error && !checking && (
        <div className="flex items-center gap-3 p-4 bg-crimson-surface/30 border border-crimson/40 rounded-lg">
          <XCircle className="w-5 h-5 text-crimson flex-shrink-0" />
          <div>
            <div className="text-sm font-medium text-crimson">Health check failed</div>
            <div className="text-xs text-text-muted font-mono mt-0.5">{error}</div>
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {checking && !health && (
        <div className="space-y-3">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-20 bg-bg-surface border border-border-default rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {/* AWS Services grid */}
      {health?.services && (
        <section>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-3">
            AWS Services
          </h2>
          <div className="space-y-2">
            {health.services.map(svc => (
              <ServiceRow key={svc.service} svc={svc} />
            ))}
          </div>
        </section>
      )}

      {/* Pipeline handlers */}
      {health?.pipeline_handlers && (
        <section>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-3">
            Pipeline Handlers (in-process)
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(health.pipeline_handlers).map(([name, status]) => (
              <HandlerPill key={name} name={name} status={status} />
            ))}
          </div>
          <p className="text-xs text-text-muted mt-2">
            These Lambda handlers run in-process locally and route to real AWS services via
            the&nbsp;<span className="font-mono text-text-secondary">LocalLambdaRouter</span>.
          </p>
        </section>
      )}

      {/* Latency summary table */}
      {health?.services && (
        <section>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-widest mb-3">
            Latency Summary
          </h2>
          <div className="card overflow-hidden p-0">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border-default">
                  <th className="text-left px-4 py-2.5 text-text-muted font-medium">Service</th>
                  <th className="text-left px-4 py-2.5 text-text-muted font-medium">Status</th>
                  <th className="text-right px-4 py-2.5 text-text-muted font-medium">Latency</th>
                  <th className="text-left px-4 py-2.5 text-text-muted font-medium w-1/3">Bar</th>
                </tr>
              </thead>
              <tbody>
                {health.services.map((svc, i) => {
                  const meta = SERVICE_META[svc.service]
                  return (
                    <tr key={svc.service} className={`border-b border-border-subtle ${i % 2 === 0 ? 'bg-bg-surface' : 'bg-bg-base'}`}>
                      <td className="px-4 py-2 font-medium text-text-primary">{meta?.label || svc.service}</td>
                      <td className="px-4 py-2">
                        <span className={`badge ${svc.status === 'ok' ? 'badge-success' : 'badge-critical'}`}>
                          {svc.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right font-mono text-text-secondary">
                        {svc.latency_ms != null ? `${svc.latency_ms} ms` : '—'}
                      </td>
                      <td className="px-4 py-2">
                        <LatencyBar ms={svc.latency_ms} />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  )
}
