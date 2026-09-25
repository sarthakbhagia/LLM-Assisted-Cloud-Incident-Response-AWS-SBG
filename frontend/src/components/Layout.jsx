import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { 
  BarChart3, 
  Shield, 
  Activity, 
  Play, 
  User,
  Menu,
  X,
  List,
  Network,
  BookOpen,
  HeartPulse
} from 'lucide-react'

export default function Layout({ children }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const location = useLocation()

  const navigation = [
    { name: 'Overview', href: '/', icon: Activity },
    { name: 'Incidents', href: '/incidents', icon: List },
    { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    { name: 'Service Map', href: '/service-map', icon: Network },
    { name: 'Runbooks', href: '/runbooks', icon: BookOpen },
    { name: 'Replay Mode', href: '/replay', icon: Play },
    { name: 'System Health', href: '/system-health', icon: HeartPulse },
  ]

  const getPageTitle = () => {
    const path = location.pathname
    if (path === '/') return 'Overview'
    if (path === '/incidents') return 'Incidents'
    if (path === '/analytics') return 'Analytics'
    if (path === '/service-map') return 'Service Map'
    if (path === '/runbooks') return 'Runbooks'
    if (path === '/replay') return 'Replay Mode'
    if (path === '/system-health') return 'System Health'
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
        style={{ width: sidebarCollapsed ? 56 : 200 }}
      >
        {/* Logo and Title */}
        <div className="p-4 border-b border-border-default">
          <div className="flex items-center space-x-3">
            <div className="w-7 h-7 bg-text-primary rounded flex items-center justify-center flex-shrink-0">
              <Shield className="w-4 h-4 text-bg-base" />
            </div>
            {!sidebarCollapsed && (
              <span className="text-sm font-medium text-text-primary whitespace-nowrap overflow-hidden">
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
                <div className="text-xs text-text-primary font-medium capitalize">
                  {import.meta.env.VITE_ENVIRONMENT || (import.meta.env.MODE === 'production' ? 'dev' : import.meta.env.MODE)}
                </div>
                <div className="text-xs text-text-muted">
                  {import.meta.env.VITE_AWS_REGION || 'ap-south-1'}
                </div>
              </div>
            )}
          </div>
          
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="mt-3 w-full flex items-center justify-center p-1 hover:bg-bg-elevated rounded"
          >
            {sidebarCollapsed ? (
              <Menu className="w-4 h-4 text-text-secondary" />
            ) : (
              <X className="w-4 h-4 text-text-secondary" />
            )}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="bg-bg-base border-b border-border-subtle h-12 flex items-center justify-between px-6 flex-shrink-0">
          <h1 className="text-base font-semibold text-text-primary">
            {getPageTitle()}
          </h1>
          
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-emerald rounded-full"></div>
              <span className="text-xs text-text-secondary">Live</span>
            </div>
            
            <div className="text-xs text-text-muted">
              Last updated {new Date().toLocaleTimeString()}
            </div>
            
            <div className="w-8 h-8 bg-bg-elevated rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-text-secondary" />
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 overflow-auto">
          <div className="max-w-7xl mx-auto w-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}