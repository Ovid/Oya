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

// Keys that could cause prototype pollution if assigned to a regular object
const DANGEROUS_KEYS = new Set(['__proto__', 'constructor', 'prototype'])

function convertKeysToSnake(obj: unknown): unknown {
  if (obj === null || typeof obj !== 'object') return obj
  if (Array.isArray(obj)) return obj.map(convertKeysToSnake)

  // Use Object.create(null) to prevent prototype pollution
  const result: Record<string, unknown> = Object.create(null)
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    if (DANGEROUS_KEYS.has(key)) continue // Skip dangerous keys
    result[toSnakeCase(key)] = convertKeysToSnake(value)
  }
  return result
}

function convertKeysToCamel(obj: unknown): unknown {
  if (obj === null || typeof obj !== 'object') return obj
  if (Array.isArray(obj)) return obj.map(convertKeysToCamel)

  // Use Object.create(null) to prevent prototype pollution
  const result: Record<string, unknown> = Object.create(null)
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    if (DANGEROUS_KEYS.has(key)) continue // Skip dangerous keys
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
          // Use parsed.jobId if valid string, otherwise fall back to key-derived jobId
          // Use the same value for both the map key and the jobId field for consistency
          const migratedJobId = typeof parsed.jobId === 'string' ? parsed.jobId : jobId
          migrated.generationTiming[migratedJobId] = {
            jobId: migratedJobId,
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
 * Only finite numbers are accepted (excludes NaN and ±Infinity).
 */
function validNumber(value: unknown, defaultValue: number): number {
  return Number.isFinite(value) ? (value as number) : defaultValue
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

    // If new key exists with valid content, use it (skip migration)
    // Use explicit null check - empty string is treated as corrupted
    if (stored !== null && stored !== '') {
      const parsed = JSON.parse(stored)

      // Validate parsed is a non-null plain object, not a primitive or array
      // (e.g., "true", "[]", "null", "123" are valid JSON but not valid storage)
      if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
        // Corrupted storage - remove and fall through to migration
        localStorage.removeItem(STORAGE_KEY)
      } else {
        const converted = convertKeysToCamel(parsed) as Partial<OyaStorage>

        return {
          darkMode: validBoolean(converted.darkMode, DEFAULT_STORAGE.darkMode),
          askPanelOpen: validBoolean(converted.askPanelOpen, DEFAULT_STORAGE.askPanelOpen),
          sidebarLeftWidth: validNumber(
            converted.sidebarLeftWidth,
            DEFAULT_STORAGE.sidebarLeftWidth
          ),
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
    }

    // Clear corrupted empty string before attempting migration
    if (stored === '') {
      localStorage.removeItem(STORAGE_KEY)
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
        // Only include if valid - don't store null for corrupted data (preserves sparse semantics)
        const validJob = validStoredJob(migrated.currentJob)
        if (validJob !== null) {
          toSave.currentJob = validJob
        }
      }
      if (migrated.qaSettings !== undefined) {
        toSave.qaSettings = migrated.qaSettings
      }
      if (migrated.generationTiming !== undefined) {
        // Only include if non-empty - don't store {} for empty/invalid data (preserves sparse semantics)
        const validTiming = validGenerationTiming(migrated.generationTiming)
        if (Object.keys(validTiming).length > 0) {
          toSave.generationTiming = validTiming
        }
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
    // Explicit null check - empty string treated as no storage
    if (stored === null || stored === '') return false
    const parsed = JSON.parse(stored)
    // Ensure parsed is a non-null plain object
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return false
    }
    const snakeKey = toSnakeCase(key)
    // Use hasOwnProperty to avoid prototype chain lookup
    return Object.prototype.hasOwnProperty.call(parsed, snakeKey)
  } catch {
    return false
  }
}

/**
 * Get a value only if it was explicitly stored, otherwise undefined.
 * Combines hasStorageValue + getStorageValue in a single parse.
 * Useful when you need to distinguish "not set" from "explicitly set to default".
 */
export function getExplicitStorageValue<K extends keyof OyaStorage>(
  key: K
): OyaStorage[K] | undefined {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    // Explicit null check - empty string treated as no storage
    if (stored === null || stored === '') return undefined
    const parsed = JSON.parse(stored)
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return undefined
    }
    const snakeKey = toSnakeCase(key)
    if (!Object.prototype.hasOwnProperty.call(parsed, snakeKey)) {
      return undefined
    }
    // Key exists - delegate to validated getter to ensure type safety
    // (e.g., handles stored "true" string being treated as boolean)
    return loadStorage()[key]
  } catch {
    return undefined
  }
}

/**
 * Set a specific value in storage, preserving other values.
 * Uses sparse writes to avoid polluting storage with defaults.
 */
export function setStorageValue<K extends keyof OyaStorage>(key: K, value: OyaStorage[K]): void {
  try {
    // Read raw storage without merging defaults to preserve sparseness
    // Explicit null/empty check - treat empty string as no storage
    const stored = localStorage.getItem(STORAGE_KEY)
    let parsed = stored !== null && stored !== '' ? JSON.parse(stored) : {}

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

/**
 * Remove a specific key from storage entirely.
 * Maintains sparse storage semantics - key will no longer exist.
 * Use this instead of setStorageValue(key, null) when you want to truly clear a value.
 */
export function clearStorageValue<K extends keyof OyaStorage>(key: K): void {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    // Explicit null/empty check - nothing to clear if no valid storage
    if (stored === null || stored === '') return

    const parsed = JSON.parse(stored)

    // Normalize non-object values to {} (handles corrupted storage)
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return // Nothing to clear
    }

    const snakeKey = toSnakeCase(key)
    if (Object.prototype.hasOwnProperty.call(parsed, snakeKey)) {
      delete parsed[snakeKey]
      localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed))
    }
  } catch {
    // localStorage unavailable - graceful degradation
  }
}

// =============================================================================
// Generation Timing Helpers
// =============================================================================

/**
 * Read raw timing data directly from storage without full object conversion.
 * Optimized for frequent timing updates during SSE progress.
 */
function getRawTimingData(): Record<string, GenerationTiming> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    // Explicit null/empty check
    if (stored === null || stored === '') return {}
    const parsed = JSON.parse(stored)
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    const rawTiming = parsed.generation_timing
    if (rawTiming === null || typeof rawTiming !== 'object' || Array.isArray(rawTiming)) return {}
    // Convert only timing entries from snake_case (shallow conversion for performance)
    // Use Object.create(null) and skip dangerous keys to prevent prototype pollution
    const result = Object.create(null) as Record<string, GenerationTiming>
    for (const [jobId, entry] of Object.entries(rawTiming)) {
      if (DANGEROUS_KEYS.has(jobId)) continue
      if (entry && typeof entry === 'object') {
        const e = entry as Record<string, unknown>
        result[jobId] = {
          // Use map key as authoritative jobId (handles corrupted/inconsistent data)
          jobId,
          jobStartedAt: e.job_started_at as number,
          phases: convertKeysToCamel(e.phases) as Record<string, PhaseTiming>,
        }
      }
    }
    return result
  } catch {
    return {}
  }
}

/**
 * Write timing data directly to storage without full object conversion.
 * Optimized for frequent timing updates during SSE progress.
 * Maintains sparse storage: deletes generation_timing key when empty.
 */
function setRawTimingData(timingData: Record<string, GenerationTiming>): void {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    // Explicit null/empty check - treat empty string as no storage
    let parsed = stored !== null && stored !== '' ? JSON.parse(stored) : {}
    if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
      parsed = {}
    }

    const entries = Object.entries(timingData)
    if (entries.length === 0) {
      // Delete key entirely for sparse storage semantics
      delete parsed.generation_timing
    } else {
      // Convert timing entries to snake_case
      // Use Object.create(null) and skip dangerous keys to prevent prototype pollution
      const snakeTiming = Object.create(null) as Record<string, unknown>
      for (const [jobId, entry] of entries) {
        if (DANGEROUS_KEYS.has(jobId)) continue
        snakeTiming[jobId] = {
          // Use map key as canonical job_id (matches getRawTimingData read behavior)
          job_id: jobId,
          job_started_at: entry.jobStartedAt,
          phases: convertKeysToSnake(entry.phases),
        }
      }
      parsed.generation_timing = snakeTiming
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(parsed))
  } catch {
    // localStorage unavailable - graceful degradation
  }
}

/**
 * Validate a GenerationTiming entry has required shape.
 * Returns null if invalid (missing/invalid jobId, jobStartedAt, or phases).
 */
function validTimingEntry(timing: unknown): GenerationTiming | null {
  if (timing === null || typeof timing !== 'object') {
    return null
  }
  const t = timing as GenerationTiming
  // Validate jobId is a string
  if (typeof t.jobId !== 'string') {
    return null
  }
  // Validate jobStartedAt is a finite number
  if (typeof t.jobStartedAt !== 'number' || !Number.isFinite(t.jobStartedAt)) {
    return null
  }
  // Validate phases is a plain object
  if (t.phases === null || typeof t.phases !== 'object' || Array.isArray(t.phases)) {
    return null
  }
  return t
}

/**
 * Get timing data for a specific job.
 * Returns null if not found or entry is corrupted.
 * Uses optimized direct storage access for performance.
 */
export function getTimingForJob(jobId: string): GenerationTiming | null {
  const timingData = getRawTimingData()
  const entry = timingData[jobId]
  if (!entry) return null

  const validated = validTimingEntry(entry)
  if (!validated) {
    // Clear corrupted entry
    const updated = { ...timingData }
    delete updated[jobId]
    setRawTimingData(updated)
    return null
  }
  return validated
}

/**
 * Set timing data for a specific job.
 * Uses optimized direct storage access for performance during SSE updates.
 * Normalizes timing.jobId to match the jobId parameter for consistency.
 */
export function setTimingForJob(jobId: string, timing: GenerationTiming): void {
  const timingData = getRawTimingData()
  // Normalize timing.jobId to match the map key for consistency
  const normalizedTiming = { ...timing, jobId }
  setRawTimingData({ ...timingData, [jobId]: normalizedTiming })
}

/**
 * Clear timing data for a specific job.
 */
export function clearTimingForJob(jobId: string): void {
  const timingData = getRawTimingData()
  const updated = { ...timingData }
  delete updated[jobId]
  setRawTimingData(updated)
}

/**
 * Remove stale timing entries older than maxAge.
 * Default maxAge is 24 hours.
 * Also removes corrupted entries that lack valid jobStartedAt.
 */
export function cleanupStaleTiming(maxAgeMs: number = 24 * 60 * 60 * 1000): void {
  const timingData = getRawTimingData()
  const now = Date.now()
  let changed = false

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
    setRawTimingData(updated)
  }
}
