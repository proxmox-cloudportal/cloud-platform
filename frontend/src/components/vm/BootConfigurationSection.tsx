import { useQuery } from '@tanstack/react-query'
import { isosApi } from '../../services/api'

interface BootConfigurationSectionProps {
  bootMethod: 'disk' | 'iso'
  selectedIsoId: string | null
  onBootMethodChange: (method: 'disk' | 'iso') => void
  onIsoSelect: (isoId: string | null) => void
}

export default function BootConfigurationSection({
  bootMethod,
  selectedIsoId,
  onBootMethodChange,
  onIsoSelect,
}: BootConfigurationSectionProps) {
  // Fetch available ISOs
  const { data: isos, isLoading } = useQuery({
    queryKey: ['isos'],
    queryFn: () => isosApi.list({ include_public: true }),
  })

  const readyISOs = isos?.data?.filter((iso: any) => iso.upload_status === 'ready') || []

  return (
    <div className="border-b border-gray-200 pb-6">
      <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
        Boot Configuration
      </h3>
      <p className="text-sm text-gray-500 mb-4">
        Choose how the VM will boot initially.
      </p>

      {/* Boot Method Tabs */}
      <div className="mb-4">
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              type="button"
              onClick={() => {
                onBootMethodChange('disk')
                onIsoSelect(null)
              }}
              className={`
                whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm
                ${
                  bootMethod === 'disk'
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              Boot from Disk
            </button>
            <button
              type="button"
              onClick={() => onBootMethodChange('iso')}
              className={`
                whitespace-nowrap pb-4 px-1 border-b-2 font-medium text-sm
                ${
                  bootMethod === 'iso'
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }
              `}
            >
              Boot from ISO
            </button>
          </nav>
        </div>
      </div>

      {/* Boot Method Content */}
      {bootMethod === 'disk' ? (
        <div className="rounded-md bg-blue-50 p-4">
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
              <h3 className="text-sm font-medium text-blue-800">
                Boot from disk only
              </h3>
              <div className="mt-2 text-sm text-blue-700">
                <p>
                  The VM will boot directly from the primary disk. Make sure you
                  have a bootable OS image or plan to install one later.
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div>
          <label htmlFor="iso-select" className="block text-sm font-medium text-gray-700 mb-2">
            Select ISO Image <span className="text-red-500">*</span>
          </label>

          {isLoading ? (
            <div className="text-sm text-gray-500">Loading ISOs...</div>
          ) : readyISOs.length === 0 ? (
            <div className="rounded-md bg-yellow-50 p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg
                    className="h-5 w-5 text-yellow-400"
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
                  <h3 className="text-sm font-medium text-yellow-800">
                    No ISO images available
                  </h3>
                  <div className="mt-2 text-sm text-yellow-700">
                    <p>
                      You need to upload an ISO image first.{' '}
                      <a href="/vm-templates/isos" className="font-medium underline">
                        Upload ISO
                      </a>
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <>
              <select
                id="iso-select"
                value={selectedIsoId || ''}
                onChange={(e) => onIsoSelect(e.target.value || null)}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border text-gray-900"
              >
                <option value="">-- Select an ISO --</option>
                {readyISOs.map((iso: any) => (
                  <option key={iso.id} value={iso.id}>
                    {iso.display_name}
                    {iso.os_type && ` (${iso.os_type}${iso.os_version ? ` ${iso.os_version}` : ''})`}
                    {' - '}
                    {(iso.file_size_bytes / (1024 ** 3)).toFixed(2)} GB
                    {iso.is_public && ' • Public'}
                  </option>
                ))}
              </select>

              <div className="mt-2 text-sm text-gray-500">
                The ISO will be mounted as a CD-ROM device and set as the first boot option.
                <br />
                <a
                  href="/vm-templates/isos"
                  className="text-indigo-600 hover:text-indigo-500 font-medium"
                >
                  Manage ISOs →
                </a>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
