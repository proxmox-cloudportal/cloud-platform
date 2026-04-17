import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { vmsApi } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import VMActionsMenu from '../components/vm/VMActionsMenu'

export default function VMsPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [nodeFilter, setNodeFilter] = useState('')
  const queryClient = useQueryClient()
  const { currentOrganization } = useAuthStore()

  const { data, isLoading, error } = useQuery({
    queryKey: ['vms', page, search, statusFilter, currentOrganization?.id],
    queryFn: () => vmsApi.list({ page, per_page: 200, search, status: statusFilter || undefined }),
    enabled: !!currentOrganization,
  })

  const startMutation = useMutation({
    mutationFn: vmsApi.start,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vms'] })
    },
  })

  const stopMutation = useMutation({
    mutationFn: (vmId: string) => vmsApi.stop(vmId, false),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vms'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: vmsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vms'] })
    },
  })

  const syncMutation = useMutation({
    mutationFn: vmsApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vms'] })
    },
  })

  const consoleMutation = useMutation({
    mutationFn: vmsApi.getConsole,
    onSuccess: (data) => {
      // Show workaround note if provided
      if (data.workaround_note) {
        alert(
          'Opening VM Console\n\n' +
          'Note: ' + data.workaround_note + '\n\n' +
          'The console window will open now.'
        )
      }

      window.open(
        data.console_url,
        'vmConsole',
        'width=1024,height=768,menubar=no,toolbar=no,location=no,status=no,resizable=yes,scrollbars=yes'
      )
    },
    onError: (error: any) => {
      alert('Failed to open console: ' + (error.response?.data?.detail || error.message))
    },
  })

  const allQemuVMs = (data?.data ?? []).filter((vm: any) => vm.vm_type === 'qemu')
  const nodes = [...new Set(allQemuVMs.map((vm: any) => vm.proxmox_node).filter(Boolean))].sort() as string[]

  // Auto-sync provisioning VMs when data loads
  useEffect(() => {
    if (data?.data) {
      const provisioningVMs = data.data.filter((vm: any) => vm.status === 'provisioning')
      provisioningVMs.forEach((vm: any) => {
        // Sync after a short delay to avoid overwhelming the API
        setTimeout(() => {
          vmsApi.sync(vm.id).then(() => {
            queryClient.invalidateQueries({ queryKey: ['vms'] })
          }).catch(err => {
            console.error(`Failed to sync VM ${vm.id}:`, err)
          })
        }, 500)
      })
    }
  }, [data?.data, queryClient])

  const handleStart = (vmId: string, vmName: string) => {
    if (confirm(`Start VM "${vmName}"?`)) {
      startMutation.mutate(vmId)
    }
  }

  const handleStop = (vmId: string, vmName: string) => {
    if (confirm(`Stop VM "${vmName}"?`)) {
      stopMutation.mutate(vmId)
    }
  }

  const handleDelete = (vmId: string, vmName: string) => {
    if (confirm(`Delete VM "${vmName}"? This action cannot be undone.`)) {
      deleteMutation.mutate(vmId)
    }
  }

  const handleSync = (vmId: string) => {
    syncMutation.mutate(vmId)
  }

  const handleConsole = (vmId: string) => {
    consoleMutation.mutate(vmId)
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'bg-green-100 text-green-800'
      case 'stopped':
        return 'bg-gray-100 text-gray-800'
      case 'provisioning':
        return 'bg-blue-100 text-blue-800'
      case 'error':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
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
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900">Virtual Machines</h1>
          <Link
            to="/vms/create"
            className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
          >
            Create VM
          </Link>
        </div>
      </header>

      {/* Main content */}
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
                <option value="provisioning">Provisioning</option>
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

        {/* VMs / CT List grouped by node */}
        {isLoading ? (
          <div className="text-center py-12">
            <div className="text-gray-600">Loading...</div>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            Failed to load VMs
          </div>
        ) : allQemuVMs.length === 0 ? (
          <div className="bg-white shadow rounded-lg p-12 text-center">
            <h3 className="text-lg font-medium text-gray-900 mb-2">No virtual machines or containers</h3>
            <p className="text-gray-500 mb-4">Get started by creating your first VM.</p>
            <Link
              to="/vms/create"
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
            >
              Create VM
            </Link>
          </div>
        ) : (
          <>
            {Object.entries(
              (nodeFilter ? allQemuVMs.filter((vm: any) => vm.proxmox_node === nodeFilter) : allQemuVMs)
                .reduce((groups: Record<string, any[]>, vm: any) => {
                  const node = vm.proxmox_node || 'unknown'
                  if (!groups[node]) groups[node] = []
                  groups[node].push(vm)
                  return groups
                }, {})
            ).sort(([a], [b]) => a.localeCompare(b)).map(([node, vms]) => (
              <div key={node} className="mb-6">
                <div className="flex items-center gap-2 mb-2 px-1">
                  <span className="text-sm font-semibold text-gray-700">{node}</span>
                  <span className="text-xs text-gray-400">({vms.length} instance{vms.length !== 1 ? 's' : ''})</span>
                </div>
                <div className="bg-white shadow sm:rounded-lg">
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Resources</th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">IP Address</th>
                          <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {vms.map((vm: any) => (
                          <tr key={vm.id}>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div>
                                <Link to={`/vms/${vm.id}`} className="text-sm font-medium text-indigo-600 hover:text-indigo-900">
                                  {vm.name}
                                </Link>
                                {vm.hostname && <div className="text-xs text-gray-400">{vm.hostname}</div>}
                                <div className="text-xs text-gray-400">VMID: {vm.proxmox_vmid}</div>
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                                vm.vm_type === 'lxc'
                                  ? 'bg-purple-100 text-purple-800'
                                  : 'bg-blue-100 text-blue-800'
                              }`}>
                                {vm.vm_type === 'lxc' ? 'CT' : 'VM'}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(vm.status)}`}>
                                {vm.status}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {vm.cpu_cores} vCPU / {Math.round(vm.memory_mb / 1024)} GB RAM
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                              {vm.primary_ip_address || '-'}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                              <div className="flex justify-end gap-3 items-center">
                                {vm.status === 'provisioning' && (
                                  <button onClick={() => handleSync(vm.id)} disabled={syncMutation.isPending}
                                    className="inline-flex items-center px-2 py-1 text-blue-600 hover:text-blue-900 disabled:opacity-50"
                                    title="Refresh status from Proxmox">
                                    <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
                                  </button>
                                )}
                                {vm.status === 'stopped' && (
                                  <button onClick={() => handleStart(vm.id, vm.name)} disabled={startMutation.isPending}
                                    className="px-3 py-1 text-sm text-green-600 hover:text-green-900 disabled:opacity-50 font-medium">
                                    Start
                                  </button>
                                )}
                                {vm.status === 'running' && (
                                  <>
                                    {vm.vm_type === 'qemu' && (
                                      <button onClick={() => handleConsole(vm.id)} disabled={consoleMutation.isPending}
                                        className="px-3 py-1 text-sm text-blue-600 hover:text-blue-900 disabled:opacity-50 font-medium">
                                        Console
                                      </button>
                                    )}
                                    <button onClick={() => handleStop(vm.id, vm.name)} disabled={stopMutation.isPending}
                                      className="px-3 py-1 text-sm text-yellow-600 hover:text-yellow-900 disabled:opacity-50 font-medium">
                                      Stop
                                    </button>
                                  </>
                                )}
                                <Link to={`/vms/${vm.id}`} className="px-3 py-1 text-sm text-indigo-600 hover:text-indigo-900 font-medium">
                                  View
                                </Link>
                                <VMActionsMenu vmId={vm.id} vmName={vm.name} vmStatus={vm.status} onDelete={() => handleDelete(vm.id, vm.name)} />
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ))}

            {/* Pagination */}
            {data && data.total_pages > 1 && (
              <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6 mt-4 rounded-lg">
                <div className="flex-1 flex justify-between sm:hidden">
                  <button
                    onClick={() => setPage(page - 1)}
                    disabled={page === 1}
                    className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={page === data.total_pages}
                    className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
                <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm text-gray-700">
                      Showing page <span className="font-medium">{page}</span> of{' '}
                      <span className="font-medium">{data.total_pages}</span> ({data.total} total
                      VMs)
                    </p>
                  </div>
                  <div>
                    <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                      <button
                        onClick={() => setPage(page - 1)}
                        disabled={page === 1}
                        className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                      >
                        Previous
                      </button>
                      <button
                        onClick={() => setPage(page + 1)}
                        disabled={page === data.total_pages}
                        className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                      >
                        Next
                      </button>
                    </nav>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
