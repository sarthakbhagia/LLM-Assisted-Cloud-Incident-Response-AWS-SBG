import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { 
  BarChart3, 
  Shield, 
  Activity, 
  Play, 
  User,
  Menu,
  X
} from 'lucide-react'

export default function Layout({ children }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const location = useLocation()

  const navigation = [
    { name: 'Overview', href: '/', icon: Activity },
    { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    { name: 'Replay Mode', href: '/replay', icon: Play }
  ]

  const getPageTitle = () => {
    switch (location.pathname) {
      case '/':
        return 'Overview'
      case '/analytics':
        return 'Analytics'
      case '/replay':
        return 'Replay Mode'
      default:
        if (location.pathname.startsWith('/incidents/')) {
          return 'Incident Detail'
        }
        return 'Dashboard'
    }
  }

  return (
    <div className="min-h-screen bg-bg-base flex">
      {/* Sidebar */}
      <div className={`${sidebarCollapsed ? 'w-14' : 'w-55'} transition-all duration-200 bg-bg-sidebar border-r border-border-default flex flex-col`}>
        {/* Logo and Title */}
        <div className="p-4 border-b border-border-default">
          <div className="flex items-center space-x-3">
            <div className="w-7 h-7 bg-text-primary rounded flex items-center justify-center">
              <Shield className="w-4 h-4 text-bg-base" />
            </div>
            {!sidebarCollapsed && (
              <span className="text-sm font-medium text-text-primary">
                Incident Command Center
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
                className={`
                  flex items-center px-3 py-2 mx-2 rounded text-sm font-medium transition-colors
                  ${isActive 
                    ? 'bg-bg-elevated text-text-primary border-l-2 border-crimson' 
                    : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
                  }
                `}
              >
                <item.icon className="w-4 h-4 flex-shrink-0" />
                {!sidebarCollapsed && (
                  <span className="ml-3">{item.name}</span>
                )}
              </NavLink>
            )
          })}
        </nav>

        {/* Bottom */}
        <div className="p-4 border-t border-border-default">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-bg-elevated rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-text-secondary" />
            </div>
            {!sidebarCollapsed && (
              <div className="flex-1">
                <div className="text-xs text-text-primary font-medium">Production</div>
                <div className="text-xs text-text-muted">ap-south-1</div>
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
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-bg-base border-b border-border-subtle h-12 flex items-center justify-between px-6">
          <h1 className="text-lg font-semibold text-text-primary">
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
        <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
          {children}
        </main>
      </div>
    </div>
  )
}