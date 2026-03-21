import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { CheckCircle, XCircle, Loader } from 'lucide-react'
import { clustersApi } from '../services/api'

export default function CreateClusterPage() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    name: '',
    api_url: '',
    api_username: 'root@pam',
    datacenter: '',
    region: '',
    api_token_id: '',
    api_token_secret: '',
    api_password: '',
    verify_ssl: false,
    auth_method: 'token' as 'token' | 'password',
  })
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; version?: string; nodes?: string[] } | null>(null)

  const testMutation = useMutation({
    mutationFn: () => clustersApi.test({
      api_url: formData.api_url,
      api_username: formData.api_username,
      api_token_id: formData.auth_method === 'token' ? formData.api_token_id : undefined,
      api_token_secret: formData.auth_method === 'token' ? formData.api_token_secret : undefined,
      api_password: formData.auth_method === 'password' ? formData.api_password : undefined,
      verify_ssl: formData.verify_ssl,
    }),
    onSuccess: (data) => {
      setTestResult(data)
    },
  })

  const createMutation = useMutation({
    mutationFn: () => clustersApi.create({
      name: formData.name,
      api_url: formData.api_url,
      api_username: formData.api_username,
      datacenter: formData.datacenter || undefined,
      region: formData.region || undefined,
      api_token_id: formData.auth_method === 'token' ? formData.api_token_id : undefined,
      api_token_secret: formData.auth_method === 'token' ? formData.api_token_secret : undefined,
      api_password: formData.auth_method === 'password' ? formData.api_password : undefined,
      verify_ssl: formData.verify_ssl,
    }),
    onSuccess: () => {
      navigate('/clusters')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    createMutation.mutate()
  }

  const handleTestConnection = () => {
    setTestResult(null)
    testMutation.mutate()
  }

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Add Proxmox Cluster</h1>
        <p className="text-gray-600 mt-1">Connect a new Proxmox VE cluster to the platform</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white shadow rounded-lg p-6 space-y-6">
        {/* Basic Information */}
        <div>
          <h3 className="text-lg font-medium text-gray-900 mb-4">Basic Information</h3>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700">
                Cluster Name *
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                placeholder="Production Cluster"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Datacenter</label>
              <input
                type="text"
                value={formData.datacenter}
                onChange={(e) => setFormData({ ...formData, datacenter: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                placeholder="DC1"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Region</label>
              <input
                type="text"
                value={formData.region}
                onChange={(e) => setFormData({ ...formData, region: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                placeholder="US-East"
              />
            </div>
          </div>
        </div>

        {/* Connection Details */}
        <div>
          <h3 className="text-lg font-medium text-gray-900 mb-4">Connection Details</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                API URL *
              </label>
              <input
                type="url"
                required
                value={formData.api_url}
                onChange={(e) => setFormData({ ...formData, api_url: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                placeholder="https://proxmox.example.com:8006"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Username *
              </label>
              <input
                type="text"
                required
                value={formData.api_username}
                onChange={(e) => setFormData({ ...formData, api_username: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                placeholder="root@pam"
              />
            </div>
          </div>
        </div>

        {/* Authentication Method */}
        <div>
          <h3 className="text-lg font-medium text-gray-900 mb-4">Authentication</h3>
          <div className="mb-4 space-y-3">
            <label className="flex items-center cursor-pointer">
              <input
                type="radio"
                checked={formData.auth_method === 'token'}
                onChange={() => setFormData({ ...formData, auth_method: 'token' })}
                className="form-radio h-4 w-4 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="ml-3 text-sm font-medium text-gray-700">API Token (Recommended)</span>
            </label>
            <label className="flex items-center cursor-pointer">
              <input
                type="radio"
                checked={formData.auth_method === 'password'}
                onChange={() => setFormData({ ...formData, auth_method: 'password' })}
                className="form-radio h-4 w-4 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="ml-3 text-sm font-medium text-gray-700">Password</span>
            </label>
          </div>

          {formData.auth_method === 'token' ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-gray-700">Token ID *</label>
                <input
                  type="text"
                  required
                  value={formData.api_token_id}
                  onChange={(e) => setFormData({ ...formData, api_token_id: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                  placeholder="my-token"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Token Secret *</label>
                <input
                  type="password"
                  required
                  value={formData.api_token_secret}
                  onChange={(e) => setFormData({ ...formData, api_token_secret: e.target.value })}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                  placeholder="••••••••"
                />
              </div>
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-gray-700">Password *</label>
              <input
                type="password"
                required
                value={formData.api_password}
                onChange={(e) => setFormData({ ...formData, api_password: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                placeholder="••••••••"
              />
            </div>
          )}

          <div className="mt-4">
            <label className="inline-flex items-center">
              <input
                type="checkbox"
                checked={formData.verify_ssl}
                onChange={(e) => setFormData({ ...formData, verify_ssl: e.target.checked })}
                className="form-checkbox h-4 w-4 text-indigo-600"
              />
              <span className="ml-2 text-sm text-gray-700">Verify SSL Certificate</span>
            </label>
          </div>
        </div>

        {/* Test Connection */}
        <div>
          <button
            type="button"
            onClick={handleTestConnection}
            disabled={testMutation.isPending || !formData.api_url || !formData.api_username}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {testMutation.isPending ? (
              <>
                <Loader className="w-4 h-4 mr-2 animate-spin" />
                Testing...
              </>
            ) : (
              'Test Connection'
            )}
          </button>

          {testResult && (
            <div className={`mt-4 p-4 rounded-md ${testResult.success ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className="flex">
                <div className="flex-shrink-0">
                  {testResult.success ? (
                    <CheckCircle className="h-5 w-5 text-green-400" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-400" />
                  )}
                </div>
                <div className="ml-3">
                  <h3 className={`text-sm font-medium ${testResult.success ? 'text-green-800' : 'text-red-800'}`}>
                    {testResult.success ? 'Connection Successful' : 'Connection Failed'}
                  </h3>
                  <div className={`mt-2 text-sm ${testResult.success ? 'text-green-700' : 'text-red-700'}`}>
                    <p>{testResult.message}</p>
                    {testResult.version && <p className="mt-1">Proxmox VE Version: {testResult.version}</p>}
                    {testResult.nodes && testResult.nodes.length > 0 && (
                      <p className="mt-1">Nodes: {testResult.nodes.join(', ')}</p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Form Actions */}
        <div className="flex justify-end space-x-3 pt-6 border-t">
          <button
            type="button"
            onClick={() => navigate('/clusters')}
            className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {createMutation.isPending ? 'Adding...' : 'Add Cluster'}
          </button>
        </div>

        {createMutation.isError && (
          <div className="rounded-md bg-red-50 p-4">
            <p className="text-sm text-red-800">
              Failed to add cluster. Please check your details and try again.
            </p>
          </div>
        )}
      </form>
    </div>
  )
}
