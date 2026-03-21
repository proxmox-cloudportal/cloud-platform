import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { snapshotsApi } from '../../services/api'

interface Snapshot {
  name: string
  description?: string
  snaptime?: number
  vmstate?: number
  parent?: string
}

interface SnapshotManagementProps {
  vmId: string
  vmStatus: string
}

export default function SnapshotManagement({ vmId, vmStatus }: SnapshotManagementProps) {
  const queryClient = useQueryClient()
  const [showCreateSnapshot, setShowCreateSnapshot] = useState(false)

  const [newSnapshot, setNewSnapshot] = useState({
    name: '',
    description: '',
    include_memory: false,
  })

  // Fetch VM snapshots
  const { data: snapshotsData, isLoading: snapshotsLoading } = useQuery({
    queryKey: ['vm-snapshots', vmId],
    queryFn: () => snapshotsApi.listVmSnapshots(vmId),
  })

  // Create snapshot mutation
  const createSnapshotMutation = useMutation({
    mutationFn: () => snapshotsApi.createSnapshot(vmId, newSnapshot),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm-snapshots', vmId] })
      setShowCreateSnapshot(false)
      setNewSnapshot({
        name: '',
        description: '',
        include_memory: false,
      })
      alert('Snapshot created successfully!')
    },
    onError: (error: any) => {
      alert('Failed to create snapshot: ' + (error.response?.data?.detail || error.message))
    },
  })

  // Rollback snapshot mutation
  const rollbackSnapshotMutation = useMutation({
    mutationFn: (snapshotName: string) => snapshotsApi.rollbackSnapshot(vmId, snapshotName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm-snapshots', vmId] })
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
      alert('VM rolled back successfully!')
    },
    onError: (error: any) => {
      alert('Failed to rollback snapshot: ' + (error.response?.data?.detail || error.message))
    },
  })

  // Delete snapshot mutation
  const deleteSnapshotMutation = useMutation({
    mutationFn: (snapshotName: string) => snapshotsApi.deleteSnapshot(vmId, snapshotName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm-snapshots', vmId] })
      alert('Snapshot deleted successfully!')
    },
    onError: (error: any) => {
      alert('Failed to delete snapshot: ' + (error.response?.data?.detail || error.message))
    },
  })

  const handleCreateSnapshot = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newSnapshot.name) {
      alert('Please enter a snapshot name')
      return
    }
    createSnapshotMutation.mutate()
  }

  const handleRollback = (snapshot: Snapshot) => {
    if (confirm(`Rollback VM to snapshot "${snapshot.name}"? This will revert all changes made after this snapshot was created.`)) {
      rollbackSnapshotMutation.mutate(snapshot.name)
    }
  }

  const handleDelete = (snapshot: Snapshot) => {
    if (confirm(`Delete snapshot "${snapshot.name}"? This action cannot be undone.`)) {
      deleteSnapshotMutation.mutate(snapshot.name)
    }
  }

  const formatDate = (timestamp?: number) => {
    if (!timestamp) return 'N/A'
    return new Date(timestamp * 1000).toLocaleString()
  }

  const snapshots = snapshotsData?.data || []

  return (
    <div className="bg-white shadow rounded-lg">
      <div className="px-4 py-5 sm:p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg leading-6 font-medium text-gray-900">Snapshots</h3>
          <button
            onClick={() => setShowCreateSnapshot(!showCreateSnapshot)}
            className="px-3 py-1 text-sm border border-transparent rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
          >
            {showCreateSnapshot ? 'Cancel' : 'Create Snapshot'}
          </button>
        </div>

        {/* Create Snapshot Form */}
        {showCreateSnapshot && (
          <form onSubmit={handleCreateSnapshot} className="mb-4 p-4 border border-gray-200 rounded-md bg-gray-50">
            <h4 className="text-sm font-medium text-gray-900 mb-3">Create New Snapshot</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Name *
                </label>
                <input
                  type="text"
                  value={newSnapshot.name}
                  onChange={(e) => setNewSnapshot({ ...newSnapshot, name: e.target.value })}
                  placeholder="snapshot-name"
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  required
                />
                <p className="mt-1 text-xs text-gray-500">
                  Use alphanumeric characters, hyphens, and underscores only
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  value={newSnapshot.description}
                  onChange={(e) => setNewSnapshot({ ...newSnapshot, description: e.target.value })}
                  placeholder="Optional description"
                  rows={2}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                />
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={newSnapshot.include_memory}
                  onChange={(e) => setNewSnapshot({ ...newSnapshot, include_memory: e.target.checked })}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <label className="ml-2 block text-sm text-gray-700">
                  Include memory state (for running VMs)
                </label>
              </div>
            </div>
            <div className="mt-3">
              <button
                type="submit"
                disabled={createSnapshotMutation.isPending}
                className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
              >
                {createSnapshotMutation.isPending ? 'Creating...' : 'Create Snapshot'}
              </button>
            </div>
          </form>
        )}

        {/* Snapshots List */}
        {snapshotsLoading ? (
          <div className="text-center py-4 text-gray-500">Loading snapshots...</div>
        ) : snapshots.length === 0 ? (
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
                d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            <p className="mt-2">No snapshots yet</p>
            <p className="text-sm">Create a snapshot to save the current state of your VM</p>
          </div>
        ) : (
          <div className="space-y-2">
            {snapshots.map((snapshot: Snapshot) => (
              <div
                key={snapshot.name}
                className="p-3 border border-gray-200 rounded-md bg-white"
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900">
                        {snapshot.name}
                      </span>
                      {snapshot.vmstate === 1 && (
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-purple-100 text-purple-800">
                          With Memory
                        </span>
                      )}
                    </div>
                    {snapshot.description && (
                      <p className="mt-1 text-xs text-gray-600">{snapshot.description}</p>
                    )}
                    <div className="mt-1 text-xs text-gray-500">
                      Created: {formatDate(snapshot.snaptime)}
                      {snapshot.parent && ` • Parent: ${snapshot.parent}`}
                    </div>
                  </div>
                  <div className="flex gap-2 ml-4">
                    <button
                      onClick={() => handleRollback(snapshot)}
                      disabled={rollbackSnapshotMutation.isPending}
                      className="text-sm text-blue-600 hover:text-blue-900 disabled:opacity-50"
                    >
                      Rollback
                    </button>
                    <button
                      onClick={() => handleDelete(snapshot)}
                      disabled={deleteSnapshotMutation.isPending}
                      className="text-sm text-red-600 hover:text-red-900 disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
