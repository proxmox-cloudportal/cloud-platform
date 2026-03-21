import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { vmsApi } from '../../services/api'

interface VMActionsMenuProps {
  vmId: string
  vmName: string
  vmStatus: string
  onActionComplete?: () => void
  onDelete?: () => void
}

interface ResizeDialogProps {
  isOpen: boolean
  onClose: () => void
  vmId: string
  currentCpuCores: number
  currentMemoryMb: number
  onSuccess: () => void
}

function ResizeDialog({ isOpen, onClose, vmId, currentCpuCores, currentMemoryMb, onSuccess }: ResizeDialogProps) {
  const [cpuCores, setCpuCores] = useState(currentCpuCores)
  const [memoryMb, setMemoryMb] = useState(currentMemoryMb)

  const resizeMutation = useMutation({
    mutationFn: () => vmsApi.resize(vmId, {
      cpu_cores: cpuCores !== currentCpuCores ? cpuCores : undefined,
      memory_mb: memoryMb !== currentMemoryMb ? memoryMb : undefined,
    }),
    onSuccess: () => {
      alert('VM resized successfully! Please start the VM to apply changes.')
      onSuccess()
      onClose()
    },
    onError: (error: any) => {
      alert('Failed to resize VM: ' + (error.response?.data?.detail || error.message))
    },
  })

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Resize VM Resources</h3>
        <p className="text-sm text-gray-600 mb-4">
          Note: VM must be stopped to resize resources.
        </p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              CPU Cores
            </label>
            <input
              type="number"
              value={cpuCores}
              onChange={(e) => setCpuCores(parseInt(e.target.value))}
              min="1"
              max="128"
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
            />
            <p className="mt-1 text-xs text-gray-500">Current: {currentCpuCores} cores</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Memory (MB)
            </label>
            <input
              type="number"
              value={memoryMb}
              onChange={(e) => setMemoryMb(parseInt(e.target.value))}
              min="512"
              max="524288"
              step="512"
              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
            />
            <p className="mt-1 text-xs text-gray-500">Current: {currentMemoryMb} MB ({Math.round(currentMemoryMb / 1024)} GB)</p>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={resizeMutation.isPending}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={() => resizeMutation.mutate()}
            disabled={resizeMutation.isPending || (cpuCores === currentCpuCores && memoryMb === currentMemoryMb)}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {resizeMutation.isPending ? 'Resizing...' : 'Resize'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function VMActionsMenu({ vmId, vmName, vmStatus, onActionComplete, onDelete }: VMActionsMenuProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [showResizeDialog, setShowResizeDialog] = useState(false)
  const [currentCpuCores, setCurrentCpuCores] = useState(2)
  const [currentMemoryMb, setCurrentMemoryMb] = useState(2048)
  const [dropdownPosition, setDropdownPosition] = useState({ top: 0, left: 0 })
  const buttonRef = useRef<HTMLButtonElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  // Advanced VM control mutations
  const restartMutation = useMutation({
    mutationFn: () => vmsApi.restart(vmId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vms'] })
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
      alert('VM restarted successfully!')
      onActionComplete?.()
      setIsOpen(false)
    },
    onError: (error: any) => {
      alert('Failed to restart VM: ' + (error.response?.data?.detail || error.message))
    },
  })
  const forceStopMutation = useMutation({
    mutationFn: () => vmsApi.forceStop(vmId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vms'] })
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
      alert('VM force stopped successfully!')
      onActionComplete?.()
      setIsOpen(false)
    },
    onError: (error: any) => {
      alert('Failed to force stop VM: ' + (error.response?.data?.detail || error.message))
    },
  })

  const resetMutation = useMutation({
    mutationFn: () => vmsApi.reset(vmId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vms'] })
      queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
      alert('VM reset successfully!')
      onActionComplete?.()
      setIsOpen(false)
    },
    onError: (error: any) => {
      alert('Failed to reset VM: ' + (error.response?.data?.detail || error.message))
    },
  })

  const handleRestart = () => {
    if (confirm(`Restart "${vmName}"?`)) {
      restartMutation.mutate()
    }
  }

  const handleForceStop = () => {
    if (confirm(`Force stop "${vmName}"? This will immediately stop the VM without graceful shutdown.`)) {
      forceStopMutation.mutate()
    }
  }

  const handleReset = () => {
    if (confirm(`Reset "${vmName}"? This performs a hard reset like pressing the reset button.`)) {
      resetMutation.mutate()
    }
  }

  const handleDelete = () => {
    if (confirm(`Delete "${vmName}"? This action cannot be undone.`)) {
      setIsOpen(false)
      onDelete?.()
    }
  }

  const handleResize = async () => {
    // Fetch current VM data
    try {
      const vm = await vmsApi.get(vmId)
      setCurrentCpuCores(vm.cpu_cores)
      setCurrentMemoryMb(vm.memory_mb)
      setShowResizeDialog(true)
      setIsOpen(false)
    } catch (error: any) {
      alert('Failed to load VM data: ' + (error.response?.data?.detail || error.message))
    }
  }

  const handleResizeSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ['vms'] })
    queryClient.invalidateQueries({ queryKey: ['vm', vmId] })
    onActionComplete?.()
  }

  return (
    <>
      <div className="relative inline-block text-left">
        <button
          ref={buttonRef}
          onClick={(e) => {
            e.stopPropagation()
            if (!isOpen && buttonRef.current) {
              const rect = buttonRef.current.getBoundingClientRect()
              setDropdownPosition({
                top: rect.bottom + window.scrollY + 8,
                left: rect.right + window.scrollX - 192 // 192px = w-48 (12rem)
              })
            }
            setIsOpen(!isOpen)
          }}
          className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          <svg className="w-4 h-4 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
          </svg>
          <span>More</span>
        </button>

        {isOpen && createPortal(
          <div
            ref={dropdownRef}
            className="fixed w-48 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-50"
            style={{
              top: `${dropdownPosition.top}px`,
              left: `${dropdownPosition.left}px`
            }}
          >
            <div className="py-1">
              {vmStatus === 'running' && (
                <>
                  <button
                    onClick={handleRestart}
                    className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  >
                    Restart
                  </button>
                  <div className="border-t border-gray-100 my-1"></div>
                </>
              )}
              <button
                onClick={handleForceStop}
                className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
              >
                Force Stop
              </button>
              <button
                onClick={handleReset}
                className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
              >
                Reset
              </button>
              <div className="border-t border-gray-100 my-1"></div>
              <button
                onClick={handleResize}
                className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
              >
                Resize CPU/RAM
              </button>
              <div className="border-t border-gray-100 my-1"></div>
              <button
                onClick={handleDelete}
                className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-100"
              >
                Delete
              </button>
            </div>
          </div>,
          document.body
        )}
      </div>

      <ResizeDialog
        isOpen={showResizeDialog}
        onClose={() => setShowResizeDialog(false)}
        vmId={vmId}
        currentCpuCores={currentCpuCores}
        currentMemoryMb={currentMemoryMb}
        onSuccess={handleResizeSuccess}
      />
    </>
  )
}
