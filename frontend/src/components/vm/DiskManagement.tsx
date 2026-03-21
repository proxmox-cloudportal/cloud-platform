import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { disksApi, isosApi, storageApi } from '../../services/api'

interface Disk {
  id: string
  disk_index: number
  disk_interface: string
  disk_number: number
  storage_pool: string
  size_gb: number
  disk_format: string | null
  is_boot_disk: boolean
  is_cdrom: boolean
  iso_image_id: string | null
  iso_image?: {
    id: string
    display_name: string
  }
  proxmox_disk_id: string | null
  status: string
  attached_at: string | null
}

interface DiskManagementProps {
  vmId: string
  clusterId: string
  vmStatus: string
}

export default function DiskManagement({ vmId, clusterId, vmStatus }: DiskManagementProps) {
  const queryClient = useQueryClient()
  const [showAddDisk, setShowAddDisk] = useState(false)
  const [showAttachISO, setShowAttachISO] = useState(false)
  const [resizingDiskId, setResizingDiskId] = useState<string | null>(null)

  const [newDisk, setNewDisk] = useState({
    size_gb: 20,
    storage_pool: 'local-lvm',
    disk_interface: 'scsi',
    disk_format: 'raw',
  })

  const [selectedIsoId, setSelectedIsoId] = useState('')
  const [newSize, setNewSize] = useState<number>(0)

  // Fetch VM disks
  const { data: disksData, isLoading: disksLoading } = useQuery({
    queryKey: ['vm-disks', vmId],
    queryFn: () => disksApi.listVmDisks(vmId),
  })

  // Fetch available ISOs
  const { data: isosData } = useQuery({
    queryKey: ['isos'],
    queryFn: () => isosApi.list({ include_public: true }),
    enabled: showAttachISO,
  })

  // Fetch storage pools
  const { data: storageData } = useQuery({
    queryKey: ['storage-pools', clusterId],
    queryFn: () => storageApi.listPools(clusterId, 'images'),
    enabled: showAddDisk,
  })

  // Add disk mutation
  const addDiskMutation = useMutation({
    mutationFn: () => disksApi.attachDisk(vmId, newDisk),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm-disks', vmId] })
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
      setShowAddDisk(false)
      setNewDisk({
        size_gb: 20,
        storage_pool: 'local-lvm',
        disk_interface: 'scsi',
        disk_format: 'raw',
      })
      alert('Disk attached successfully!')
    },
    onError: (error: any) => {
      alert('Failed to attach disk: ' + (error.response?.data?.detail || error.message))
    },
  })

  // Detach disk mutation
  const detachDiskMutation = useMutation({
    mutationFn: (diskId: string) => disksApi.detachDisk(vmId, diskId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm-disks', vmId] })
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
      alert('Disk detached successfully!')
    },
    onError: (error: any) => {
      alert('Failed to detach disk: ' + (error.response?.data?.detail || error.message))
    },
  })

  // Attach ISO mutation
  const attachISOMutation = useMutation({
    mutationFn: () => disksApi.attachISO(vmId, selectedIsoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm-disks', vmId] })
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
      setShowAttachISO(false)
      setSelectedIsoId('')
      alert('ISO attached successfully!')
    },
    onError: (error: any) => {
      alert('Failed to attach ISO: ' + (error.response?.data?.detail || error.message))
    },
  })

  // Resize disk mutation
  const resizeDiskMutation = useMutation({
    mutationFn: ({ diskId, newSizeGb }: { diskId: string; newSizeGb: number }) =>
      disksApi.resizeDisk(vmId, diskId, newSizeGb),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vm-disks', vmId] })
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
      setResizingDiskId(null)
      setNewSize(0)
      alert('Disk resized successfully!')
    },
    onError: (error: any) => {
      alert('Failed to resize disk: ' + (error.response?.data?.detail || error.message))
    },
  })

  const handleDetachDisk = (disk: Disk) => {
    if (disk.is_boot_disk) {
      alert('Cannot detach the boot disk')
      return
    }

    if (confirm(`Detach disk "${disk.proxmox_disk_id || disk.id}"? This action cannot be undone.`)) {
      detachDiskMutation.mutate(disk.id)
    }
  }

  const handleAddDisk = (e: React.FormEvent) => {
    e.preventDefault()
    addDiskMutation.mutate()
  }

  const handleAttachISO = (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedIsoId) {
      alert('Please select an ISO image')
      return
    }
    attachISOMutation.mutate()
  }

  const handleResizeDisk = (disk: Disk, e: React.FormEvent) => {
    e.preventDefault()
    if (newSize <= disk.size_gb) {
      alert(`New size must be larger than current size (${disk.size_gb}GB)`)
      return
    }
    resizeDiskMutation.mutate({ diskId: disk.id, newSizeGb: newSize })
  }

  const startResize = (disk: Disk) => {
    setResizingDiskId(disk.id)
    setNewSize(disk.size_gb + 10) // Default to current + 10GB
  }

  const cancelResize = () => {
    setResizingDiskId(null)
    setNewSize(0)
  }

  const disks = disksData?.data || []
  const regularDisks = disks.filter((d: Disk) => !d.is_cdrom)
  const cdromDisk = disks.find((d: Disk) => d.is_cdrom)

  return (
    <div className="bg-white shadow rounded-lg">
      <div className="px-4 py-5 sm:p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg leading-6 font-medium text-gray-900">Disks & Storage</h3>
          <div className="flex gap-2">
            <button
              onClick={() => setShowAttachISO(!showAttachISO)}
              className="px-3 py-1 text-sm border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50"
            >
              {showAttachISO ? 'Cancel' : 'Attach ISO'}
            </button>
            <button
              onClick={() => setShowAddDisk(!showAddDisk)}
              className="px-3 py-1 text-sm border border-transparent rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
            >
              {showAddDisk ? 'Cancel' : 'Add Disk'}
            </button>
          </div>
        </div>

        {/* Add Disk Form */}
        {showAddDisk && (
          <form onSubmit={handleAddDisk} className="mb-4 p-4 border border-gray-200 rounded-md bg-gray-50">
            <h4 className="text-sm font-medium text-gray-900 mb-3">Add New Disk</h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Size (GB)
                </label>
                <input
                  type="number"
                  value={newDisk.size_gb}
                  onChange={(e) => setNewDisk({ ...newDisk, size_gb: parseInt(e.target.value) })}
                  min="1"
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Storage Pool
                </label>
                <select
                  value={newDisk.storage_pool}
                  onChange={(e) => setNewDisk({ ...newDisk, storage_pool: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                >
                  <option value="local-lvm">local-lvm</option>
                  {storageData?.data?.map((pool: any) => (
                    <option key={pool.storage_name} value={pool.storage_name}>
                      {pool.storage_name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Interface
                </label>
                <select
                  value={newDisk.disk_interface}
                  onChange={(e) => setNewDisk({ ...newDisk, disk_interface: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                >
                  <option value="scsi">SCSI</option>
                  <option value="sata">SATA</option>
                  <option value="virtio">VirtIO</option>
                  <option value="ide">IDE</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Format
                </label>
                <select
                  value={newDisk.disk_format}
                  onChange={(e) => setNewDisk({ ...newDisk, disk_format: e.target.value })}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                >
                  <option value="raw">RAW</option>
                  <option value="qcow2">QCOW2</option>
                </select>
              </div>
            </div>
            <div className="mt-3">
              <button
                type="submit"
                disabled={addDiskMutation.isPending}
                className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
              >
                {addDiskMutation.isPending ? 'Attaching...' : 'Attach Disk'}
              </button>
            </div>
          </form>
        )}

        {/* Attach ISO Form */}
        {showAttachISO && (
          <form onSubmit={handleAttachISO} className="mb-4 p-4 border border-gray-200 rounded-md bg-gray-50">
            <h4 className="text-sm font-medium text-gray-900 mb-3">Attach ISO Image</h4>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Select ISO
              </label>
              <select
                value={selectedIsoId}
                onChange={(e) => setSelectedIsoId(e.target.value)}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                required
              >
                <option value="">-- Select ISO --</option>
                {isosData?.data?.filter((iso: any) => iso.upload_status === 'ready').map((iso: any) => (
                  <option key={iso.id} value={iso.id}>
                    {iso.display_name} ({iso.os_type})
                  </option>
                ))}
              </select>
            </div>
            <div className="mt-3">
              <button
                type="submit"
                disabled={attachISOMutation.isPending || !selectedIsoId}
                className="px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
              >
                {attachISOMutation.isPending ? 'Attaching...' : 'Attach ISO'}
              </button>
            </div>
          </form>
        )}

        {/* Disks List */}
        {disksLoading ? (
          <div className="text-center py-4 text-gray-500">Loading disks...</div>
        ) : (
          <div className="space-y-4">
            {/* Regular Disks */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Hard Disks</h4>
              {regularDisks.length === 0 ? (
                <p className="text-sm text-gray-500">No disks attached</p>
              ) : (
                <div className="space-y-2">
                  {regularDisks.map((disk: Disk) => (
                    <div
                      key={disk.id}
                      className="p-3 border border-gray-200 rounded-md bg-white"
                    >
                      <div className="flex justify-between items-center">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-gray-900">
                              {disk.proxmox_disk_id || `${disk.disk_interface}${disk.disk_number}`}
                            </span>
                            {disk.is_boot_disk && (
                              <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-800">
                                Boot
                              </span>
                            )}
                            <span
                              className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                                disk.status === 'ready'
                                  ? 'bg-green-100 text-green-800'
                                  : disk.status === 'creating'
                                  ? 'bg-yellow-100 text-yellow-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              {disk.status}
                            </span>
                          </div>
                          <div className="mt-1 text-xs text-gray-500">
                            {disk.size_gb} GB • {disk.disk_interface.toUpperCase()} • {disk.storage_pool}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => startResize(disk)}
                            disabled={resizeDiskMutation.isPending || resizingDiskId === disk.id}
                            className="text-sm text-blue-600 hover:text-blue-900 disabled:opacity-50"
                          >
                            Resize
                          </button>
                          {!disk.is_boot_disk && (
                            <button
                              onClick={() => handleDetachDisk(disk)}
                              disabled={detachDiskMutation.isPending}
                              className="text-sm text-red-600 hover:text-red-900 disabled:opacity-50"
                            >
                              Detach
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Resize Form */}
                      {resizingDiskId === disk.id && (
                        <form onSubmit={(e) => handleResizeDisk(disk, e)} className="mt-3 pt-3 border-t border-gray-200">
                          <div className="flex items-end gap-2">
                            <div className="flex-1">
                              <label className="block text-sm font-medium text-gray-700 mb-1">
                                New Size (GB)
                              </label>
                              <input
                                type="number"
                                value={newSize}
                                onChange={(e) => setNewSize(parseInt(e.target.value))}
                                min={disk.size_gb + 1}
                                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
                                required
                              />
                              <p className="mt-1 text-xs text-gray-500">
                                Current: {disk.size_gb} GB (can only increase)
                              </p>
                            </div>
                            <button
                              type="submit"
                              disabled={resizeDiskMutation.isPending}
                              className="px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                            >
                              {resizeDiskMutation.isPending ? 'Resizing...' : 'Apply'}
                            </button>
                            <button
                              type="button"
                              onClick={cancelResize}
                              disabled={resizeDiskMutation.isPending}
                              className="px-3 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                            >
                              Cancel
                            </button>
                          </div>
                        </form>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* CD-ROM */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">CD-ROM</h4>
              {cdromDisk ? (
                <div className="p-3 border border-gray-200 rounded-md bg-white">
                  <div className="flex justify-between items-center">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900">
                          {cdromDisk.proxmox_disk_id || 'ide2'}
                        </span>
                        <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-purple-100 text-purple-800">
                          CD-ROM
                        </span>
                      </div>
                      <div className="mt-1 text-xs text-gray-500">
                        {cdromDisk.iso_image?.display_name || 'No ISO mounted'}
                      </div>
                    </div>
                    <div>
                      <button
                        onClick={() => handleDetachDisk(cdromDisk)}
                        disabled={detachDiskMutation.isPending}
                        className="text-sm text-red-600 hover:text-red-900 disabled:opacity-50"
                      >
                        Eject
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-500">No ISO attached</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
