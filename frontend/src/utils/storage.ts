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
  sidebarRightWidth: 320,
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
      // Validate each field to avoid persisting invalid types
      migrated.qaSettings = {
        quickMode: validBoolean(parsed.quickMode, DEFAULT_QA_SETTINGS.quickMode),
        temperature: validNumber(parsed.temperature, DEFAULT_QA_SETTINGS.temperature),
        timeoutMinutes: validNumber(parsed.timeoutMinutes, DEFAULT_QA_SETTINGS.timeoutMinutes),
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
        // Validate required fields before migrating
        if (
          typeof parsed.jobStartedAt === 'number' &&
          Number.isFinite(parsed.jobStartedAt) &&
          parsed.phases !== null &&
          typeof parsed.phases === 'object' &&
          !Array.isArray(parsed.phases)
        ) {
          migrated.generationTiming[jobId] = {
            jobId: parsed.jobId,
            jobStartedAt: parsed.jobStartedAt,
            phases: parsed.phases,
          }
        }
        // Invalid entries are silently dropped during migration
      } catch {
        // Invalid JSON, skip
      }
      localStorage.removeItem(key)
    }
  }

  return migrated
}

// =============================================================================
// Type Validation Helpers
// =============================================================================

/**
 * Validate and return a boolean value, falling back to default if invalid.
 */
function validBoolean(value: unknown, defaultValue: boolean): boolean {
  return typeof value === 'boolean' ? value : defaultValue
}

/**
 * Validate and return a number value, falling back to default if invalid.
 */
function validNumber(value: unknown, defaultValue: number): number {
  return typeof value === 'number' && !isNaN(value) ? value : defaultValue
}

/**
 * Validate and return a plain object for generationTiming.
 * Returns empty object if value is not a plain object.
 */
function validGenerationTiming(value: unknown): Record<string, GenerationTiming> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    return {}
  }
  return value as Record<string, GenerationTiming>
}

/**
 * Validate and normalize StoredJobStatus shape. Returns null if invalid.
 * Requires jobId and status as strings. Normalizes other fields to ensure
 * they have correct types (coercing missing/invalid to null).
 */
function validStoredJob(value: unknown): StoredJobStatus | null {
  if (
    typeof value !== 'object' ||
    value === null ||
    typeof (value as { jobId?: unknown }).jobId !== 'string' ||
    typeof (value as { status?: unknown }).status !== 'string'
  ) {
    return null
  }

  const raw = value as Partial<StoredJobStatus>
  return {
    jobId: raw.jobId as string,
    status: raw.status as string,
    // Ensure type is always a defined string
    type: typeof raw.type === 'string' ? raw.type : '',
    // Nullable string fields: coerce non-strings/missing to null
    startedAt: typeof raw.startedAt === 'string' ? raw.startedAt : null,
    completedAt: typeof raw.completedAt === 'string' ? raw.completedAt : null,
    currentPhase: typeof raw.currentPhase === 'string' ? raw.currentPhase : null,
    errorMessage: typeof raw.errorMessage === 'string' ? raw.errorMessage : null,
    // Nullable number field: coerce invalid/missing to null
    totalPhases:
      typeof raw.totalPhases === 'number' && Number.isFinite(raw.totalPhases)
        ? raw.totalPhases
        : null,
  }
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
        darkMode: validBoolean(converted.darkMode, DEFAULT_STORAGE.darkMode),
        askPanelOpen: validBoolean(converted.askPanelOpen, DEFAULT_STORAGE.askPanelOpen),
        sidebarLeftWidth: validNumber(converted.sidebarLeftWidth, DEFAULT_STORAGE.sidebarLeftWidth),
        sidebarRightWidth: validNumber(
          converted.sidebarRightWidth,
          DEFAULT_STORAGE.sidebarRightWidth
        ),
        currentJob: validStoredJob(converted.currentJob),
        qaSettings: {
          quickMode: validBoolean(
            converted.qaSettings?.quickMode,
            DEFAULT_STORAGE.qaSettings.quickMode
          ),
          temperature: validNumber(
            converted.qaSettings?.temperature,
            DEFAULT_STORAGE.qaSettings.temperature
          ),
          timeoutMinutes: validNumber(
            converted.qaSettings?.timeoutMinutes,
            DEFAULT_STORAGE.qaSettings.timeoutMinutes
          ),
        },
        generationTiming: validGenerationTiming(converted.generationTiming),
      }
    }

    // Try migrating old keys
    const migrated = migrateOldKeys()
    if (migrated) {
      // Only save the keys that were actually migrated, not defaults.
      // This preserves hasStorageValue() semantics - only explicitly set
      // values should be considered "stored".
      const toSave: Partial<OyaStorage> = {}
      if (migrated.darkMode !== undefined) {
        toSave.darkMode = validBoolean(migrated.darkMode, DEFAULT_STORAGE.darkMode)
      }
      if (migrated.askPanelOpen !== undefined) {
        toSave.askPanelOpen = validBoolean(migrated.askPanelOpen, DEFAULT_STORAGE.askPanelOpen)
      }
      if (migrated.sidebarLeftWidth !== undefined) {
        toSave.sidebarLeftWidth = validNumber(
          migrated.sidebarLeftWidth,
          DEFAULT_STORAGE.sidebarLeftWidth
        )
      }
      if (migrated.sidebarRightWidth !== undefined) {
        toSave.sidebarRightWidth = validNumber(
          migrated.sidebarRightWidth,
          DEFAULT_STORAGE.sidebarRightWidth
        )
      }
      if (migrated.currentJob !== undefined) {
        toSave.currentJob = validStoredJob(migrated.currentJob)
      }
      if (migrated.qaSettings !== undefined) {
        toSave.qaSettings = migrated.qaSettings
      }
      if (migrated.generationTiming !== undefined) {
        toSave.generationTiming = validGenerationTiming(migrated.generationTiming)
      }

      // Save only migrated keys to new storage
      try {
        const converted = convertKeysToSnake(toSave)
        localStorage.setItem(STORAGE_KEY, JSON.stringify(converted))
      } catch {
        // localStorage unavailable - continue with defaults
      }

      // Return full object with defaults for missing keys
      return {
        darkMode: toSave.darkMode ?? DEFAULT_STORAGE.darkMode,
        askPanelOpen: toSave.askPanelOpen ?? DEFAULT_STORAGE.askPanelOpen,
        sidebarLeftWidth: toSave.sidebarLeftWidth ?? DEFAULT_STORAGE.sidebarLeftWidth,
        sidebarRightWidth: toSave.sidebarRightWidth ?? DEFAULT_STORAGE.sidebarRightWidth,
        currentJob: toSave.currentJob ?? DEFAULT_STORAGE.currentJob,
        qaSettings: toSave.qaSettings ?? { ...DEFAULT_STORAGE.qaSettings },
        generationTiming: toSave.generationTiming ?? DEFAULT_STORAGE.generationTiming,
      }
    }

    return { ...DEFAULT_STORAGE }
  } catch {
    // Corrupted or unavailable - try to clear, then return defaults
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // localStorage unavailable (e.g., blocked storage, disabled cookies)
    }
    return { ...DEFAULT_STORAGE }
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
 * Uses sparse writes to avoid polluting storage with defaults.
 */
export function setStorageValue<K extends keyof OyaStorage>(key: K, value: OyaStorage[K]): void {
  try {
    // Read raw storage without merging defaults to preserve sparseness
    const stored = localStorage.getItem(STORAGE_KEY)
    let parsed = stored ? JSON.parse(stored) : {}

    // Normalize non-object values to {} (handles corrupted storage like 'true', 'null', '[]')
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      parsed = {}
    }

    // Update only the requested key (convert key and value to snake_case)
    const snakeKey = toSnakeCase(key)
    parsed[snakeKey] = convertKeysToSnake(value)

    localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed))
  } catch {
    // localStorage unavailable or quota exceeded - graceful degradation
  }
}

// =============================================================================
// Generation Timing Helpers
// =============================================================================

/**
 * Validate a GenerationTiming entry has required shape.
 * Returns null if invalid (missing jobStartedAt or phases is not an object).
 */
function validTimingEntry(timing: unknown): GenerationTiming | null {
  if (
    timing === null ||
    typeof timing !== 'object' ||
    typeof (timing as GenerationTiming).jobStartedAt !== 'number' ||
    !Number.isFinite((timing as GenerationTiming).jobStartedAt)
  ) {
    return null
  }
  const t = timing as GenerationTiming
  // Ensure phases is an object
  if (t.phases === null || typeof t.phases !== 'object' || Array.isArray(t.phases)) {
    return null
  }
  return t
}

/**
 * Get timing data for a specific job.
 * Returns null if not found or entry is corrupted.
 */
export function getTimingForJob(jobId: string): GenerationTiming | null {
  const timingData = getStorageValue('generationTiming')
  const entry = timingData[jobId]
  if (!entry) return null

  const validated = validTimingEntry(entry)
  if (!validated) {
    // Clear corrupted entry using sparse write
    const updated = { ...timingData }
    delete updated[jobId]
    setStorageValue('generationTiming', updated)
    return null
  }
  return validated
}

/**
 * Set timing data for a specific job.
 */
export function setTimingForJob(jobId: string, timing: GenerationTiming): void {
  const timingData = getStorageValue('generationTiming')
  setStorageValue('generationTiming', { ...timingData, [jobId]: timing })
}

/**
 * Clear timing data for a specific job.
 */
export function clearTimingForJob(jobId: string): void {
  const timingData = getStorageValue('generationTiming')
  const updated = { ...timingData }
  delete updated[jobId]
  setStorageValue('generationTiming', updated)
}

/**
 * Remove stale timing entries older than maxAge.
 * Default maxAge is 24 hours.
 * Also removes corrupted entries that lack valid jobStartedAt.
 */
export function cleanupStaleTiming(maxAgeMs: number = 24 * 60 * 60 * 1000): void {
  const timingData = getStorageValue('generationTiming')
  const now = Date.now()
  let changed = false

  // Validate generationTiming is an object (getStorageValue returns {} for invalid)
  const updated = { ...timingData }

  for (const [jobId, timing] of Object.entries(updated)) {
    // Validate timing entry has required shape
    if (
      timing === null ||
      typeof timing !== 'object' ||
      typeof timing.jobStartedAt !== 'number' ||
      !Number.isFinite(timing.jobStartedAt)
    ) {
      // Remove corrupted entry
      delete updated[jobId]
      changed = true
      continue
    }

    if (now - timing.jobStartedAt > maxAgeMs) {
      delete updated[jobId]
      changed = true
    }
  }

  if (changed) {
    setStorageValue('generationTiming', updated)
  }
}
