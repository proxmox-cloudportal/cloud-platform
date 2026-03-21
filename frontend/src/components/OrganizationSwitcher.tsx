import { useState, useEffect } from 'react'
import { Building2, ChevronDown, Check } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { organizationsApi } from '../services/api'

export default function OrganizationSwitcher() {
  const { currentOrganization, organizations, setOrganizations, setCurrentOrganization } = useAuthStore()
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadOrganizations()
  }, [])

  const loadOrganizations = async () => {
    try {
      setLoading(true)
      const data = await organizationsApi.listMyOrganizations()
      setOrganizations(data)
    } catch (error) {
      console.error('Failed to load organizations:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectOrganization = (org: any) => {
    setCurrentOrganization(org.organization)
    setIsOpen(false)
    // Reload page to refresh data with new org context
    window.location.reload()
  }

  if (loading || organizations.length === 0) {
    return null
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center w-full px-4 py-3 text-sm font-medium text-gray-300 hover:bg-gray-800 rounded-lg transition-colors"
      >
        <Building2 className="w-5 h-5 mr-3" />
        <div className="flex-1 text-left min-w-0">
          <p className="text-sm font-medium text-white truncate">
            {currentOrganization?.name || 'Select Organization'}
          </p>
          <p className="text-xs text-gray-400 truncate">
            {organizations.find(o => o.organization.id === currentOrganization?.id)?.role || 'member'}
          </p>
        </div>
        <ChevronDown className={`w-4 h-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />

          {/* Dropdown */}
          <div className="absolute left-0 right-0 mt-2 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-20 max-h-64 overflow-y-auto">
            {organizations.map((membership) => {
              const isSelected = membership.organization.id === currentOrganization?.id

              return (
                <button
                  key={membership.organization.id}
                  onClick={() => handleSelectOrganization(membership)}
                  className={`
                    w-full flex items-center px-4 py-3 text-left hover:bg-gray-700 transition-colors
                    ${isSelected ? 'bg-gray-700' : ''}
                  `}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">
                      {membership.organization.name}
                    </p>
                    <p className="text-xs text-gray-400 truncate">
                      {membership.role}
                    </p>
                  </div>
                  {isSelected && (
                    <Check className="w-5 h-5 text-indigo-500 flex-shrink-0" />
                  )}
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
