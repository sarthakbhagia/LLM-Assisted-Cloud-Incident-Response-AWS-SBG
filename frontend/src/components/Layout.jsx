import { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  BarChart3, 
  Shield, 
  Activity, 
  Play, 
  User,
  PanelLeft,
  List,
  Network,
  BookOpen
} from 'lucide-react'
import { apiClient } from '../config/api'
import { POLLING_INTERVALS } from '../utils/constants'

export default function Layout({ children }) {
  // Narrow windows start collapsed so the 220px sidebar doesn't eat the content
  // area (the full-page screenshot showed the content squeezed to ~350px).
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

  // Real backend connectivity + a clock that actually ticks (both were
  // previously static values rendered once at mount).
  const [apiHealthy, setApiHealthy] = useState(null)
  const [clock, setClock] = useState(() => new Date().toLocaleTimeString())

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
    checkHealth()
    const healthTimer = setInterval(checkHealth, POLLING_INTERVALS.INCIDENTS_FEED)
    const clockTimer = setInterval(() => setClock(new Date().toLocaleTimeString()), 30000)
    return () => {
      cancelled = true
      clearInterval(healthTimer)
      clearInterval(clockTimer)
    }
  }, [])

  const navigation = [
    { name: 'Overview', href: '/', icon: Activity },
    { name: 'Incidents', href: '/incidents', icon: List },
    { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    { name: 'Service Map', href: '/service-map', icon: Network },
    { name: 'Runbooks', href: '/runbooks', icon: BookOpen },
    { name: 'Replay Mode', href: '/replay', icon: Play }
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
      {/* Sidebar */}
      <div
        className="transition-all duration-200 bg-bg-sidebar border-r border-border-default flex flex-col flex-shrink-0"
        style={{ width: sidebarCollapsed ? 56 : 220 }}
      >
        {/* Logo and Title */}
        <div className="p-4 border-b border-border-default">
          <div className="flex items-center space-x-3">
            <div className="w-7 h-7 bg-text-primary rounded flex items-center justify-center flex-shrink-0">
              <Shield className="w-4 h-4 text-bg-base" />
            </div>
            {!sidebarCollapsed && (
              <span className="text-sm font-medium text-text-primary whitespace-nowrap overflow-hidden tracking-tight">
                Incident Command
              </span>
            )}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 pt-4">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href || 
              (item.href !== '/' && location.pathname.startsWith(item.href))
            
            return (
              <NavLink
                key={item.name}
                to={item.href}
                title={sidebarCollapsed ? item.name : undefined}
                className={`
                  flex items-center px-3 py-2 mx-2 rounded text-sm font-medium transition-colors mb-0.5
                  ${isActive 
                    ? 'bg-bg-elevated text-text-primary border-l-2 border-crimson' 
                    : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary border-l-2 border-transparent'
                  }
                `}
              >
                <item.icon className="w-4 h-4 flex-shrink-0" />
                {!sidebarCollapsed && (
                  <span className="ml-3 truncate">{item.name}</span>
                )}
              </NavLink>
            )
          })}
        </nav>

        {/* Bottom */}
        <div className="p-4 border-t border-border-default">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-bg-elevated rounded-full flex items-center justify-center flex-shrink-0">
              <User className="w-4 h-4 text-text-secondary" />
            </div>
            {!sidebarCollapsed && (
              <div className="flex-1 min-w-0">
                <div className="text-xs text-text-primary font-medium">Staging</div>
                <div className="text-xs text-text-muted">ap-south-1</div>
              </div>
            )}
          </div>
          
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="mt-3 w-full flex items-center justify-center p-1.5 hover:bg-bg-elevated rounded text-text-secondary hover:text-text-primary transition-colors"
          >
            <PanelLeft className={`w-4 h-4 transition-transform duration-200 ${
              sidebarCollapsed ? '' : 'scale-x-[-1]'
            }`} />
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="bg-bg-base border-b border-border-subtle h-12 flex items-center justify-between px-6 flex-shrink-0">
          <h1 className="text-base font-semibold text-text-primary tracking-tight">
            {getPageTitle()}
          </h1>
          
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 whitespace-nowrap">
              <div className={`w-2 h-2 rounded-full ${
                apiHealthy === null ? 'bg-border-strong' : apiHealthy ? 'bg-emerald' : 'bg-crimson'
              }`}></div>
              <span className="text-xs text-text-secondary">
                {apiHealthy === null ? 'Checking…' : apiHealthy ? 'Live' : 'Backend offline'}
              </span>
            </div>
            
            <div className="text-xs text-text-muted whitespace-nowrap hidden md:block">
              Updated {clock}
            </div>
            
            <div className="w-8 h-8 bg-bg-elevated rounded-full flex items-center justify-center flex-shrink-0">
              <User className="w-4 h-4 text-text-secondary" />
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 overflow-auto">
          <div className="max-w-[1120px] mx-auto w-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}