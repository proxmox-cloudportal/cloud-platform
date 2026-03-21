import { useState } from 'react'

interface OSOption {
  id: string
  name: string
  icon: string
  description: string
}

const osOptions: OSOption[] = [
  { id: 'linux', name: 'Linux', icon: '🐧', description: 'Generic Linux distribution' },
  { id: 'ubuntu', name: 'Ubuntu', icon: '🟠', description: 'Ubuntu Server' },
  { id: 'debian', name: 'Debian', icon: '🔴', description: 'Debian GNU/Linux' },
  { id: 'centos', name: 'CentOS', icon: '💚', description: 'CentOS / Rocky / Alma' },
  { id: 'windows', name: 'Windows', icon: '🪟', description: 'Windows Server' },
  { id: 'other', name: 'Other', icon: '❓', description: 'Other operating system' },
]

interface OSSelectionSectionProps {
  selectedOS: string
  onSelect: (osId: string) => void
}

export default function OSSelectionSection({ selectedOS, onSelect }: OSSelectionSectionProps) {
  return (
    <div className="border-b border-gray-200 pb-6">
      <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
        Operating System
      </h3>
      <p className="text-sm text-gray-500 mb-4">
        Select the operating system you'll be installing on this virtual machine.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {osOptions.map((os) => (
          <button
            key={os.id}
            type="button"
            onClick={() => onSelect(os.id)}
            className={`
              relative flex flex-col items-center justify-center p-4 border-2 rounded-lg
              transition-all duration-200 hover:border-indigo-400 hover:shadow-md
              ${
                selectedOS === os.id
                  ? 'border-indigo-600 bg-indigo-50 ring-2 ring-indigo-600'
                  : 'border-gray-300 bg-white'
              }
            `}
          >
            <span className="text-4xl mb-2">{os.icon}</span>
            <span className="text-sm font-medium text-gray-900">{os.name}</span>
            {selectedOS === os.id && (
              <div className="absolute top-2 right-2">
                <svg
                  className="h-5 w-5 text-indigo-600"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
            )}
          </button>
        ))}
      </div>

      <div className="mt-3 text-sm text-gray-600">
        <span className="font-medium">Selected:</span>{' '}
        {osOptions.find((os) => os.id === selectedOS)?.description || 'None'}
      </div>
    </div>
  )
}
