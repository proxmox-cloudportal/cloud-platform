import { Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Server,
  HardDrive,
  Network,
  FileText,
  Settings,
  LogOut,
  Building2,
  BarChart3
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import OrganizationSwitcher from './OrganizationSwitcher'

interface NavItem {
  name: string
  path: string
  icon: React.ReactNode
}

export default function Sidebar() {
  const location = useLocation()
  const { user, clearAuth } = useAuthStore()

  const navItems: NavItem[] = [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: <LayoutDashboard className="w-5 h-5" />
    },
    {
      name: 'Virtual Machines',
      path: '/vms',
      icon: <Server className="w-5 h-5" />
    },
    {
      name: 'Proxmox Clusters',
      path: '/clusters',
      icon: <HardDrive className="w-5 h-5" />
    },
    {
      name: 'Resource Quotas',
      path: '/quotas',
      icon: <BarChart3 className="w-5 h-5" />
    },
    {
      name: 'Organization',
      path: '/organization/settings',
      icon: <Building2 className="w-5 h-5" />
    },
    {
      name: 'VM Templates',
      path: '/templates',
      icon: <FileText className="w-5 h-5" />
    },
    {
      name: 'Networking',
      path: '/networking',
      icon: <Network className="w-5 h-5" />
    },
    {
      name: 'Settings',
      path: '/settings',
      icon: <Settings className="w-5 h-5" />
    }
  ]

  const handleLogout = () => {
    clearAuth()
    window.location.href = '/login'
  }

  return (
    <div className="flex flex-col w-64 bg-gray-900 min-h-screen">
      {/* Logo/Header */}
      <div className="flex items-center justify-center h-16 bg-gray-800 border-b border-gray-700">
        <h1 className="text-xl font-bold text-white">Cloud Platform</h1>
      </div>

      {/* Organization Switcher */}
      <div className="px-3 py-4 border-b border-gray-700">
        <OrganizationSwitcher />
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path ||
                          location.pathname.startsWith(item.path + '/')

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`
                flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors
                ${isActive
                  ? 'bg-indigo-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }
              `}
            >
              <span className="mr-3">{item.icon}</span>
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* User section */}
      <div className="p-4 border-t border-gray-700">
        <div className="flex items-center mb-3">
          <div className="flex-shrink-0">
            <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white font-semibold">
              {user?.first_name?.[0] || user?.username?.[0] || 'U'}
            </div>
          </div>
          <div className="ml-3 flex-1 min-w-0">
            <p className="text-sm font-medium text-white truncate">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-xs text-gray-400 truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center px-4 py-2 text-sm font-medium text-gray-300 rounded-lg hover:bg-gray-800 hover:text-white transition-colors"
        >
          <LogOut className="w-5 h-5 mr-3" />
          Logout
        </button>
      </div>
    </div>
  )
}
