import { useQuery } from '@tanstack/react-query'
import { storageApi } from '../../services/api'

interface Disk {
  id: string
  size_gb: number
  storage_pool: string
  disk_interface: string
  is_boot_disk: boolean
}

interface DiskConfigurationSectionProps {
  disks: Disk[]
  onDisksChange: (disks: Disk[]) => void
  totalStorageQuota?: number
  usedStorageQuota?: number
}

export default function DiskConfigurationSection({
  disks,
  onDisksChange,
  totalStorageQuota,
  usedStorageQuota,
}: DiskConfigurationSectionProps) {
  // Fetch available storage pools
  const { data: storagePools, isLoading: loadingPools } = useQuery({
    queryKey: ['storage', 'pools'],
    queryFn: () => storageApi.listAllAccessible('images'),
  })

  const totalDiskSize = disks.reduce((sum, disk) => sum + disk.size_gb, 0)
  const remainingQuota = totalStorageQuota && usedStorageQuota !== undefined
    ? totalStorageQuota - usedStorageQuota - totalDiskSize
    : null

  const addDisk = () => {
    const newDisk: Disk = {
      id: `disk-${Date.now()}`,
      size_gb: 40,
      storage_pool: storagePools?.data?.[0]?.storage_name || 'local-lvm',
      disk_interface: 'scsi',
      is_boot_disk: disks.length === 0, // First disk is boot disk
    }
    onDisksChange([...disks, newDisk])
  }

  const removeDisk = (diskId: string) => {
    // Don't allow removing the last disk or boot disk
    const disk = disks.find((d) => d.id === diskId)
    if (disks.length === 1 || disk?.is_boot_disk) {
      return
    }
    onDisksChange(disks.filter((d) => d.id !== diskId))
  }

  const updateDisk = (diskId: string, field: string, value: any) => {
    onDisksChange(
      disks.map((disk) =>
        disk.id === diskId ? { ...disk, [field]: value } : disk
      )
    )
  }

  const setBootDisk = (diskId: string) => {
    onDisksChange(
      disks.map((disk) => ({
        ...disk,
        is_boot_disk: disk.id === diskId,
      }))
    )
  }

  return (
    <div className="border-b border-gray-200 pb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-medium leading-6 text-gray-900">
            Disk Configuration
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            Configure storage disks for your virtual machine
          </p>
        </div>
        <button
          type="button"
          onClick={addDisk}
          disabled={loadingPools || (remainingQuota !== null && remainingQuota < 10)}
          className="inline-flex items-center px-3 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <svg
            className="-ml-0.5 mr-2 h-4 w-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
          Add Disk
        </button>
      </div>

      {/* Quota Warning */}
      {remainingQuota !== null && remainingQuota < 50 && (
        <div className={`mb-4 rounded-md p-4 ${remainingQuota < 0 ? 'bg-red-50' : 'bg-yellow-50'}`}>
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className={`h-5 w-5 ${remainingQuota < 0 ? 'text-red-400' : 'text-yellow-400'}`}
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className={`text-sm font-medium ${remainingQuota < 0 ? 'text-red-800' : 'text-yellow-800'}`}>
                {remainingQuota < 0 ? 'Storage quota exceeded' : 'Low storage quota'}
              </h3>
              <div className={`mt-2 text-sm ${remainingQuota < 0 ? 'text-red-700' : 'text-yellow-700'}`}>
                <p>
                  Remaining quota: {remainingQuota} GB
                  {remainingQuota < 0 && ' (Exceeds available quota)'}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Disks List */}
      <div className="space-y-4">
        {disks.map((disk, index) => (
          <div
            key={disk.id}
            className="border border-gray-300 rounded-lg p-4 bg-gray-50"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-900">
                  Disk {index + 1}
                </span>
                {disk.is_boot_disk && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                    Boot Disk
                  </span>
                )}
              </div>
              <button
                type="button"
                onClick={() => removeDisk(disk.id)}
                disabled={disks.length === 1 || disk.is_boot_disk}
                className="text-red-600 hover:text-red-800 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <svg
                  className="h-5 w-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* Disk Size */}
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Size (GB) <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  min="10"
                  max="10240"
                  value={disk.size_gb}
                  onChange={(e) =>
                    updateDisk(disk.id, 'size_gb', parseInt(e.target.value) || 0)
                  }
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
                />
              </div>

              {/* Storage Pool */}
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Storage Pool <span className="text-red-500">*</span>
                </label>
                <select
                  value={disk.storage_pool}
                  onChange={(e) => updateDisk(disk.id, 'storage_pool', e.target.value)}
                  disabled={loadingPools}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
                >
                  {loadingPools ? (
                    <option>Loading...</option>
                  ) : (
                    storagePools?.data?.map((pool: any) => (
                      <option key={pool.id} value={pool.storage_name}>
                        {pool.storage_name} ({pool.storage_type})
                        {pool.available_bytes &&
                          ` - ${Math.round(pool.available_bytes / (1024 ** 3))} GB available`}
                      </option>
                    ))
                  )}
                </select>
              </div>

              {/* Disk Interface */}
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Interface
                </label>
                <select
                  value={disk.disk_interface}
                  onChange={(e) => updateDisk(disk.id, 'disk_interface', e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
                >
                  <option value="scsi">SCSI (Recommended)</option>
                  <option value="virtio">VirtIO</option>
                  <option value="sata">SATA</option>
                  <option value="ide">IDE</option>
                </select>
              </div>

              {/* Boot Disk Toggle */}
              <div className="flex items-end">
                <button
                  type="button"
                  onClick={() => setBootDisk(disk.id)}
                  disabled={disk.is_boot_disk}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm font-medium hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {disk.is_boot_disk ? '✓ Boot Disk' : 'Set as Boot Disk'}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Total Storage Display */}
      <div className="mt-4 p-4 bg-blue-50 rounded-md">
        <div className="flex justify-between text-sm">
          <span className="font-medium text-gray-700">Total Storage:</span>
          <span className="font-bold text-indigo-600">{totalDiskSize} GB</span>
        </div>
        {remainingQuota !== null && (
          <div className="flex justify-between text-sm mt-1">
            <span className="text-gray-600">Remaining Quota:</span>
            <span className={remainingQuota < 0 ? 'text-red-600' : 'text-gray-900'}>
              {remainingQuota} GB
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
