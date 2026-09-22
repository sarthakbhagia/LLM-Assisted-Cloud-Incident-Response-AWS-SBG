import { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  Activity,
  Zap,
  List,
  BarChart3,
  Network,
  BookOpen,
  RotateCcw,
  ChevronLeft,
  ChevronRight
} from 'lucide-react'
import { apiClient } from '../config/api'
import { POLLING_INTERVALS, CURRENT_USER } from '../utils/constants'

export default function Layout({ children }) {
  // Narrow windows start collapsed so the 236px sidebar doesn't eat the
  // content area (verified against a ~360px preview pane).
  const [isNarrow, setIsNarrow] = useState(
    () => typeof window !== 'undefined' && window.innerWidth < 1024
  )
  const [sidebarCollapsed, setSidebarCollapsed] = useState(isNarrow)

  useEffect(() => {
    const onResize = () => {
      const narrow = window.innerWidth < 1024
      setIsNarrow(narrow)
      if (narrow !== isNarrow) setSidebarCollapsed(narrow)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [isNarrow])

  const location = useLocation()

  // Real backend connectivity + a clock that actually ticks.
  const [apiHealthy, setApiHealthy] = useState(null)
  const [clock, setClock] = useState(() => new Date().toLocaleTimeString())
  // Pending approvals feed the "N" badge on the Incidents nav item.
  const [pendingCount, setPendingCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    const checkHealth = async () => {
      try {
        await apiClient.getHealth()
        if (!cancelled) setApiHealthy(true)
      } catch {
        if (!cancelled) setApiHealthy(false)
      }
    }
    const checkPending = async () => {
      try {
        const data = await apiClient.getIncidents({ limit: 100 })
        const items = data?.items || []
        if (!cancelled) {
          setPendingCount(items.filter(i => i.remediation?.status === 'pending_approval').length)
        }
      } catch {
        if (!cancelled) setPendingCount(0)
      }
    }
    checkHealth()
    checkPending()
    const healthTimer = setInterval(checkHealth, POLLING_INTERVALS.INCIDENTS_FEED)
    const pendingTimer = setInterval(checkPending, POLLING_INTERVALS.INCIDENTS_FEED)
    const clockTimer = setInterval(() => setClock(new Date().toLocaleTimeString()), 30000)
    return () => {
      cancelled = true
      clearInterval(healthTimer)
      clearInterval(pendingTimer)
      clearInterval(clockTimer)
    }
  }, [])

  const navGroups = [
    {
      caption: 'Monitor',
      items: [
        { name: 'Overview', href: '/', icon: Activity },
        { name: 'Incidents', href: '/incidents', icon: List, badge: pendingCount },
        { name: 'Analytics', href: '/analytics', icon: BarChart3 }
      ]
    },
    {
      caption: 'Operate',
      items: [
        { name: 'Service Map', href: '/service-map', icon: Network },
        { name: 'Runbooks', href: '/runbooks', icon: BookOpen },
        { name: 'Replay Mode', href: '/replay', icon: RotateCcw }
      ]
    }
  ]

  const getPageTitle = () => {
    const path = location.pathname
    if (path === '/') return 'Overview'
    if (path === '/incidents') return 'Incidents'
    if (path === '/analytics') return 'Analytics'
    if (path === '/service-map') return 'Service Map'
    if (path === '/runbooks') return 'Runbooks'
    if (path === '/replay') return 'Replay Mode'
    if (path.startsWith('/incidents/')) return 'Incident Detail'
    if (path.startsWith('/runbooks/')) return 'Runbook'
    if (path.startsWith('/replay/')) return 'Replay Mode'
    return 'Dashboard'
  }

  return (
    <div className="min-h-screen bg-bg-base flex">
      {/* ===== Sidebar ===== */}
      <aside
        className="transition-all duration-200 bg-bg-sidebar border-r border-border-default flex flex-col flex-shrink-0 fixed inset-y-0 left-0 z-40"
        style={{ width: sidebarCollapsed ? 68 : 236 }}
      >
        {/* Brand */}
        <div className="px-4 pt-[18px] pb-[14px] border-b border-border-default">
          <div className="flex items-center gap-2.5">
            <div className="w-[30px] h-[30px] rounded-[9px] bg-gradient-to-br from-ink to-[#1E293B] flex items-center justify-center flex-shrink-0 shadow-card">
              <Zap className="w-4 h-4 text-white" />
            </div>
            {!sidebarCollapsed && (
              <div className="min-w-0">
                <div className="text-[14px] font-semibold text-text-primary tracking-[-0.015em] whitespace-nowrap leading-tight">
                  Incident Command
                </div>
                <div className="text-[11px] text-text-muted leading-tight">LLM-assisted response</div>
              </div>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-[14px] flex flex-col gap-0.5 overflow-y-auto">
          {navGroups.map((group, gi) => (
            <div key={group.caption} className={gi > 0 ? 'mt-3' : ''}>
              {!sidebarCollapsed && (
                <div className="text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-muted px-3 pb-2">
                  {group.caption}
                </div>
              )}
              {group.items.map((item) => {
                const isActive = location.pathname === item.href ||
                  (item.href !== '/' && location.pathname.startsWith(item.href))
                return (
                  <NavLink
                    key={item.name}
                    to={item.href}
                    title={sidebarCollapsed ? item.name : undefined}
                    className={`flex items-center gap-2.5 px-3 py-[9px] rounded-[10px] text-[13.5px] font-medium transition-colors w-full ${
                      isActive
                        ? 'bg-gradient-to-r from-indigo-surface/70 to-transparent text-text-primary'
                        : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                    }`}
                  >
                    <item.icon className={`w-[17px] h-[17px] flex-shrink-0 ${isActive ? 'text-indigo' : 'text-text-muted'}`} />
                    {!sidebarCollapsed && <span className="truncate">{item.name}</span>}
                    {!sidebarCollapsed && item.badge > 0 && (
                      <span className="ml-auto text-[10.5px] font-semibold text-crimson bg-crimson-surface rounded-full px-[7px] py-px">
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>

        {/* Bottom: env card + user + collapse toggle */}
        <div className="px-3 pb-4 pt-[14px] border-t border-border-default">
          {!sidebarCollapsed && (
            <>
              <div className="flex items-center gap-2.5 bg-bg-elevated border border-border-default rounded-[12px] px-3 py-2.5 mb-3">
                <div className="min-w-0">
                  <div className="text-[12.5px] font-semibold text-text-primary">Sandbox · Staging</div>
                  <div className="text-[11px] text-text-muted truncate">ap-south-1 · incidents-staging</div>
                </div>
              </div>
              <div className="flex items-center gap-2.5 px-1 pb-2.5">
                <div className="w-[30px] h-[30px] rounded-full bg-gradient-to-br from-indigo to-violet flex items-center justify-center flex-shrink-0">
                  <span className="text-[11.5px] font-semibold text-white">{CURRENT_USER.initials}</span>
                </div>
                <div className="min-w-0">
                  <div className="text-[12.5px] font-semibold text-text-primary truncate">{CURRENT_USER.name}</div>
                  <div className="text-[11px] text-text-muted">{CURRENT_USER.role}</div>
                </div>
              </div>
            </>
          )}
          {sidebarCollapsed && (
            <div className="flex justify-center pb-2.5">
              <div className="w-[30px] h-[30px] rounded-full bg-gradient-to-br from-indigo to-violet flex items-center justify-center">
                <span className="text-[11.5px] font-semibold text-white">{CURRENT_USER.initials}</span>
              </div>
            </div>
          )}
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="w-full h-8 flex items-center justify-center border border-border-default bg-white hover:bg-bg-elevated rounded-[10px] text-text-secondary hover:text-text-primary transition-colors"
          >
            {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>
      </aside>

      {/* ===== Main column ===== */}
      <div
        className="flex-1 flex flex-col min-w-0 transition-all duration-200"
        style={{ marginLeft: sidebarCollapsed ? 68 : 236 }}
      >
        {/* Header */}
        <header
          className="border-b border-border-default h-[58px] flex items-center gap-4 px-8 flex-shrink-0 sticky top-0 z-30"
          style={{
            background: 'rgba(245, 247, 251, 0.82)',
            backdropFilter: 'saturate(1.4) blur(14px)',
            WebkitBackdropFilter: 'saturate(1.4) blur(14px)'
          }}
        >
          <span className="text-[13px] text-text-muted">
            Monitor / <b className="text-text-primary font-semibold">{getPageTitle()}</b>
          </span>

          <div className="flex-1" />

          <div className="flex items-center gap-2 whitespace-nowrap bg-white border border-border-default rounded-full px-3 py-[5px]">
            <span className={`w-2 h-2 rounded-full ${
              apiHealthy === null ? 'bg-border-strong' : apiHealthy ? 'bg-emerald' : 'bg-crimson'
            }`} />
            <span className="text-xs font-medium text-text-secondary">
              {apiHealthy === null ? 'Checking…' : apiHealthy ? 'Live' : 'Backend offline'}
            </span>
          </div>

          <div className="text-xs text-text-muted whitespace-nowrap hidden md:block mono">
            {clock}
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 px-8 pb-20 overflow-x-hidden">
          <div className="max-w-[1120px] mx-auto w-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
