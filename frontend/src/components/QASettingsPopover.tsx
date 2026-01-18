import { useState, useRef, useEffect } from 'react'
import { QA_CONSTRAINTS, QA_DEFAULTS } from '../config/qa'

export interface QASettings {
  quickMode: boolean
  temperature: number
  timeoutMinutes: number
}

interface QASettingsPopoverProps {
  settings: QASettings
  onChange: (settings: QASettings) => void
}

export function QASettingsPopover({ settings, onChange }: QASettingsPopoverProps) {
  const [isOpen, setIsOpen] = useState(false)
  const popoverRef = useRef<HTMLDivElement>(null)

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  const temperatureLabel = settings.temperature <= 0.3 ? 'Precise' : settings.temperature <= 0.6 ? 'Balanced' : 'Creative'

  return (
    <div className="relative" ref={popoverRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
        aria-label="Answer settings"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>

      {isOpen && (
        <div className="absolute right-0 bottom-full mb-2 w-64 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 z-50">
          <div className="p-3 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
            <span className="font-medium text-gray-900 dark:text-white text-sm">Answer Settings</span>
            <button onClick={() => setIsOpen(false)} aria-label="Close settings" className="text-gray-400 hover:text-gray-600">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="p-3 space-y-4">
            {/* Mode Selection */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">Mode</label>
              <div className="space-y-1">
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    name="mode"
                    checked={settings.quickMode}
                    onChange={() => onChange({ ...settings, quickMode: true })}
                    className="mr-2"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Quick (~40s)</span>
                </label>
                <label className="flex items-center cursor-pointer">
                  <input
                    type="radio"
                    name="mode"
                    checked={!settings.quickMode}
                    onChange={() => onChange({ ...settings, quickMode: false })}
                    className="mr-2"
                    aria-label="Thorough mode"
                  />
                  <span className="text-sm text-gray-700 dark:text-gray-300">Thorough (~2min)</span>
                </label>
              </div>
            </div>

            {/* Temperature Slider */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Temperature <span className="text-gray-500">[{settings.temperature.toFixed(1)}]</span>
              </label>
              <input
                type="range"
                min={QA_CONSTRAINTS.temperature.min}
                max={QA_CONSTRAINTS.temperature.max}
                step={QA_CONSTRAINTS.temperature.step}
                value={settings.temperature}
                onChange={(e) => onChange({ ...settings, temperature: parseFloat(e.target.value) })}
                className="w-full"
                aria-label="Temperature"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>Precise</span>
                <span>{temperatureLabel}</span>
                <span>Creative</span>
              </div>
            </div>

            {/* Timeout Slider */}
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Timeout <span className="text-gray-500">[{settings.timeoutMinutes}min]</span>
              </label>
              <input
                type="range"
                min={QA_CONSTRAINTS.timeout.min}
                max={QA_CONSTRAINTS.timeout.max}
                step={QA_CONSTRAINTS.timeout.step}
                value={settings.timeoutMinutes}
                onChange={(e) => onChange({ ...settings, timeoutMinutes: parseInt(e.target.value) })}
                className="w-full"
                aria-label="Timeout"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>1min</span>
                <span>5min</span>
              </div>
            </div>

            {/* Reset Button */}
            <button
              onClick={() => onChange({ ...QA_DEFAULTS })}
              className="w-full text-xs text-blue-600 hover:text-blue-700 dark:text-blue-400"
            >
              Reset to defaults
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
