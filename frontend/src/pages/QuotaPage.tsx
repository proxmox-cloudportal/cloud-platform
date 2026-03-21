import { useState, useEffect } from 'react'
import { AlertCircle, TrendingUp, RefreshCw } from 'lucide-react'
import { quotasApi } from '../services/api'
import { useAuthStore } from '../stores/authStore'

interface QuotaResource {
  resource_type: string
  resource_name: string
  used: number
  limit: number
  remaining: number
  usage_percentage: number
  last_calculated: string | null
}

interface QuotaUsage {
  organization_id: string
  resources: QuotaResource[]
}

export default function QuotaPage() {
  const [quotaUsage, setQuotaUsage] = useState<QuotaUsage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const { currentOrganization } = useAuthStore()

  useEffect(() => {
    if (currentOrganization) {
      loadQuotaUsage()
    }
  }, [currentOrganization])

  const loadQuotaUsage = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await quotasApi.getUsage()
      setQuotaUsage(data)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load quota usage')
    } finally {
      setLoading(false)
    }
  }

  const getProgressColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-red-500'
    if (percentage >= 75) return 'bg-yellow-500'
    return 'bg-green-500'
  }

  const getTextColor = (percentage: number) => {
    if (percentage >= 90) return 'text-red-600'
    if (percentage >= 75) return 'text-yellow-600'
    return 'text-green-600'
  }

  const formatValue = (value: number, resourceType: string) => {
    if (resourceType === 'memory_gb' || resourceType === 'storage_gb') {
      return `${value.toFixed(2)} GB`
    }
    return Math.floor(value).toString()
  }

  if (loading) {
    return (
      <div className="p-8">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
          <AlertCircle className="w-5 h-5 text-red-500 mr-3 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-medium text-red-800">Error loading quotas</h3>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      </div>
    )
  }

  if (!quotaUsage) {
    return null
  }

  return (
    <div className="p-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Resource Quotas</h1>
          <p className="text-gray-600 mt-2">
            Monitor your organization's resource usage and limits
          </p>
        </div>
        <button
          onClick={loadQuotaUsage}
          className="flex items-center px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      {/* Quota Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {quotaUsage.resources.map((resource) => (
          <div
            key={resource.resource_type}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6"
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  {resource.resource_name}
                </h3>
                <p className="text-sm text-gray-500 mt-1">
                  {formatValue(resource.used, resource.resource_type)} of{' '}
                  {formatValue(resource.limit, resource.resource_type)} used
                </p>
              </div>
              {resource.usage_percentage >= 75 && (
                <AlertCircle
                  className={`w-5 h-5 ${
                    resource.usage_percentage >= 90 ? 'text-red-500' : 'text-yellow-500'
                  }`}
                />
              )}
            </div>

            {/* Progress Bar */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className={`text-sm font-medium ${getTextColor(resource.usage_percentage)}`}>
                  {resource.usage_percentage.toFixed(1)}% used
                </span>
                <span className="text-sm text-gray-500">
                  {formatValue(resource.remaining, resource.resource_type)} remaining
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${getProgressColor(resource.usage_percentage)}`}
                  style={{ width: `${Math.min(resource.usage_percentage, 100)}%` }}
                />
              </div>
            </div>

            {/* Warning Messages */}
            {resource.usage_percentage >= 90 && (
              <div className="bg-red-50 border border-red-200 rounded p-3">
                <p className="text-xs text-red-700 font-medium">
                  Critical: Quota almost exhausted. Contact admin to increase limit.
                </p>
              </div>
            )}
            {resource.usage_percentage >= 75 && resource.usage_percentage < 90 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
                <p className="text-xs text-yellow-700 font-medium">
                  Warning: Approaching quota limit. Plan for additional resources.
                </p>
              </div>
            )}

            {/* Last Calculated */}
            {resource.last_calculated && (
              <div className="mt-3 pt-3 border-t border-gray-100">
                <p className="text-xs text-gray-500">
                  Last updated: {new Date(resource.last_calculated).toLocaleString()}
                </p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Summary Stats */}
      <div className="mt-8 bg-gradient-to-r from-indigo-50 to-blue-50 rounded-lg p-6 border border-indigo-100">
        <div className="flex items-center mb-4">
          <TrendingUp className="w-6 h-6 text-indigo-600 mr-3" />
          <h2 className="text-xl font-semibold text-gray-900">Usage Summary</h2>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <p className="text-sm text-gray-600">Total Resources</p>
            <p className="text-2xl font-bold text-gray-900">{quotaUsage.resources.length}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Near Limit (&gt;75%)</p>
            <p className="text-2xl font-bold text-yellow-600">
              {quotaUsage.resources.filter(r => r.usage_percentage >= 75 && r.usage_percentage < 90).length}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Critical (&gt;90%)</p>
            <p className="text-2xl font-bold text-red-600">
              {quotaUsage.resources.filter(r => r.usage_percentage >= 90).length}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Healthy (&lt;75%)</p>
            <p className="text-2xl font-bold text-green-600">
              {quotaUsage.resources.filter(r => r.usage_percentage < 75).length}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
