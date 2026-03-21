import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { vmsApi } from '../services/api'
import DiskManagement from '../components/vm/DiskManagement'
import SnapshotManagement from '../components/vm/SnapshotManagement'
import VMActionsMenu from '../components/vm/VMActionsMenu'

export default function VMDetailPage() {
  const { vmId } = useParams<{ vmId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'monitor' | 'detail' | 'storage' | 'snapshots'>('detail')

  const { data: vm, isLoading, error } = useQuery({
    queryKey: ['vm', vmId],
    queryFn: () => vmsApi.get(vmId!),
    enabled: !!vmId,
  })

  const startMutation = useMutation({
    mutationFn: () => vmsApi.start(vmId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
    },
  })

  const stopMutation = useMutation({
    mutationFn: () => vmsApi.stop(vmId!, false),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
    },
  })

  const restartMutation = useMutation({
    mutationFn: () => vmsApi.restart(vmId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => vmsApi.delete(vmId!),
    onSuccess: () => {
      navigate('/vms')
    },
  })

  const consoleMutation = useMutation({
    mutationFn: () => vmsApi.getConsole(vmId!),
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

  const handleDelete = () => {
    if (confirm(`Delete VM "${vm?.name}"? This action cannot be undone.`)) {
      deleteMutation.mutate()
    }
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

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-gray-600">Loading VM details...</div>
      </div>
    )
  }

  if (error || !vm) {
    return (
      <div className="min-h-screen bg-gray-100">
        <div className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            VM not found
          </div>
          <Link to="/vms" className="mt-4 inline-block text-indigo-600 hover:text-indigo-900">
            ← Back to VMs
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center">
            <div>
              <Link to="/vms" className="text-sm text-gray-500 hover:text-gray-700 mb-2 inline-block">
                ← Back to VMs
              </Link>
              <h1 className="text-3xl font-bold text-gray-900">{vm.name}</h1>
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(
                    vm.status
                  )}`}
                >
                  {vm.status}
                </span>
                {vm.power_state && (
                  <span className="text-sm text-gray-500">
                    Power: {vm.power_state}
                  </span>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-2">
              {vm.status === 'stopped' && (
                <button
                  onClick={() => startMutation.mutate()}
                  disabled={startMutation.isPending}
                  className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:opacity-50"
                >
                  Start
                </button>
              )}
              {vm.status === 'running' && (
                <>
                  <button
                    onClick={() => consoleMutation.mutate()}
                    disabled={consoleMutation.isPending}
                    className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    Console
                  </button>
                  <button
                    onClick={() => stopMutation.mutate()}
                    disabled={stopMutation.isPending}
                    className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-yellow-600 hover:bg-yellow-700 disabled:opacity-50"
                  >
                    Stop
                  </button>
                  <button
                    onClick={() => restartMutation.mutate()}
                    disabled={restartMutation.isPending}
                    className="px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    Restart
                  </button>
                </>
              )}
              <VMActionsMenu
                vmId={vm.id}
                vmName={vm.name}
                vmStatus={vm.status}
                onDelete={handleDelete}
              />
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {/* Tabs */}
        <div className="border-b border-gray-200 mb-6">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('monitor')}
              className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'monitor'
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Monitor
            </button>
            <button
              onClick={() => setActiveTab('detail')}
              className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'detail'
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Detail
            </button>
            <button
              onClick={() => setActiveTab('storage')}
              className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'storage'
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Storage
            </button>
            <button
              onClick={() => setActiveTab('snapshots')}
              className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'snapshots'
                  ? 'border-indigo-500 text-indigo-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Snapshots
            </button>
          </nav>
        </div>

        {/* Monitor Tab */}
        {activeTab === 'monitor' && (
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Performance Metrics
              </h3>
              <div className="text-center py-8 text-gray-500">
                <svg
                  className="mx-auto h-12 w-12 text-gray-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
                  />
                </svg>
                <p className="mt-2">Performance metrics coming soon</p>
              </div>
            </div>
          </div>
        )}

        {/* Detail Tab */}
        {activeTab === 'detail' && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* VM Information */}
            <div className="bg-white shadow rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                  VM Information
                </h3>
              <dl className="grid grid-cols-1 gap-x-4 gap-y-4">
                <div>
                  <dt className="text-sm font-medium text-gray-500">VM ID</dt>
                  <dd className="mt-1 text-sm text-gray-900">{vm.id}</dd>
                </div>
                {vm.hostname && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Hostname</dt>
                    <dd className="mt-1 text-sm text-gray-900">{vm.hostname}</dd>
                  </div>
                )}
                {vm.description && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Description</dt>
                    <dd className="mt-1 text-sm text-gray-900">{vm.description}</dd>
                  </div>
                )}
                <div>
                  <dt className="text-sm font-medium text-gray-500">Owner</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {vm.owner.username} ({vm.owner.email})
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Created</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {new Date(vm.created_at).toLocaleString()}
                  </dd>
                </div>
                {vm.provisioned_at && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Provisioned</dt>
                    <dd className="mt-1 text-sm text-gray-900">
                      {new Date(vm.provisioned_at).toLocaleString()}
                    </dd>
                  </div>
                )}
              </dl>
            </div>
          </div>

          {/* Resource Configuration */}
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Resource Configuration
              </h3>
              <dl className="grid grid-cols-1 gap-x-4 gap-y-4">
                <div>
                  <dt className="text-sm font-medium text-gray-500">CPU</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {vm.cpu_cores} cores × {vm.cpu_sockets} socket(s)
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Memory</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {Math.round(vm.memory_mb / 1024)} GB ({vm.memory_mb} MB)
                  </dd>
                </div>
                {vm.os_type && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">OS Type</dt>
                    <dd className="mt-1 text-sm text-gray-900 capitalize">{vm.os_type}</dd>
                  </div>
                )}
                {vm.primary_ip_address && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">IP Address</dt>
                    <dd className="mt-1 text-sm text-gray-900">{vm.primary_ip_address}</dd>
                  </div>
                )}
              </dl>
            </div>
          </div>

          {/* Proxmox Information */}
          <div className="bg-white shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                Proxmox Details
              </h3>
              <dl className="grid grid-cols-1 gap-x-4 gap-y-4">
                <div>
                  <dt className="text-sm font-medium text-gray-500">Cluster</dt>
                  <dd className="mt-1 text-sm text-gray-900">{vm.proxmox_cluster.name}</dd>
                </div>
                {vm.proxmox_cluster.region && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Region</dt>
                    <dd className="mt-1 text-sm text-gray-900">{vm.proxmox_cluster.region}</dd>
                  </div>
                )}
                {vm.proxmox_cluster.datacenter && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Datacenter</dt>
                    <dd className="mt-1 text-sm text-gray-900">{vm.proxmox_cluster.datacenter}</dd>
                  </div>
                )}
                {vm.proxmox_node && (
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Node</dt>
                    <dd className="mt-1 text-sm text-gray-900">{vm.proxmox_node}</dd>
                  </div>
                )}
                <div>
                  <dt className="text-sm font-medium text-gray-500">Proxmox VM ID</dt>
                  <dd className="mt-1 text-sm text-gray-900">{vm.proxmox_vmid}</dd>
                </div>
              </dl>
            </div>
          </div>

          </div>
        )}

        {/* Storage Tab */}
        {activeTab === 'storage' && (
          <DiskManagement
            vmId={vm.id}
            clusterId={vm.proxmox_cluster.id}
            vmStatus={vm.status}
          />
        )}

        {/* Snapshots Tab */}
        {activeTab === 'snapshots' && (
          <SnapshotManagement
            vmId={vm.id}
            vmStatus={vm.status}
          />
        )}
      </main>
    </div>
  )
}
