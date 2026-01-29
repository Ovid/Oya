// frontend/src/utils/storage.ts

/**
 * Consolidated localStorage module.
 *
 * All Oya data is stored under a single 'oya' key with snake_case property names.
 * Runtime types use camelCase; conversion happens at the storage boundary.
 */

const STORAGE_KEY = 'oya'

// =============================================================================
// Types (runtime uses camelCase)
// =============================================================================

export interface StoredJobStatus {
  jobId: string
  type: string
  status: string
  startedAt: string | null
  completedAt: string | null
  currentPhase: string | null
  totalPhases: number | null
  errorMessage: string | null
}

export interface QASettings {
  quickMode: boolean
  temperature: number
  timeoutMinutes: number
}

export interface PhaseTiming {
  startedAt: number
  completedAt?: number
  duration?: number
}

export interface GenerationTiming {
  jobId: string
  jobStartedAt: number
  phases: Record<string, PhaseTiming>
}

export interface OyaStorage {
  darkMode: boolean
  askPanelOpen: boolean
  sidebarLeftWidth: number
  sidebarRightWidth: number
  currentJob: StoredJobStatus | null
  qaSettings: QASettings
  generationTiming: Record<string, GenerationTiming>
}

// =============================================================================
// Defaults
// =============================================================================

export const DEFAULT_QA_SETTINGS: QASettings = {
  quickMode: true,
  temperature: 0.5,
  timeoutMinutes: 3,
}

export const DEFAULT_STORAGE: OyaStorage = {
  darkMode: false,
  askPanelOpen: false,
  sidebarLeftWidth: 256,
  sidebarRightWidth: 200,
  currentJob: null,
  qaSettings: { ...DEFAULT_QA_SETTINGS },
  generationTiming: {},
}

// =============================================================================
// Snake Case Conversion
// =============================================================================

function toSnakeCase(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

function toCamelCase(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

function convertKeysToSnake(obj: unknown): unknown {
  if (obj === null || typeof obj !== 'object') return obj
  if (Array.isArray(obj)) return obj.map(convertKeysToSnake)

  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    result[toSnakeCase(key)] = convertKeysToSnake(value)
  }
  return result
}

function convertKeysToCamel(obj: unknown): unknown {
  if (obj === null || typeof obj !== 'object') return obj
  if (Array.isArray(obj)) return obj.map(convertKeysToCamel)

  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    result[toCamelCase(key)] = convertKeysToCamel(value)
  }
  return result
}

// =============================================================================
// Core Storage Functions
// =============================================================================

/**
 * Load storage from localStorage.
 * Returns defaults merged with stored values.
 * Clears corrupted data.
 */
export function loadStorage(): OyaStorage {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return { ...DEFAULT_STORAGE }

    const parsed = JSON.parse(stored)
    const converted = convertKeysToCamel(parsed) as Partial<OyaStorage>

    // Merge with defaults to handle missing keys
    return {
      darkMode: converted.darkMode ?? DEFAULT_STORAGE.darkMode,
      askPanelOpen: converted.askPanelOpen ?? DEFAULT_STORAGE.askPanelOpen,
      sidebarLeftWidth: converted.sidebarLeftWidth ?? DEFAULT_STORAGE.sidebarLeftWidth,
      sidebarRightWidth: converted.sidebarRightWidth ?? DEFAULT_STORAGE.sidebarRightWidth,
      currentJob: converted.currentJob ?? DEFAULT_STORAGE.currentJob,
      qaSettings: {
        quickMode: converted.qaSettings?.quickMode ?? DEFAULT_STORAGE.qaSettings.quickMode,
        temperature: converted.qaSettings?.temperature ?? DEFAULT_STORAGE.qaSettings.temperature,
        timeoutMinutes: converted.qaSettings?.timeoutMinutes ?? DEFAULT_STORAGE.qaSettings.timeoutMinutes,
      },
      generationTiming: converted.generationTiming ?? DEFAULT_STORAGE.generationTiming,
    }
  } catch {
    // Corrupted - clear and return defaults
    localStorage.removeItem(STORAGE_KEY)
    return { ...DEFAULT_STORAGE }
  }
}

/**
 * Save full storage object to localStorage.
 */
export function saveStorage(storage: OyaStorage): void {
  try {
    const converted = convertKeysToSnake(storage)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(converted))
  } catch {
    // localStorage unavailable or quota exceeded - graceful degradation
  }
}

/**
 * Get a specific value from storage.
 */
export function getStorageValue<K extends keyof OyaStorage>(key: K): OyaStorage[K] {
  return loadStorage()[key]
}

/**
 * Set a specific value in storage, preserving other values.
 */
export function setStorageValue<K extends keyof OyaStorage>(key: K, value: OyaStorage[K]): void {
  const storage = loadStorage()
  storage[key] = value
  saveStorage(storage)
}
