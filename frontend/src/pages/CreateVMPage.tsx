import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { vmsApi, quotasApi, networksApi } from '../services/api'
import OSSelectionSection from '../components/vm/OSSelectionSection'
import BootConfigurationSection from '../components/vm/BootConfigurationSection'
import DiskConfigurationSection from '../components/vm/DiskConfigurationSection'
import { Network, Wifi, WifiOff } from 'lucide-react'

interface Disk {
  id: string
  size_gb: number
  storage_pool: string
  disk_interface: string
  is_boot_disk: boolean
}

export default function CreateVMPage() {
  const navigate = useNavigate()
  const [error, setError] = useState('')

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    hostname: '',
    description: '',
    cpu_cores: 2,
    cpu_sockets: 1,
    memory_mb: 2048,
    os_type: 'linux',
  })

  const [bootMethod, setBootMethod] = useState<'disk' | 'iso'>('disk')
  const [selectedIsoId, setSelectedIsoId] = useState<string | null>(null)

  const [disks, setDisks] = useState<Disk[]>([
    {
      id: `disk-${Date.now()}`,
      size_gb: 40,
      storage_pool: 'local-lvm',
      disk_interface: 'scsi',
      is_boot_disk: true,
    },
  ])

  // Network configuration
  const [selectedNetworkId, setSelectedNetworkId] = useState<string | null>(null)
  const [allocateIp, setAllocateIp] = useState(true)

  // Fetch networks
  const { data: networksData, isLoading: networksLoading } = useQuery({
    queryKey: ['networks'],
    queryFn: () => networksApi.list(1, 100),
  })

  const networks = networksData?.data || []
  const selectedNetwork = networks.find((n: any) => n.id === selectedNetworkId)

  // Fetch quotas
  const { data: quotas } = useQuery({
    queryKey: ['quotas'],
    queryFn: quotasApi.getQuotas,
  })

  const storageQuota = quotas?.find((q: any) => q.resource_type === 'storage_gb')

  // Create VM mutation
  const createMutation = useMutation({
    mutationFn: async (vmData: any) => {
      // Create VM with network_id included
      // Network is configured during async Proxmox provisioning
      const vm = await vmsApi.create(vmData)
      return vm
    },
    onSuccess: (data) => {
      navigate(`/vms/${data.id}`)
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to create VM')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Validate
    if (bootMethod === 'iso' && !selectedIsoId) {
      setError('Please select an ISO image or choose "Boot from Disk"')
      return
    }

    // Prepare disk data
    const diskData = disks.map((disk) => ({
      size_gb: disk.size_gb,
      storage_pool: disk.storage_pool || undefined,
      disk_interface: disk.disk_interface,
      disk_format: 'raw',
      is_boot_disk: disk.is_boot_disk,
    }))

    // Prepare request data - network_id is passed to backend for async provisioning
    const requestData = {
      ...formData,
      disks: diskData,
      iso_image_id: bootMethod === 'iso' ? selectedIsoId! : undefined,
      boot_order: bootMethod === 'iso' ? 'cdrom,disk' : 'disk',
      network_id: selectedNetworkId || undefined,  // Include network for Celery task
    }

    createMutation.mutate(requestData)
  }

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value, type } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'number' ? parseInt(value) || 0 : value,
    }))
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">Create Virtual Machine</h1>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-5xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="bg-white shadow rounded-lg">
          <form onSubmit={handleSubmit} className="space-y-6 p-6">
            {error && (
              <div className="rounded-md bg-red-50 p-4">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {/* Basic Information */}
            <div className="border-b border-gray-200 pb-6">
              <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                Basic Information
              </h3>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                    VM Name <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    id="name"
                    name="name"
                    required
                    value={formData.name}
                    onChange={handleChange}
                    placeholder="web-server-01"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
                  />
                </div>

                <div>
                  <label htmlFor="hostname" className="block text-sm font-medium text-gray-700">
                    Hostname
                  </label>
                  <input
                    type="text"
                    id="hostname"
                    name="hostname"
                    value={formData.hostname}
                    onChange={handleChange}
                    placeholder="web01.example.com"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
                  />
                </div>

                <div className="sm:col-span-2">
                  <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                    Description
                  </label>
                  <textarea
                    id="description"
                    name="description"
                    rows={2}
                    value={formData.description}
                    onChange={handleChange}
                    placeholder="Production web server"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
                  />
                </div>
              </div>
            </div>

            {/* OS Selection */}
            <OSSelectionSection
              selectedOS={formData.os_type}
              onSelect={(osId) => setFormData((prev) => ({ ...prev, os_type: osId }))}
            />

            {/* Boot Configuration */}
            <BootConfigurationSection
              bootMethod={bootMethod}
              selectedIsoId={selectedIsoId}
              onBootMethodChange={setBootMethod}
              onIsoSelect={setSelectedIsoId}
            />

            {/* Resource Configuration */}
            <div className="border-b border-gray-200 pb-6">
              <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                Resource Configuration
              </h3>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="cpu_cores" className="block text-sm font-medium text-gray-700">
                    CPU Cores <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    id="cpu_cores"
                    name="cpu_cores"
                    required
                    min="1"
                    max="64"
                    value={formData.cpu_cores}
                    onChange={handleChange}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
                  />
                  <p className="mt-1 text-xs text-gray-500">1-64 vCPU cores</p>
                </div>

                <div>
                  <label htmlFor="memory_mb" className="block text-sm font-medium text-gray-700">
                    Memory (MB) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    id="memory_mb"
                    name="memory_mb"
                    required
                    min="512"
                    step="512"
                    value={formData.memory_mb}
                    onChange={handleChange}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    {Math.round(formData.memory_mb / 1024)} GB RAM
                  </p>
                </div>
              </div>

              {/* Quick Presets */}
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Quick Presets
                </label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {[
                    { name: 'Small', cpu: 1, mem: 1024 },
                    { name: 'Medium', cpu: 2, mem: 2048 },
                    { name: 'Large', cpu: 4, mem: 8192 },
                    { name: 'X-Large', cpu: 8, mem: 16384 },
                  ].map((preset) => (
                    <button
                      key={preset.name}
                      type="button"
                      onClick={() =>
                        setFormData((prev) => ({
                          ...prev,
                          cpu_cores: preset.cpu,
                          memory_mb: preset.mem,
                        }))
                      }
                      className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                    >
                      {preset.name}
                      <br />
                      <span className="text-xs text-gray-500">
                        {preset.cpu} vCPU / {preset.mem / 1024} GB
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Disk Configuration */}
            <DiskConfigurationSection
              disks={disks}
              onDisksChange={setDisks}
              totalStorageQuota={storageQuota?.limit_value}
              usedStorageQuota={storageQuota?.used_value}
            />

            {/* Network Configuration */}
            <div className="border-b border-gray-200 pb-6">
              <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4 flex items-center gap-2">
                <Network size={20} />
                Network Configuration
              </h3>

              <div className="space-y-4">
                {/* Network Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    VPC Network
                  </label>

                  {networksLoading ? (
                    <div className="text-sm text-gray-500">Loading networks...</div>
                  ) : networks.length === 0 ? (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                      <div className="flex items-center gap-2 text-yellow-800">
                        <WifiOff size={18} />
                        <span className="font-medium">No networks available</span>
                      </div>
                      <p className="text-sm text-yellow-700 mt-1">
                        VM will use default bridge (vmbr0) without VLAN isolation.
                        <a href="/networking" className="ml-1 text-yellow-800 underline hover:text-yellow-900">
                          Create a network
                        </a>
                      </p>
                    </div>
                  ) : (
                    <>
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {/* No Network Option */}
                        <div
                          onClick={() => setSelectedNetworkId(null)}
                          className={`cursor-pointer rounded-lg border-2 p-4 transition-all ${
                            selectedNetworkId === null
                              ? 'border-indigo-500 bg-indigo-50'
                              : 'border-gray-200 hover:border-gray-300'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <WifiOff size={18} className="text-gray-400" />
                            <span className="font-medium text-gray-900">No Network</span>
                          </div>
                          <p className="text-xs text-gray-500 mt-1">
                            Use default bridge (vmbr0)
                          </p>
                        </div>

                        {/* Network Options */}
                        {networks.map((network: any) => (
                          <div
                            key={network.id}
                            onClick={() => setSelectedNetworkId(network.id)}
                            className={`cursor-pointer rounded-lg border-2 p-4 transition-all ${
                              selectedNetworkId === network.id
                                ? 'border-indigo-500 bg-indigo-50'
                                : 'border-gray-200 hover:border-gray-300'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Wifi size={18} className="text-indigo-500" />
                                <span className="font-medium text-gray-900">{network.name}</span>
                              </div>
                              {network.is_default && (
                                <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                                  Default
                                </span>
                              )}
                            </div>
                            <div className="mt-2 space-y-1">
                              <p className="text-xs text-gray-500">
                                VLAN: <span className="font-mono text-indigo-600">{network.vlan_id}</span>
                              </p>
                              <p className="text-xs text-gray-500">
                                CIDR: <span className="font-mono">{network.cidr}</span>
                              </p>
                              {network.gateway && (
                                <p className="text-xs text-gray-500">
                                  Gateway: <span className="font-mono">{network.gateway}</span>
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* IP Allocation Option */}
                      {selectedNetworkId && (
                        <div className="mt-4 bg-gray-50 rounded-lg p-4">
                          <div className="flex items-center justify-between">
                            <div>
                              <label className="font-medium text-gray-900">
                                Auto-allocate IP Address
                              </label>
                              <p className="text-xs text-gray-500 mt-0.5">
                                Automatically assign an IP from the network pool
                              </p>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                              <input
                                type="checkbox"
                                checked={allocateIp}
                                onChange={(e) => setAllocateIp(e.target.checked)}
                                className="sr-only peer"
                              />
                              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                            </label>
                          </div>
                          {selectedNetwork && (
                            <div className="mt-3 pt-3 border-t border-gray-200 text-sm text-gray-600">
                              Selected: <strong>{selectedNetwork.name}</strong> (VLAN {selectedNetwork.vlan_id})
                            </div>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Form Actions */}
            <div className="flex justify-end gap-3 pt-4">
              <button
                type="button"
                onClick={() => navigate('/vms')}
                className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending}
                className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
              >
                {createMutation.isPending ? 'Creating...' : 'Create VM'}
              </button>
            </div>
          </form>
        </div>

        {/* Help Text */}
        <div className="mt-6 bg-blue-50 border-l-4 border-blue-400 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-blue-400"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-blue-700">
                <strong>Note:</strong> VM provisioning happens asynchronously. Your VM will be
                created in the background with the configured disks and boot options. You can
                monitor the status on the VMs page.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
