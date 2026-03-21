import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { isosApi } from '../services/api'

export default function ISOUploadPage() {
  const navigate = useNavigate()
  const [uploadMethod, setUploadMethod] = useState<'file' | 'url'>('file')
  const [file, setFile] = useState<File | null>(null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState('')

  const [formData, setFormData] = useState({
    url: '',
    display_name: '',
    description: '',
    os_type: '',
    os_version: '',
    architecture: 'x86_64',
    is_public: false,
  })

  // Fetch existing ISOs
  const { data: isos, refetch } = useQuery({
    queryKey: ['isos'],
    queryFn: () => isosApi.list({ include_public: true }),
  })

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async (data: any) => {
      setUploadProgress(10)
      const result = await isosApi.upload(file!, data)
      setUploadProgress(100)
      return result
    },
    onSuccess: () => {
      refetch()
      // Reset form
      setFile(null)
      setFormData({
        url: '',
        display_name: '',
        description: '',
        os_type: '',
        os_version: '',
        architecture: 'x86_64',
        is_public: false,
      })
      setUploadProgress(0)
      alert('ISO uploaded successfully! It will be transferred to Proxmox storage in the background.')
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to upload ISO')
      setUploadProgress(0)
    },
  })

  // URL upload mutation
  const uploadFromURLMutation = useMutation({
    mutationFn: async (data: any) => {
      setUploadProgress(10)
      const result = await isosApi.uploadFromURL(data)
      setUploadProgress(100)
      return result
    },
    onSuccess: () => {
      refetch()
      // Reset form
      setFormData({
        url: '',
        display_name: '',
        description: '',
        os_type: '',
        os_version: '',
        architecture: 'x86_64',
        is_public: false,
      })
      setUploadProgress(0)
      alert('ISO download from URL initiated! Proxmox is fetching the file in the background.')
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || 'Failed to initiate ISO download from URL')
      setUploadProgress(0)
    },
  })

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      if (!selectedFile.name.toLowerCase().endsWith('.iso')) {
        setError('Please select an ISO file')
        return
      }

      // Check file size (10GB limit)
      const maxSize = 10 * 1024 * 1024 * 1024 // 10GB
      if (selectedFile.size > maxSize) {
        setError('File size exceeds 10GB limit')
        return
      }

      setFile(selectedFile)
      setError('')

      // Auto-fill display name from filename
      if (!formData.display_name) {
        const displayName = selectedFile.name.replace('.iso', '').replace(/[-_]/g, ' ')
        setFormData((prev) => ({ ...prev, display_name: displayName }))
      }
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!formData.display_name) {
      setError('Please enter a display name')
      return
    }

    if (uploadMethod === 'file') {
      if (!file) {
        setError('Please select an ISO file')
        return
      }

      uploadMutation.mutate({
        name: file.name,
        ...formData,
      })
    } else {
      // URL upload
      if (!formData.url) {
        setError('Please enter a URL')
        return
      }

      if (!formData.url.startsWith('http://') && !formData.url.startsWith('https://') && !formData.url.startsWith('ftp://')) {
        setError('URL must start with http://, https://, or ftp://')
        return
      }

      uploadFromURLMutation.mutate(formData)
    }
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready':
        return 'bg-green-100 text-green-800'
      case 'processing':
      case 'uploading':
        return 'bg-blue-100 text-blue-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900">ISO Images</h1>
          <button
            onClick={() => navigate('/vms')}
            className="text-indigo-600 hover:text-indigo-800"
          >
            ← Back to VMs
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Upload Form */}
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Upload New ISO</h2>

            {/* Upload Method Tabs */}
            <div className="border-b border-gray-200 mb-4">
              <nav className="-mb-px flex space-x-8">
                <button
                  type="button"
                  onClick={() => setUploadMethod('file')}
                  className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm ${
                    uploadMethod === 'file'
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Upload from File
                </button>
                <button
                  type="button"
                  onClick={() => setUploadMethod('url')}
                  className={`whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm ${
                    uploadMethod === 'url'
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  Upload from URL
                </button>
              </nav>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="rounded-md bg-red-50 p-4">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}

              {/* URL Input (for URL upload method) */}
              {uploadMethod === 'url' && (
                <div>
                  <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-2">
                    ISO URL <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="url"
                    id="url"
                    value={formData.url}
                    onChange={(e) => setFormData((prev) => ({ ...prev, url: e.target.value }))}
                    placeholder="https://releases.ubuntu.com/22.04/ubuntu-22.04.3-live-server-amd64.iso"
                    disabled={uploadFromURLMutation.isPending}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Proxmox will download the ISO directly from this URL
                  </p>
                </div>
              )}

              {/* File Input (for file upload method) */}
              {uploadMethod === 'file' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    ISO File <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="file"
                    accept=".iso"
                    onChange={handleFileSelect}
                    disabled={uploadMutation.isPending}
                    className="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none p-2"
                  />
                  {file && (
                    <p className="mt-2 text-sm text-gray-600">
                      Selected: {file.name} ({formatBytes(file.size)})
                    </p>
                  )}
                </div>
              )}

              {/* Display Name */}
              <div>
                <label htmlFor="display_name" className="block text-sm font-medium text-gray-700">
                  Display Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  id="display_name"
                  required
                  value={formData.display_name}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, display_name: e.target.value }))
                  }
                  placeholder="Ubuntu 22.04 LTS Server"
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>

              {/* Description */}
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                  Description
                </label>
                <textarea
                  id="description"
                  rows={2}
                  value={formData.description}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, description: e.target.value }))
                  }
                  placeholder="Ubuntu 22.04.3 LTS Server installation media"
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>

              {/* OS Type & Version */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="os_type" className="block text-sm font-medium text-gray-700">
                    OS Type
                  </label>
                  <select
                    id="os_type"
                    value={formData.os_type}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, os_type: e.target.value }))
                    }
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  >
                    <option value="">Select...</option>
                    <option value="linux">Linux</option>
                    <option value="windows">Windows</option>
                    <option value="other">Other</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="os_version" className="block text-sm font-medium text-gray-700">
                    OS Version
                  </label>
                  <input
                    type="text"
                    id="os_version"
                    value={formData.os_version}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, os_version: e.target.value }))
                    }
                    placeholder="22.04"
                    className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  />
                </div>
              </div>

              {/* Public Toggle */}
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="is_public"
                  checked={formData.is_public}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, is_public: e.target.checked }))
                  }
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <label htmlFor="is_public" className="ml-2 block text-sm text-gray-900">
                  Make this ISO public (available to all organizations)
                </label>
              </div>

              {/* Progress Bar */}
              {uploadProgress > 0 && uploadProgress < 100 && (
                <div className="w-full bg-gray-200 rounded-full h-2.5">
                  <div
                    className="bg-indigo-600 h-2.5 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  ></div>
                </div>
              )}

              {/* Submit Button */}
              <button
                type="submit"
                disabled={
                  (uploadMethod === 'file' && (!file || uploadMutation.isPending)) ||
                  (uploadMethod === 'url' && uploadFromURLMutation.isPending)
                }
                className="w-full px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploadMethod === 'file' ? (
                  uploadMutation.isPending ? 'Uploading...' : 'Upload ISO from File'
                ) : (
                  uploadFromURLMutation.isPending ? 'Initiating Download...' : 'Download ISO from URL'
                )}
              </button>
            </form>
          </div>

          {/* ISO List */}
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Available ISOs</h2>

            {isos?.data?.length === 0 ? (
              <p className="text-sm text-gray-500">No ISO images available yet.</p>
            ) : (
              <div className="space-y-3">
                {isos?.data?.map((iso: any) => (
                  <div
                    key={iso.id}
                    className="border border-gray-200 rounded-lg p-4 hover:border-indigo-300 transition-colors"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="text-sm font-medium text-gray-900">{iso.display_name}</h3>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(
                          iso.upload_status
                        )}`}
                      >
                        {iso.upload_status}
                      </span>
                    </div>

                    {iso.description && (
                      <p className="text-xs text-gray-600 mb-2">{iso.description}</p>
                    )}

                    <div className="flex flex-wrap gap-2 text-xs text-gray-500">
                      {iso.os_type && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-gray-100">
                          {iso.os_type}
                          {iso.os_version && ` ${iso.os_version}`}
                        </span>
                      )}
                      <span>{formatBytes(iso.file_size_bytes)}</span>
                      {iso.is_public && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                          Public
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Info Box */}
        <div className="mt-6 bg-blue-50 border-l-4 border-blue-400 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-blue-400"
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
              <h3 className="text-sm font-medium text-blue-800">About ISO Images</h3>
              <div className="mt-2 text-sm text-blue-700">
                <ul className="list-disc list-inside space-y-1">
                  <li>Maximum file size: 10 GB</li>
                  <li>ISOs are deduplicated by content (SHA256 checksum)</li>
                  <li>After upload, ISOs are transferred to Proxmox storage in the background</li>
                  <li>You can use ISOs to boot new VMs during creation</li>
                  <li>Public ISOs are shared across all organizations</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
