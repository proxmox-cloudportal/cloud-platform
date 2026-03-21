import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Server, CheckCircle, XCircle, RefreshCw, Trash2 } from 'lucide-react'
import { clustersApi } from '../services/api'

export default function ClustersPage() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const queryClient = useQueryClient()

  const { data: clustersData, isLoading } = useQuery({
    queryKey: ['clusters', page, search],
    queryFn: () => clustersApi.list({ page, per_page: 20, search: search || undefined }),
  })

  const deleteMutation = useMutation({
    mutationFn: clustersApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clusters'] })
    },
  })

  const syncMutation = useMutation({
    mutationFn: clustersApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['clusters'] })
    },
  })

  const handleDelete = (clusterId: string, clusterName: string) => {
    if (window.confirm(`Are you sure you want to delete cluster "${clusterName}"?`)) {
      deleteMutation.mutate(clusterId)
    }
  }

  const handleSync = (clusterId: string) => {
    syncMutation.mutate(clusterId)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-600">Loading clusters...</div>
      </div>
    )
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Proxmox Clusters</h1>
            <p className="text-gray-600 mt-1">Manage your Proxmox VE clusters</p>
          </div>
          <Link
            to="/clusters/create"
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
          >
            <Plus className="w-5 h-5 mr-2" />
            Add Cluster
          </Link>
        </div>
      </div>

      {/* Search */}
      <div className="mb-6">
        <input
          type="text"
          placeholder="Search clusters..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-md w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
        />
      </div>

      {/* Clusters List */}
      {clustersData?.items.length === 0 ? (
        <div className="bg-white shadow rounded-lg p-8 text-center">
          <Server className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No clusters found</h3>
          <p className="text-gray-600 mb-4">Get started by adding your first Proxmox cluster.</p>
          <Link
            to="/clusters/create"
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700"
          >
            <Plus className="w-5 h-5 mr-2" />
            Add Cluster
          </Link>
        </div>
      ) : (
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Cluster
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Location
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Resources
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Sync
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {clustersData?.items.map((cluster: any) => (
                <tr key={cluster.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <Server className="w-5 h-5 text-gray-400 mr-3" />
                      <div>
                        <Link
                          to={`/clusters/${cluster.id}`}
                          className="text-sm font-medium text-indigo-600 hover:text-indigo-900"
                        >
                          {cluster.name}
                        </Link>
                        <div className="text-sm text-gray-500">{cluster.api_url}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-900">{cluster.datacenter || '-'}</div>
                    <div className="text-sm text-gray-500">{cluster.region || '-'}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <div>{cluster.total_cpu_cores || 0} CPU Cores</div>
                    <div className="text-gray-500">{Math.round((cluster.total_memory_mb || 0) / 1024)} GB RAM</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {cluster.is_active ? (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        <CheckCircle className="w-4 h-4 mr-1" />
                        Active
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        <XCircle className="w-4 h-4 mr-1" />
                        Inactive
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {cluster.last_sync ? new Date(cluster.last_sync).toLocaleString() : 'Never'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => handleSync(cluster.id)}
                      disabled={syncMutation.isPending}
                      className="text-indigo-600 hover:text-indigo-900 mr-4"
                      title="Sync resources"
                    >
                      <RefreshCw className={`w-5 h-5 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                    </button>
                    <button
                      onClick={() => handleDelete(cluster.id, cluster.name)}
                      disabled={deleteMutation.isPending}
                      className="text-red-600 hover:text-red-900"
                      title="Delete cluster"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {clustersData && clustersData.pages > 1 && (
        <div className="mt-4 flex justify-between items-center">
          <button
            onClick={() => setPage(page - 1)}
            disabled={page === 1}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-gray-700">
            Page {page} of {clustersData.pages}
          </span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= clustersData.pages}
            className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
