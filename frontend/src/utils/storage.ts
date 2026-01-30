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
// Migration from Old Keys
// =============================================================================

const OLD_KEYS = {
  darkMode: 'oya-dark-mode',
  askPanelOpen: 'oya-ask-panel-open',
  sidebarLeftWidth: 'oya-sidebar-left-width',
  sidebarRightWidth: 'oya-sidebar-right-width',
  currentJob: 'oya-current-job',
  qaSettings: 'oya-qa-settings',
  generationTimingPrefix: 'oya-generation-timing-',
} as const

function migrateOldKeys(): Partial<OyaStorage> | null {
  // Check if any old keys exist
  const hasOldKeys = Object.values(OLD_KEYS).some((key) =>
    key.endsWith('-')
      ? Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i)).some((k) =>
          k?.startsWith(key)
        )
      : localStorage.getItem(key) !== null
  )

  if (!hasOldKeys) return null

  const migrated: Partial<OyaStorage> = {}

  // Migrate simple boolean/number keys
  const darkModeStr = localStorage.getItem(OLD_KEYS.darkMode)
  if (darkModeStr !== null) {
    migrated.darkMode = darkModeStr === 'true'
    localStorage.removeItem(OLD_KEYS.darkMode)
  }

  const askPanelStr = localStorage.getItem(OLD_KEYS.askPanelOpen)
  if (askPanelStr !== null) {
    migrated.askPanelOpen = askPanelStr === 'true'
    localStorage.removeItem(OLD_KEYS.askPanelOpen)
  }

  const leftWidthStr = localStorage.getItem(OLD_KEYS.sidebarLeftWidth)
  if (leftWidthStr !== null) {
    const parsed = parseInt(leftWidthStr, 10)
    if (!isNaN(parsed)) migrated.sidebarLeftWidth = parsed
    localStorage.removeItem(OLD_KEYS.sidebarLeftWidth)
  }

  const rightWidthStr = localStorage.getItem(OLD_KEYS.sidebarRightWidth)
  if (rightWidthStr !== null) {
    const parsed = parseInt(rightWidthStr, 10)
    if (!isNaN(parsed)) migrated.sidebarRightWidth = parsed
    localStorage.removeItem(OLD_KEYS.sidebarRightWidth)
  }

  // Migrate JSON keys
  const currentJobStr = localStorage.getItem(OLD_KEYS.currentJob)
  if (currentJobStr !== null) {
    try {
      const parsed = JSON.parse(currentJobStr)
      // Old format uses snake_case, convert to camelCase
      migrated.currentJob = {
        jobId: parsed.job_id,
        type: parsed.type,
        status: parsed.status,
        startedAt: parsed.started_at,
        completedAt: parsed.completed_at,
        currentPhase: parsed.current_phase,
        totalPhases: parsed.total_phases,
        errorMessage: parsed.error_message,
      }
    } catch {
      // Invalid JSON, skip
    }
    localStorage.removeItem(OLD_KEYS.currentJob)
  }

  const qaSettingsStr = localStorage.getItem(OLD_KEYS.qaSettings)
  if (qaSettingsStr !== null) {
    try {
      const parsed = JSON.parse(qaSettingsStr)
      migrated.qaSettings = {
        quickMode: parsed.quickMode ?? DEFAULT_QA_SETTINGS.quickMode,
        temperature: parsed.temperature ?? DEFAULT_QA_SETTINGS.temperature,
        timeoutMinutes: parsed.timeoutMinutes ?? DEFAULT_QA_SETTINGS.timeoutMinutes,
      }
    } catch {
      // Invalid JSON, skip
    }
    localStorage.removeItem(OLD_KEYS.qaSettings)
  }

  // Migrate timing keys (dynamic)
  const timingKeys: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key?.startsWith(OLD_KEYS.generationTimingPrefix)) {
      timingKeys.push(key)
    }
  }

  if (timingKeys.length > 0) {
    migrated.generationTiming = {}
    for (const key of timingKeys) {
      const jobId = key.slice(OLD_KEYS.generationTimingPrefix.length)
      try {
        const parsed = JSON.parse(localStorage.getItem(key)!)
        migrated.generationTiming[jobId] = {
          jobId: parsed.jobId,
          jobStartedAt: parsed.jobStartedAt,
          phases: parsed.phases,
        }
      } catch {
        // Invalid JSON, skip
      }
      localStorage.removeItem(key)
    }
  }

  return migrated
}

// =============================================================================
// Core Storage Functions
// =============================================================================

/**
 * Load storage from localStorage.
 * Returns defaults merged with stored values.
 * Clears corrupted data.
 * Migrates from old keys if new key doesn't exist.
 */
export function loadStorage(): OyaStorage {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)

    // If new key exists, use it (skip migration)
    if (stored) {
      const parsed = JSON.parse(stored)
      const converted = convertKeysToCamel(parsed) as Partial<OyaStorage>

      return {
        darkMode: converted.darkMode ?? DEFAULT_STORAGE.darkMode,
        askPanelOpen: converted.askPanelOpen ?? DEFAULT_STORAGE.askPanelOpen,
        sidebarLeftWidth: converted.sidebarLeftWidth ?? DEFAULT_STORAGE.sidebarLeftWidth,
        sidebarRightWidth: converted.sidebarRightWidth ?? DEFAULT_STORAGE.sidebarRightWidth,
        currentJob: converted.currentJob ?? DEFAULT_STORAGE.currentJob,
        qaSettings: {
          quickMode: converted.qaSettings?.quickMode ?? DEFAULT_STORAGE.qaSettings.quickMode,
          temperature: converted.qaSettings?.temperature ?? DEFAULT_STORAGE.qaSettings.temperature,
          timeoutMinutes:
            converted.qaSettings?.timeoutMinutes ?? DEFAULT_STORAGE.qaSettings.timeoutMinutes,
        },
        generationTiming: converted.generationTiming ?? DEFAULT_STORAGE.generationTiming,
      }
    }

    // Try migrating old keys
    const migrated = migrateOldKeys()
    if (migrated) {
      const storage: OyaStorage = {
        darkMode: migrated.darkMode ?? DEFAULT_STORAGE.darkMode,
        askPanelOpen: migrated.askPanelOpen ?? DEFAULT_STORAGE.askPanelOpen,
        sidebarLeftWidth: migrated.sidebarLeftWidth ?? DEFAULT_STORAGE.sidebarLeftWidth,
        sidebarRightWidth: migrated.sidebarRightWidth ?? DEFAULT_STORAGE.sidebarRightWidth,
        currentJob: migrated.currentJob ?? DEFAULT_STORAGE.currentJob,
        qaSettings: migrated.qaSettings ?? { ...DEFAULT_STORAGE.qaSettings },
        generationTiming: migrated.generationTiming ?? DEFAULT_STORAGE.generationTiming,
      }
      // Save migrated data to new key
      saveStorage(storage)
      return storage
    }

    return { ...DEFAULT_STORAGE }
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
 * Check if a specific key has been explicitly stored (vs using default).
 * Useful for distinguishing "no preference set" from "explicitly set to default value".
 */
export function hasStorageValue<K extends keyof OyaStorage>(key: K): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return false
    const parsed = JSON.parse(stored)
    const snakeKey = toSnakeCase(key)
    return snakeKey in parsed
  } catch {
    return false
  }
}

/**
 * Set a specific value in storage, preserving other values.
 */
export function setStorageValue<K extends keyof OyaStorage>(key: K, value: OyaStorage[K]): void {
  const storage = loadStorage()
  storage[key] = value
  saveStorage(storage)
}

// =============================================================================
// Generation Timing Helpers
// =============================================================================

/**
 * Get timing data for a specific job.
 */
export function getTimingForJob(jobId: string): GenerationTiming | null {
  const storage = loadStorage()
  return storage.generationTiming[jobId] ?? null
}

/**
 * Set timing data for a specific job.
 */
export function setTimingForJob(jobId: string, timing: GenerationTiming): void {
  const storage = loadStorage()
  storage.generationTiming[jobId] = timing
  saveStorage(storage)
}

/**
 * Clear timing data for a specific job.
 */
export function clearTimingForJob(jobId: string): void {
  const storage = loadStorage()
  delete storage.generationTiming[jobId]
  saveStorage(storage)
}

/**
 * Remove stale timing entries older than maxAge.
 * Default maxAge is 24 hours.
 */
export function cleanupStaleTiming(maxAgeMs: number = 24 * 60 * 60 * 1000): void {
  const storage = loadStorage()
  const now = Date.now()
  let changed = false

  for (const [jobId, timing] of Object.entries(storage.generationTiming)) {
    if (now - timing.jobStartedAt > maxAgeMs) {
      delete storage.generationTiming[jobId]
      changed = true
    }
  }

  if (changed) {
    saveStorage(storage)
  }
}
