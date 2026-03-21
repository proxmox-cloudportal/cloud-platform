import { useState, useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'
import { networksApi } from '../services/api'
import { Plus, Network, Trash2, Settings } from 'lucide-react'

interface Network {
  id: string
  name: string
  description?: string
  vlan_id: number
  bridge: string
  cidr: string
  gateway?: string
  dns_servers?: string[]
  is_shared: boolean
  is_default: boolean
  created_at: string
}

interface CreateNetworkForm {
  name: string
  cidr: string
  description: string
  gateway: string
  dns_servers: string
  is_shared: boolean
  bridge: string
}

export default function NetworksPage() {
  const { currentOrganization } = useAuthStore()
  const [networks, setNetworks] = useState<Network[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [formData, setFormData] = useState<CreateNetworkForm>({
    name: '',
    cidr: '',
    description: '',
    gateway: '',
    dns_servers: '',
    is_shared: false,
    bridge: 'vmbr0'
  })
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    loadNetworks()
  }, [currentOrganization])

  const loadNetworks = async () => {
    if (!currentOrganization) return

    try {
      setLoading(true)
      const response = await networksApi.list()
      setNetworks(response.data || [])
    } catch (error) {
      console.error('Failed to load networks:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)

    try {
      const dnsServers = formData.dns_servers
        .split(',')
        .map(s => s.trim())
        .filter(s => s)

      await networksApi.create({
        name: formData.name,
        cidr: formData.cidr,
        description: formData.description || undefined,
        gateway: formData.gateway || undefined,
        dns_servers: dnsServers.length > 0 ? dnsServers : undefined,
        is_shared: formData.is_shared,
        bridge: formData.bridge
      })

      setShowCreateModal(false)
      setFormData({
        name: '',
        cidr: '',
        description: '',
        gateway: '',
        dns_servers: '',
        is_shared: false,
        bridge: 'vmbr0'
      })
      loadNetworks()
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to create network')
    } finally {
      setCreating(false)
    }
  }

  const handleDelete = async (networkId: string) => {
    if (!confirm('Are you sure you want to delete this network? VMs must be detached first.')) {
      return
    }

    try {
      await networksApi.delete(networkId)
      loadNetworks()
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Failed to delete network')
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">VPC Networks</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage virtual private cloud networks with VLAN isolation
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
        >
          <Plus size={20} />
          Create Network
        </button>
      </div>

      {networks.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <Network size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No networks yet</h3>
          <p className="text-gray-500 mb-4">
            Create your first VPC network to isolate your virtual machines
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg inline-flex items-center gap-2"
          >
            <Plus size={20} />
            Create Network
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {networks.map((network) => (
            <div
              key={network.id}
              className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-lg transition-shadow"
            >
              <div className="flex justify-between items-start mb-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-gray-900">{network.name}</h3>
                    {network.is_default && (
                      <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded">
                        Default
                      </span>
                    )}
                  </div>
                  {network.description && (
                    <p className="text-sm text-gray-500 mt-1">{network.description}</p>
                  )}
                </div>
                <button
                  onClick={() => handleDelete(network.id)}
                  className="text-red-600 hover:text-red-700 p-2"
                  title="Delete network"
                >
                  <Trash2 size={18} />
                </button>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">VLAN ID:</span>
                  <span className="font-mono bg-blue-50 text-blue-700 px-2 py-1 rounded">
                    {network.vlan_id}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">CIDR:</span>
                  <span className="font-mono text-gray-900">{network.cidr}</span>
                </div>
                {network.gateway && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">Gateway:</span>
                    <span className="font-mono text-gray-900">{network.gateway}</span>
                  </div>
                )}
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500">Bridge:</span>
                  <span className="font-mono text-gray-900">{network.bridge}</span>
                </div>
                {network.is_shared && (
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-500">Shared:</span>
                    <span className="text-green-600">✓</span>
                  </div>
                )}
              </div>

              <div className="mt-4 pt-4 border-t border-gray-200">
                <button
                  className="w-full text-sm text-blue-600 hover:text-blue-700 flex items-center justify-center gap-2"
                  title="Network settings"
                >
                  <Settings size={16} />
                  Manage Settings
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Network Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <h2 className="text-2xl font-bold mb-6">Create VPC Network</h2>

              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Network Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Production Network"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    CIDR Block *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.cidr}
                    onChange={(e) => setFormData({ ...formData, cidr: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="10.100.0.0/24"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    CIDR notation (e.g., 10.100.0.0/24). VLAN will be auto-allocated.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Gateway IP
                  </label>
                  <input
                    type="text"
                    value={formData.gateway}
                    onChange={(e) => setFormData({ ...formData, gateway: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="10.100.0.1 (auto if empty)"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Description
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows={3}
                    placeholder="Primary production network for web services"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    DNS Servers
                  </label>
                  <input
                    type="text"
                    value={formData.dns_servers}
                    onChange={(e) => setFormData({ ...formData, dns_servers: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="8.8.8.8, 8.8.4.4"
                  />
                  <p className="text-xs text-gray-500 mt-1">Comma-separated list</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Proxmox Bridge
                  </label>
                  <input
                    type="text"
                    value={formData.bridge}
                    onChange={(e) => setFormData({ ...formData, bridge: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="vmbr0"
                  />
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="is_shared"
                    checked={formData.is_shared}
                    onChange={(e) => setFormData({ ...formData, is_shared: e.target.checked })}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                  />
                  <label htmlFor="is_shared" className="ml-2 block text-sm text-gray-900">
                    Share network within organization
                  </label>
                </div>

                <div className="flex gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                    disabled={creating}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    disabled={creating}
                  >
                    {creating ? 'Creating...' : 'Create Network'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
