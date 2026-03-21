import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { vmsApi } from '../services/api'

export default function CreateVMPage() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    name: '',
    hostname: '',
    description: '',
    cpu_cores: 2,
    memory_mb: 2048,
    disk_gb: 20,
    os_type: 'linux',
  })
  const [error, setError] = useState('')

  const createMutation = useMutation({
    mutationFn: vmsApi.create,
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
    createMutation.mutate(formData)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
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
      <main className="max-w-3xl mx-auto py-6 sm:px-6 lg:px-8">
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

              <div className="space-y-4">
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
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
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
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>

                <div>
                  <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                    Description
                  </label>
                  <textarea
                    id="description"
                    name="description"
                    rows={3}
                    value={formData.description}
                    onChange={handleChange}
                    placeholder="Production web server"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>

                <div>
                  <label htmlFor="os_type" className="block text-sm font-medium text-gray-700">
                    Operating System
                  </label>
                  <select
                    id="os_type"
                    name="os_type"
                    value={formData.os_type}
                    onChange={handleChange}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  >
                    <option value="linux">Linux</option>
                    <option value="windows">Windows</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>
            </div>

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
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                  <p className="mt-1 text-xs text-gray-500">Number of virtual CPU cores (1-64)</p>
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
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Memory in MB ({Math.round(formData.memory_mb / 1024)} GB)
                  </p>
                </div>

                <div>
                  <label htmlFor="disk_gb" className="block text-sm font-medium text-gray-700">
                    Disk Size (GB) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    id="disk_gb"
                    name="disk_gb"
                    required
                    min="10"
                    value={formData.disk_gb}
                    onChange={handleChange}
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                  <p className="mt-1 text-xs text-gray-500">Disk size in GB (minimum 10 GB)</p>
                </div>
              </div>

              {/* Quick Presets */}
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Quick Presets
                </label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <button
                    type="button"
                    onClick={() =>
                      setFormData((prev) => ({ ...prev, cpu_cores: 1, memory_mb: 1024, disk_gb: 20 }))
                    }
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                  >
                    Small
                    <br />
                    <span className="text-xs text-gray-500">1 vCPU / 1 GB</span>
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setFormData((prev) => ({ ...prev, cpu_cores: 2, memory_mb: 2048, disk_gb: 40 }))
                    }
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                  >
                    Medium
                    <br />
                    <span className="text-xs text-gray-500">2 vCPU / 2 GB</span>
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setFormData((prev) => ({ ...prev, cpu_cores: 4, memory_mb: 8192, disk_gb: 80 }))
                    }
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                  >
                    Large
                    <br />
                    <span className="text-xs text-gray-500">4 vCPU / 8 GB</span>
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setFormData((prev) => ({
                        ...prev,
                        cpu_cores: 8,
                        memory_mb: 16384,
                        disk_gb: 160,
                      }))
                    }
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
                  >
                    X-Large
                    <br />
                    <span className="text-xs text-gray-500">8 vCPU / 16 GB</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Form Actions */}
            <div className="flex justify-end gap-3">
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
                <strong>Note:</strong> VM creation may take a few minutes. The VM will be provisioned
                on the best available Proxmox cluster and node.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
