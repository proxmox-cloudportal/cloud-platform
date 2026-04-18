import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { vmsApi } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import VMActionsMenu from '../components/vm/VMActionsMenu'

export default function ContainersPage() {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [nodeFilter, setNodeFilter] = useState('')
  const queryClient = useQueryClient()
  const { currentOrganization } = useAuthStore()

  const { data, isLoading, error } = useQuery({
    queryKey: ['containers', search, statusFilter, currentOrganization?.id],
    queryFn: () => vmsApi.list({ per_page: 500, search, status: statusFilter || undefined }),
    enabled: !!currentOrganization,
  })

  const startMutation = useMutation({
    mutationFn: vmsApi.start,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['containers'] }),
  })
  const stopMutation = useMutation({
    mutationFn: (id: string) => vmsApi.stop(id, false),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['containers'] }),
  })
  const deleteMutation = useMutation({
    mutationFn: vmsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['containers'] }),
  })

  const allCTs = (data?.data ?? []).filter((v: any) => v.vm_type === 'lxc')

  const nodes = [...new Set(allCTs.map((v: any) => v.proxmox_node).filter(Boolean))].sort() as string[]

  const filtered = nodeFilter ? allCTs.filter((v: any) => v.proxmox_node === nodeFilter) : allCTs

  const grouped = filtered.reduce((acc: Record<string, any[]>, ct: any) => {
    const node = ct.proxmox_node || 'unknown'
    if (!acc[node]) acc[node] = []
    acc[node].push(ct)
    return acc
  }, {})

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-green-100 text-green-800'
      case 'stopped': return 'bg-gray-100 text-gray-800'
      case 'error': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  if (!currentOrganization) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading organization...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">Containers</h1>
        </div>
      </header>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {/* Filters */}
        <div className="bg-white shadow rounded-lg p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Search</label>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name..."
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
              >
                <option value="">All Statuses</option>
                <option value="running">Running</option>
                <option value="stopped">Stopped</option>
                <option value="error">Error</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Node</label>
              <select
                value={nodeFilter}
                onChange={(e) => setNodeFilter(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
              >
                <option value="">All Nodes</option>
                {nodes.map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="text-center py-12"><div className="text-gray-600">Loading containers...</div></div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">Failed to load containers</div>
        ) : filtered.length === 0 ? (
          <div className="bg-white shadow rounded-lg p-12 text-center">
            <h3 className="text-lg font-medium text-gray-900 mb-2">No containers found</h3>
            <p className="text-gray-500">Sync your cluster to import existing LXC containers.</p>
          </div>
        ) : (
          Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b)).map(([node, cts]) => (
            <div key={node} className="mb-6">
              <div className="flex items-center gap-2 mb-2 px-1">
                <span className="text-sm font-semibold text-gray-700">{node}</span>
                <span className="text-xs text-gray-400">({cts.length} container{cts.length !== 1 ? 's' : ''})</span>
              </div>
              <div className="bg-white shadow sm:rounded-lg">
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Resources</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP Address</th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {cts.map((ct: any) => (
                        <tr key={ct.id}>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm font-medium text-gray-900">{ct.name}</div>
                            <div className="text-xs text-gray-400">CTID: {ct.proxmox_vmid}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(ct.status)}`}>
                              {ct.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {ct.cpu_cores} vCPU / {Math.round(ct.memory_mb / 1024)} GB RAM
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {ct.primary_ip_address || '-'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <div className="flex justify-end gap-3 items-center">
                              {ct.status === 'stopped' && (
                                <button onClick={() => startMutation.mutate(ct.id)} disabled={startMutation.isPending}
                                  className="px-3 py-1 text-sm text-green-600 hover:text-green-900 disabled:opacity-50 font-medium">
                                  Start
                                </button>
                              )}
                              {ct.status === 'running' && (
                                <button onClick={() => stopMutation.mutate(ct.id)} disabled={stopMutation.isPending}
                                  className="px-3 py-1 text-sm text-yellow-600 hover:text-yellow-900 disabled:opacity-50 font-medium">
                                  Stop
                                </button>
                              )}
                              <VMActionsMenu vmId={ct.id} vmName={ct.name} vmStatus={ct.status} onDelete={() => deleteMutation.mutate(ct.id)} />
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ))
        )}
      </main>
    </div>
  )
}
