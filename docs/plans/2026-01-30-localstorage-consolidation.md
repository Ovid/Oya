# localStorage Consolidation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate all Oya localStorage keys into a single `oya` key with snake_case property names.

**Architecture:** Create a centralized storage module that handles all localStorage access, converting between snake_case (storage) and camelCase (runtime). Migration from old keys happens transparently on first load.

**Tech Stack:** TypeScript, Vitest, React hooks, Zustand stores

---

## Task 1: Create Storage Module Types and Core Functions

**Files:**
- Create: `frontend/src/utils/storage.ts`
- Create: `frontend/src/utils/storage.test.ts`

**Step 1: Write failing tests for storage types and load/save**

```typescript
// frontend/src/utils/storage.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { loadStorage, saveStorage, getStorageValue, setStorageValue, DEFAULT_STORAGE } from './storage'

describe('storage module', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  describe('loadStorage', () => {
    it('returns default values when no storage exists', () => {
      const storage = loadStorage()
      expect(storage).toEqual(DEFAULT_STORAGE)
    })

    it('loads existing storage with snake_case keys', () => {
      localStorage.setItem('oya', JSON.stringify({
        dark_mode: true,
        ask_panel_open: true,
        sidebar_left_width: 300,
        sidebar_right_width: 250,
        current_job: null,
        qa_settings: { quick_mode: false, temperature: 0.7, timeout_minutes: 5 },
        generation_timing: {}
      }))

      const storage = loadStorage()
      expect(storage.darkMode).toBe(true)
      expect(storage.askPanelOpen).toBe(true)
      expect(storage.sidebarLeftWidth).toBe(300)
      expect(storage.qaSettings.quickMode).toBe(false)
    })

    it('handles corrupted JSON gracefully', () => {
      localStorage.setItem('oya', 'not valid json {')
      const storage = loadStorage()
      expect(storage).toEqual(DEFAULT_STORAGE)
      expect(localStorage.getItem('oya')).toBeNull()
    })

    it('merges partial storage with defaults', () => {
      localStorage.setItem('oya', JSON.stringify({
        dark_mode: true
      }))
      const storage = loadStorage()
      expect(storage.darkMode).toBe(true)
      expect(storage.askPanelOpen).toBe(false) // default
      expect(storage.sidebarLeftWidth).toBe(256) // default
    })
  })

  describe('saveStorage', () => {
    it('saves storage with snake_case keys', () => {
      saveStorage({
        darkMode: true,
        askPanelOpen: false,
        sidebarLeftWidth: 300,
        sidebarRightWidth: 200,
        currentJob: null,
        qaSettings: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
        generationTiming: {}
      })

      const stored = JSON.parse(localStorage.getItem('oya')!)
      expect(stored.dark_mode).toBe(true)
      expect(stored.sidebar_left_width).toBe(300)
      expect(stored.qa_settings.quick_mode).toBe(true)
    })
  })

  describe('getStorageValue', () => {
    it('returns specific value from storage', () => {
      localStorage.setItem('oya', JSON.stringify({ dark_mode: true }))
      expect(getStorageValue('darkMode')).toBe(true)
    })

    it('returns default when key missing', () => {
      expect(getStorageValue('darkMode')).toBe(false)
    })
  })

  describe('setStorageValue', () => {
    it('updates specific value in storage', () => {
      setStorageValue('darkMode', true)
      const stored = JSON.parse(localStorage.getItem('oya')!)
      expect(stored.dark_mode).toBe(true)
    })

    it('preserves other values', () => {
      localStorage.setItem('oya', JSON.stringify({
        dark_mode: false,
        sidebar_left_width: 300
      }))
      setStorageValue('darkMode', true)
      const stored = JSON.parse(localStorage.getItem('oya')!)
      expect(stored.dark_mode).toBe(true)
      expect(stored.sidebar_left_width).toBe(300)
    })
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- src/utils/storage.test.ts`
Expected: FAIL - module not found

**Step 3: Implement storage module core**

```typescript
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
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- src/utils/storage.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/utils/storage.ts frontend/src/utils/storage.test.ts
git commit -m "feat: add consolidated storage module with core functions"
```

---

## Task 2: Add Migration from Old Keys

**Files:**
- Modify: `frontend/src/utils/storage.ts`
- Modify: `frontend/src/utils/storage.test.ts`

**Step 1: Write failing tests for migration**

Add to `frontend/src/utils/storage.test.ts`:

```typescript
describe('migration from old keys', () => {
  it('migrates oya-dark-mode', () => {
    localStorage.setItem('oya-dark-mode', 'true')
    const storage = loadStorage()
    expect(storage.darkMode).toBe(true)
    expect(localStorage.getItem('oya-dark-mode')).toBeNull()
  })

  it('migrates oya-ask-panel-open', () => {
    localStorage.setItem('oya-ask-panel-open', 'true')
    const storage = loadStorage()
    expect(storage.askPanelOpen).toBe(true)
    expect(localStorage.getItem('oya-ask-panel-open')).toBeNull()
  })

  it('migrates oya-sidebar-left-width', () => {
    localStorage.setItem('oya-sidebar-left-width', '350')
    const storage = loadStorage()
    expect(storage.sidebarLeftWidth).toBe(350)
    expect(localStorage.getItem('oya-sidebar-left-width')).toBeNull()
  })

  it('migrates oya-sidebar-right-width', () => {
    localStorage.setItem('oya-sidebar-right-width', '280')
    const storage = loadStorage()
    expect(storage.sidebarRightWidth).toBe(280)
    expect(localStorage.getItem('oya-sidebar-right-width')).toBeNull()
  })

  it('migrates oya-current-job', () => {
    const job = {
      job_id: 'test-123',
      type: 'full',
      status: 'running',
      started_at: '2026-01-30T10:00:00',
      completed_at: null,
      current_phase: 'files',
      total_phases: 8,
      error_message: null
    }
    localStorage.setItem('oya-current-job', JSON.stringify(job))
    const storage = loadStorage()
    expect(storage.currentJob?.jobId).toBe('test-123')
    expect(storage.currentJob?.status).toBe('running')
    expect(localStorage.getItem('oya-current-job')).toBeNull()
  })

  it('migrates oya-qa-settings', () => {
    const settings = { quickMode: false, temperature: 0.8, timeoutMinutes: 7 }
    localStorage.setItem('oya-qa-settings', JSON.stringify(settings))
    const storage = loadStorage()
    expect(storage.qaSettings.quickMode).toBe(false)
    expect(storage.qaSettings.temperature).toBe(0.8)
    expect(localStorage.getItem('oya-qa-settings')).toBeNull()
  })

  it('migrates oya-generation-timing-* keys', () => {
    const timing = {
      jobId: 'job-abc',
      jobStartedAt: 1700000000000,
      phases: { files: { startedAt: 1700000001000 } }
    }
    localStorage.setItem('oya-generation-timing-job-abc', JSON.stringify(timing))
    const storage = loadStorage()
    expect(storage.generationTiming['job-abc']).toBeDefined()
    expect(storage.generationTiming['job-abc'].jobId).toBe('job-abc')
    expect(localStorage.getItem('oya-generation-timing-job-abc')).toBeNull()
  })

  it('migrates all old keys together', () => {
    localStorage.setItem('oya-dark-mode', 'true')
    localStorage.setItem('oya-sidebar-left-width', '300')
    localStorage.setItem('oya-qa-settings', JSON.stringify({ quickMode: false, temperature: 0.6, timeoutMinutes: 4 }))

    const storage = loadStorage()

    expect(storage.darkMode).toBe(true)
    expect(storage.sidebarLeftWidth).toBe(300)
    expect(storage.qaSettings.quickMode).toBe(false)
    expect(localStorage.getItem('oya-dark-mode')).toBeNull()
    expect(localStorage.getItem('oya-sidebar-left-width')).toBeNull()
    expect(localStorage.getItem('oya-qa-settings')).toBeNull()
  })

  it('new storage takes precedence over old keys', () => {
    localStorage.setItem('oya', JSON.stringify({ dark_mode: false }))
    localStorage.setItem('oya-dark-mode', 'true')
    const storage = loadStorage()
    expect(storage.darkMode).toBe(false) // new key wins
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- src/utils/storage.test.ts`
Expected: FAIL - migration not implemented

**Step 3: Implement migration**

Add to `frontend/src/utils/storage.ts` before `loadStorage`:

```typescript
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
      ? Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i))
          .some((k) => k?.startsWith(key))
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
```

Update `loadStorage` to call migration:

```typescript
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
          timeoutMinutes: converted.qaSettings?.timeoutMinutes ?? DEFAULT_STORAGE.qaSettings.timeoutMinutes,
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
    localStorage.removeItem(STORAGE_KEY)
    return { ...DEFAULT_STORAGE }
  }
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- src/utils/storage.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/utils/storage.ts frontend/src/utils/storage.test.ts
git commit -m "feat: add migration from old localStorage keys"
```

---

## Task 3: Add Generation Timing Helper Functions

**Files:**
- Modify: `frontend/src/utils/storage.ts`
- Modify: `frontend/src/utils/storage.test.ts`

**Step 1: Write failing tests for timing helpers**

Add to `frontend/src/utils/storage.test.ts`:

```typescript
import {
  loadStorage,
  saveStorage,
  getStorageValue,
  setStorageValue,
  DEFAULT_STORAGE,
  getTimingForJob,
  setTimingForJob,
  clearTimingForJob,
  cleanupStaleTiming,
} from './storage'

// ... existing tests ...

describe('generation timing helpers', () => {
  describe('getTimingForJob', () => {
    it('returns timing for existing job', () => {
      const timing = { jobId: 'job-1', jobStartedAt: 1000, phases: {} }
      localStorage.setItem('oya', JSON.stringify({
        generation_timing: { 'job-1': { job_id: 'job-1', job_started_at: 1000, phases: {} } }
      }))
      expect(getTimingForJob('job-1')).toEqual(timing)
    })

    it('returns null for non-existent job', () => {
      expect(getTimingForJob('no-such-job')).toBeNull()
    })
  })

  describe('setTimingForJob', () => {
    it('adds timing for new job', () => {
      const timing = { jobId: 'job-2', jobStartedAt: 2000, phases: { files: { startedAt: 2001 } } }
      setTimingForJob('job-2', timing)
      expect(getTimingForJob('job-2')).toEqual(timing)
    })

    it('updates timing for existing job', () => {
      setTimingForJob('job-3', { jobId: 'job-3', jobStartedAt: 3000, phases: {} })
      setTimingForJob('job-3', { jobId: 'job-3', jobStartedAt: 3000, phases: { files: { startedAt: 3001, completedAt: 3005, duration: 4 } } })
      expect(getTimingForJob('job-3')?.phases.files?.completedAt).toBe(3005)
    })
  })

  describe('clearTimingForJob', () => {
    it('removes timing for job', () => {
      setTimingForJob('job-4', { jobId: 'job-4', jobStartedAt: 4000, phases: {} })
      clearTimingForJob('job-4')
      expect(getTimingForJob('job-4')).toBeNull()
    })

    it('does not throw for non-existent job', () => {
      expect(() => clearTimingForJob('no-job')).not.toThrow()
    })
  })

  describe('cleanupStaleTiming', () => {
    it('removes entries older than maxAge', () => {
      const now = Date.now()
      // Old entry (25 hours ago)
      setTimingForJob('old-job', { jobId: 'old-job', jobStartedAt: now - 25 * 60 * 60 * 1000, phases: {} })
      // Recent entry (1 hour ago)
      setTimingForJob('new-job', { jobId: 'new-job', jobStartedAt: now - 1 * 60 * 60 * 1000, phases: {} })

      cleanupStaleTiming(24 * 60 * 60 * 1000)

      expect(getTimingForJob('old-job')).toBeNull()
      expect(getTimingForJob('new-job')).not.toBeNull()
    })
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- src/utils/storage.test.ts`
Expected: FAIL - functions not exported

**Step 3: Implement timing helpers**

Add to `frontend/src/utils/storage.ts`:

```typescript
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
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- src/utils/storage.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/utils/storage.ts frontend/src/utils/storage.test.ts
git commit -m "feat: add generation timing helper functions"
```

---

## Task 4: Update uiStore to Use New Storage

**Files:**
- Modify: `frontend/src/stores/uiStore.ts`
- Modify: `frontend/src/stores/uiStore.test.ts`

**Step 1: Update uiStore tests for new storage module**

Replace `frontend/src/stores/uiStore.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useUIStore, initialState } from './uiStore'
import * as storage from '../utils/storage'

vi.mock('../utils/storage', () => ({
  getStorageValue: vi.fn(),
  setStorageValue: vi.fn(),
  DEFAULT_STORAGE: {
    darkMode: false,
    askPanelOpen: false,
    sidebarLeftWidth: 256,
    sidebarRightWidth: 200,
    currentJob: null,
    qaSettings: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
    generationTiming: {},
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
  useUIStore.setState(initialState)
})

describe('uiStore', () => {
  describe('toggleDarkMode', () => {
    it('toggles dark mode from false to true', () => {
      useUIStore.setState({ darkMode: false })
      useUIStore.getState().toggleDarkMode()
      expect(useUIStore.getState().darkMode).toBe(true)
    })

    it('toggles dark mode from true to false', () => {
      useUIStore.setState({ darkMode: true })
      useUIStore.getState().toggleDarkMode()
      expect(useUIStore.getState().darkMode).toBe(false)
    })

    it('persists to storage', () => {
      useUIStore.setState({ darkMode: false })
      useUIStore.getState().toggleDarkMode()
      expect(storage.setStorageValue).toHaveBeenCalledWith('darkMode', true)
    })
  })

  describe('setAskPanelOpen', () => {
    it('sets ask panel open state', () => {
      useUIStore.getState().setAskPanelOpen(true)
      expect(useUIStore.getState().askPanelOpen).toBe(true)
    })

    it('persists to storage', () => {
      useUIStore.getState().setAskPanelOpen(true)
      expect(storage.setStorageValue).toHaveBeenCalledWith('askPanelOpen', true)
    })
  })

  describe('toast notifications', () => {
    it('adds a toast with unique id', () => {
      useUIStore.getState().addToast('Test message', 'error')
      const toasts = useUIStore.getState().toasts
      expect(toasts).toHaveLength(1)
      expect(toasts[0].message).toBe('Test message')
      expect(toasts[0].type).toBe('error')
      expect(toasts[0].id).toBeDefined()
    })

    it('adds multiple toasts', () => {
      useUIStore.getState().addToast('First', 'error')
      useUIStore.getState().addToast('Second', 'warning')
      expect(useUIStore.getState().toasts).toHaveLength(2)
    })

    it('dismisses a toast by id', () => {
      useUIStore.getState().addToast('Test', 'info')
      const toastId = useUIStore.getState().toasts[0].id
      useUIStore.getState().dismissToast(toastId)
      expect(useUIStore.getState().toasts).toHaveLength(0)
    })

    it('only dismisses the specified toast', () => {
      useUIStore.getState().addToast('First', 'error')
      useUIStore.getState().addToast('Second', 'warning')
      const firstId = useUIStore.getState().toasts[0].id
      useUIStore.getState().dismissToast(firstId)
      const remaining = useUIStore.getState().toasts
      expect(remaining).toHaveLength(1)
      expect(remaining[0].message).toBe('Second')
    })
  })

  describe('error modal', () => {
    it('shows error modal', () => {
      useUIStore.getState().showErrorModal('Error Title', 'Error details')
      const modal = useUIStore.getState().errorModal
      expect(modal).not.toBeNull()
      expect(modal?.title).toBe('Error Title')
      expect(modal?.message).toBe('Error details')
    })

    it('dismisses error modal', () => {
      useUIStore.getState().showErrorModal('Title', 'Message')
      useUIStore.getState().dismissErrorModal()
      expect(useUIStore.getState().errorModal).toBeNull()
    })
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- src/stores/uiStore.test.ts`
Expected: FAIL - uiStore still uses old imports

**Step 3: Update uiStore implementation**

Replace `frontend/src/stores/uiStore.ts`:

```typescript
import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'
import { getStorageValue, setStorageValue, DEFAULT_STORAGE } from '../utils/storage'
import type { Toast, ToastType, ErrorModalState } from '../types'

function getInitialDarkMode(): boolean {
  if (typeof window === 'undefined') return false
  const stored = getStorageValue('darkMode')
  if (stored !== DEFAULT_STORAGE.darkMode) return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function getInitialAskPanelOpen(): boolean {
  if (typeof window === 'undefined') return false
  return getStorageValue('askPanelOpen')
}

let toastIdCounter = 0

interface UIState {
  darkMode: boolean
  askPanelOpen: boolean
  toasts: Toast[]
  errorModal: ErrorModalState | null
}

interface UIActions {
  toggleDarkMode: () => void
  setAskPanelOpen: (open: boolean) => void
  addToast: (message: string, type: ToastType) => string
  dismissToast: (id: string) => void
  showErrorModal: (title: string, message: string) => void
  dismissErrorModal: () => void
}

// For production: reads from storage/matchMedia
const runtimeInitialState: UIState = {
  darkMode: getInitialDarkMode(),
  askPanelOpen: getInitialAskPanelOpen(),
  toasts: [],
  errorModal: null,
}

// For testing: fixed default values
export const initialState: UIState = {
  darkMode: false,
  askPanelOpen: false,
  toasts: [],
  errorModal: null,
}

export const useUIStore = create<UIState & UIActions>()(
  subscribeWithSelector((set, get) => ({
    ...runtimeInitialState,

    toggleDarkMode: () => {
      const newValue = !get().darkMode
      setStorageValue('darkMode', newValue)
      set({ darkMode: newValue })
    },

    setAskPanelOpen: (open) => {
      setStorageValue('askPanelOpen', open)
      set({ askPanelOpen: open })
    },

    addToast: (message, type) => {
      const id = `toast-${++toastIdCounter}`
      const toast: Toast = {
        id,
        message,
        type,
        createdAt: Date.now(),
      }
      set((state) => ({ toasts: [...state.toasts, toast] }))
      return id
    },

    dismissToast: (id) => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
    },

    showErrorModal: (title, message) => {
      set({ errorModal: { title, message } })
    },

    dismissErrorModal: () => {
      set({ errorModal: null })
    },
  }))
)

// Apply dark mode class to document
useUIStore.subscribe(
  (state) => state.darkMode,
  (darkMode) => {
    if (typeof document !== 'undefined') {
      if (darkMode) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }
  },
  { fireImmediately: true }
)
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- src/stores/uiStore.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/stores/uiStore.ts frontend/src/stores/uiStore.test.ts
git commit -m "refactor: update uiStore to use consolidated storage"
```

---

## Task 5: Update generationStore to Use New Storage

**Files:**
- Modify: `frontend/src/stores/generationStore.ts`
- Modify: `frontend/src/stores/generationStore.test.ts`

**Step 1: Update generationStore tests**

Add storage mock and update tests in `frontend/src/stores/generationStore.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useGenerationStore, initialState } from './generationStore'
import { useUIStore, initialState as uiInitialState } from './uiStore'
import * as api from '../api/client'
import * as storage from '../utils/storage'

vi.mock('../api/client', () => ({
  initRepo: vi.fn(),
  getJob: vi.fn(),
}))

vi.mock('../utils/storage', () => ({
  getStorageValue: vi.fn(() => null),
  setStorageValue: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  useGenerationStore.setState(initialState)
  useUIStore.setState(uiInitialState)
})

describe('generationStore', () => {
  describe('initial state', () => {
    it('has correct initial values', () => {
      const state = useGenerationStore.getState()
      expect(state.currentJob).toBeNull()
      expect(state.generationStatus).toBeNull()
    })
  })

  describe('startGeneration', () => {
    it('returns job_id on success', async () => {
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'test-job-123',
        status: 'pending',
        message: 'Created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'test-job-123',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBe('test-job-123')
      expect(useGenerationStore.getState().currentJob?.job_id).toBe('test-job-123')
    })

    it('persists job to storage', async () => {
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'test-job-123',
        status: 'pending',
        message: 'Created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'test-job-123',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      await useGenerationStore.getState().startGeneration()

      expect(storage.setStorageValue).toHaveBeenCalledWith(
        'currentJob',
        expect.objectContaining({ jobId: 'test-job-123' })
      )
    })

    it('clears generationStatus when starting', async () => {
      useGenerationStore.setState({ generationStatus: { status: 'incomplete', message: 'test' } })
      vi.mocked(api.initRepo).mockResolvedValue({
        job_id: 'job',
        status: 'pending',
        message: 'Created',
      })
      vi.mocked(api.getJob).mockResolvedValue({
        job_id: 'job',
        type: 'generation',
        status: 'running',
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      })

      await useGenerationStore.getState().startGeneration()

      expect(useGenerationStore.getState().generationStatus).toBeNull()
    })

    it('returns null and sets error on failure', async () => {
      vi.mocked(api.initRepo).mockRejectedValue(new Error('Server error'))

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBeNull()
      expect(useGenerationStore.getState().error).toBe('Server error')
    })

    it('shows error modal on failure', async () => {
      vi.mocked(api.initRepo).mockRejectedValue(new Error('Server error'))

      await useGenerationStore.getState().startGeneration()

      const errorModal = useUIStore.getState().errorModal
      expect(errorModal).not.toBeNull()
      expect(errorModal?.title).toBe('Generation Failed')
      expect(errorModal?.message).toBe('Server error')
    })

    it('returns null without calling API if already loading', async () => {
      useGenerationStore.setState({ isLoading: true })

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBeNull()
      expect(api.initRepo).not.toHaveBeenCalled()
    })

    it('returns null without calling API if job is already running', async () => {
      useGenerationStore.setState({
        currentJob: {
          job_id: 'existing',
          type: 'generation',
          status: 'running',
          started_at: null,
          completed_at: null,
          current_phase: null,
          total_phases: null,
          error_message: null,
        },
      })

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBeNull()
      expect(api.initRepo).not.toHaveBeenCalled()
    })

    it('returns null without calling API if job is pending', async () => {
      useGenerationStore.setState({
        currentJob: {
          job_id: 'existing',
          type: 'generation',
          status: 'pending',
          started_at: null,
          completed_at: null,
          current_phase: null,
          total_phases: null,
          error_message: null,
        },
      })

      const jobId = await useGenerationStore.getState().startGeneration()

      expect(jobId).toBeNull()
      expect(api.initRepo).not.toHaveBeenCalled()
    })
  })

  describe('setCurrentJob', () => {
    it('updates current job', () => {
      const job = {
        job_id: 'test',
        type: 'generation' as const,
        status: 'running' as const,
        started_at: null,
        completed_at: null,
        current_phase: null,
        total_phases: null,
        error_message: null,
      }

      useGenerationStore.getState().setCurrentJob(job)

      expect(useGenerationStore.getState().currentJob).toEqual(job)
    })

    it('clears job from storage when set to null', () => {
      useGenerationStore.getState().setCurrentJob(null)
      expect(storage.setStorageValue).toHaveBeenCalledWith('currentJob', null)
    })
  })

  describe('dismissGenerationStatus', () => {
    it('clears generation status', () => {
      useGenerationStore.setState({ generationStatus: { status: 'incomplete', message: 'test' } })

      useGenerationStore.getState().dismissGenerationStatus()

      expect(useGenerationStore.getState().generationStatus).toBeNull()
    })
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- src/stores/generationStore.test.ts`
Expected: FAIL - generationStore uses old storage functions

**Step 3: Update generationStore implementation**

Replace `frontend/src/stores/generationStore.ts`:

```typescript
import { create } from 'zustand'
import type { JobStatus, GenerationStatus } from '../types'
import * as api from '../api/client'
import { useUIStore } from './uiStore'
import { getStorageValue, setStorageValue, type StoredJobStatus } from '../utils/storage'

// Convert between API JobStatus (snake_case) and StoredJobStatus (camelCase)
function toStoredJob(job: JobStatus): StoredJobStatus {
  return {
    jobId: job.job_id,
    type: job.type,
    status: job.status,
    startedAt: job.started_at,
    completedAt: job.completed_at,
    currentPhase: job.current_phase,
    totalPhases: job.total_phases,
    errorMessage: job.error_message,
  }
}

function fromStoredJob(stored: StoredJobStatus): JobStatus {
  return {
    job_id: stored.jobId,
    type: stored.type,
    status: stored.status as JobStatus['status'],
    started_at: stored.startedAt,
    completed_at: stored.completedAt,
    current_phase: stored.currentPhase,
    total_phases: stored.totalPhases,
    error_message: stored.errorMessage,
  }
}

/**
 * Load current job from storage.
 * Returns null if not found or invalid.
 * Exported so initializeApp can call this after React is ready.
 */
export function loadStoredJob(): JobStatus | null {
  const stored = getStorageValue('currentJob')
  if (!stored) return null
  return fromStoredJob(stored)
}

/**
 * Save current job to storage.
 */
export function saveStoredJob(job: JobStatus | null): void {
  if (job && (job.status === 'running' || job.status === 'pending')) {
    setStorageValue('currentJob', toStoredJob(job))
  } else {
    setStorageValue('currentJob', null)
  }
}

interface GenerationState {
  currentJob: JobStatus | null
  generationStatus: GenerationStatus | null
  isLoading: boolean
  error: string | null
}

interface GenerationActions {
  startGeneration: (mode?: 'incremental' | 'full') => Promise<string | null>
  setCurrentJob: (job: JobStatus | null) => void
  setGenerationStatus: (status: GenerationStatus | null) => void
  dismissGenerationStatus: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const initialState: GenerationState = {
  currentJob: null,
  generationStatus: null,
  isLoading: false,
  error: null,
}

export const useGenerationStore = create<GenerationState & GenerationActions>()((set, get) => ({
  ...initialState,

  startGeneration: async (mode: 'incremental' | 'full' = 'incremental') => {
    const state = get()
    const jobIsActive =
      state.currentJob?.status === 'running' || state.currentJob?.status === 'pending'
    if (state.isLoading || jobIsActive) {
      return null
    }

    set({ isLoading: true, generationStatus: null, error: null })
    try {
      const result = await api.initRepo(mode)
      const job = await api.getJob(result.job_id)
      saveStoredJob(job)
      set({ currentJob: job })
      return result.job_id
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to start generation'
      set({ error: message })
      useUIStore.getState().showErrorModal('Generation Failed', message)
      return null
    } finally {
      set({ isLoading: false })
    }
  },

  setCurrentJob: (job) => {
    saveStoredJob(job)
    set({ currentJob: job })
  },
  setGenerationStatus: (status) => set({ generationStatus: status }),
  dismissGenerationStatus: () => set({ generationStatus: null }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}))
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- src/stores/generationStore.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/stores/generationStore.ts frontend/src/stores/generationStore.test.ts
git commit -m "refactor: update generationStore to use consolidated storage"
```

---

## Task 6: Update useResizablePanel Hook

**Files:**
- Modify: `frontend/src/hooks/useResizablePanel.ts`
- Modify: `frontend/src/hooks/useResizablePanel.test.ts`
- Modify: `frontend/src/components/Layout.tsx`

**Step 1: Update hook tests**

Replace `frontend/src/hooks/useResizablePanel.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useResizablePanel } from './useResizablePanel'
import * as storage from '../utils/storage'

vi.mock('../utils/storage', () => ({
  getStorageValue: vi.fn(() => 256),
  setStorageValue: vi.fn(),
  DEFAULT_STORAGE: {
    sidebarLeftWidth: 256,
    sidebarRightWidth: 200,
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useResizablePanel', () => {
  it('returns default width initially', () => {
    vi.mocked(storage.getStorageValue).mockReturnValue(256)
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'sidebarLeftWidth',
      })
    )
    expect(result.current.width).toBe(256)
  })

  it('loads width from storage', () => {
    vi.mocked(storage.getStorageValue).mockReturnValue(300)
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'sidebarLeftWidth',
      })
    )
    expect(result.current.width).toBe(300)
  })

  it('clamps width to max bounds', () => {
    vi.mocked(storage.getStorageValue).mockReturnValue(999)
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'sidebarLeftWidth',
      })
    )
    expect(result.current.width).toBe(400)
  })

  it('clamps width to minWidth when stored value is too small', () => {
    vi.mocked(storage.getStorageValue).mockReturnValue(50)
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'sidebarLeftWidth',
      })
    )
    expect(result.current.width).toBe(180)
  })

  it('provides isDragging state initially false', () => {
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'sidebarLeftWidth',
      })
    )
    expect(result.current.isDragging).toBe(false)
  })

  it('provides handleMouseDown function', () => {
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'sidebarLeftWidth',
      })
    )
    expect(typeof result.current.handleMouseDown).toBe('function')
  })

  it('persists width to storage after initialization', () => {
    vi.mocked(storage.getStorageValue).mockReturnValue(256)
    renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'sidebarLeftWidth',
      })
    )
    expect(storage.setStorageValue).toHaveBeenCalledWith('sidebarLeftWidth', 256)
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- src/hooks/useResizablePanel.test.ts`
Expected: FAIL - hook uses localStorage directly

**Step 3: Update hook implementation**

Replace `frontend/src/hooks/useResizablePanel.ts`:

```typescript
import { useState, useCallback, useEffect } from 'react'
import { getStorageValue, setStorageValue, type OyaStorage } from '../utils/storage'

type StorageWidthKey = 'sidebarLeftWidth' | 'sidebarRightWidth'

interface UseResizablePanelOptions {
  side: 'left' | 'right'
  defaultWidth: number
  minWidth: number
  maxWidth: number
  storageKey: StorageWidthKey
}

interface UseResizablePanelResult {
  width: number
  isDragging: boolean
  handleMouseDown: (e: React.MouseEvent) => void
}

export function useResizablePanel({
  side,
  defaultWidth,
  minWidth,
  maxWidth,
  storageKey,
}: UseResizablePanelOptions): UseResizablePanelResult {
  const [width, setWidth] = useState(() => {
    const stored = getStorageValue(storageKey)
    const value = stored ?? defaultWidth
    return Math.min(maxWidth, Math.max(minWidth, value))
  })
  const [isDragging, setIsDragging] = useState(false)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  useEffect(() => {
    if (!isDragging) return

    const handleMouseMove = (e: MouseEvent) => {
      let newWidth: number
      if (side === 'left') {
        newWidth = e.clientX
      } else {
        newWidth = window.innerWidth - e.clientX
      }
      newWidth = Math.min(maxWidth, Math.max(minWidth, newWidth))
      setWidth(newWidth)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      setStorageValue(storageKey, width)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, side, minWidth, maxWidth, storageKey, width])

  // Persist on width change (debounced via mouseup)
  useEffect(() => {
    if (!isDragging) {
      setStorageValue(storageKey, width)
    }
  }, [width, isDragging, storageKey])

  return { width, isDragging, handleMouseDown }
}
```

**Step 4: Update Layout.tsx to remove old storage imports**

In `frontend/src/components/Layout.tsx`, change line 20:

```typescript
// Remove this import:
// import { STORAGE_KEY_SIDEBAR_LEFT_WIDTH, STORAGE_KEY_SIDEBAR_RIGHT_WIDTH } from '../config/storage'
```

And update the hook calls (lines 43-57):

```typescript
  const leftPanel = useResizablePanel({
    side: 'left',
    defaultWidth: SIDEBAR_WIDTH,
    minWidth: SIDEBAR_MIN_WIDTH,
    maxWidth: SIDEBAR_MAX_WIDTH,
    storageKey: 'sidebarLeftWidth',
  })

  const rightPanel = useResizablePanel({
    side: 'right',
    defaultWidth: RIGHT_PANEL_WIDTH,
    minWidth: RIGHT_PANEL_MIN_WIDTH,
    maxWidth: RIGHT_PANEL_MAX_WIDTH,
    storageKey: 'sidebarRightWidth',
  })
```

**Step 5: Run tests to verify they pass**

Run: `cd frontend && npm run test -- src/hooks/useResizablePanel.test.ts`
Expected: PASS

**Step 6: Commit**

```bash
git add frontend/src/hooks/useResizablePanel.ts frontend/src/hooks/useResizablePanel.test.ts frontend/src/components/Layout.tsx
git commit -m "refactor: update useResizablePanel to use consolidated storage"
```

---

## Task 7: Update AskPanel QA Settings

**Files:**
- Modify: `frontend/src/components/AskPanel.tsx`
- Modify: `frontend/src/components/AskPanel.test.tsx`

**Step 1: Update AskPanel tests for storage**

In `frontend/src/components/AskPanel.test.tsx`, add storage mock:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { AskPanel } from './AskPanel'
import * as storage from '../utils/storage'

vi.mock('../utils/storage', () => ({
  getStorageValue: vi.fn(() => ({ quickMode: true, temperature: 0.5, timeoutMinutes: 3 })),
  setStorageValue: vi.fn(),
  DEFAULT_STORAGE: {
    qaSettings: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
  },
  DEFAULT_QA_SETTINGS: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
}))

// Mock stores
vi.mock('../stores', () => ({
  useGenerationStore: vi.fn(() => null),
  useWikiStore: vi.fn(() => ({
    overview: true,
    architecture: false,
    workflows: [],
    directories: [],
    files: [],
  })),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AskPanel', () => {
  const renderPanel = (isOpen = true) =>
    render(
      <BrowserRouter>
        <AskPanel isOpen={isOpen} onClose={vi.fn()} />
      </BrowserRouter>
    )

  it('renders when open', () => {
    renderPanel(true)
    expect(screen.getByText('Ask about this codebase')).toBeInTheDocument()
  })

  it('does not render when closed', () => {
    renderPanel(false)
    expect(screen.queryByText('Ask about this codebase')).not.toBeInTheDocument()
  })

  it('loads settings from storage on mount', () => {
    renderPanel(true)
    expect(storage.getStorageValue).toHaveBeenCalledWith('qaSettings')
  })
})
```

**Step 2: Run tests to verify behavior**

Run: `cd frontend && npm run test -- src/components/AskPanel.test.tsx`
Expected: May pass or fail depending on current state

**Step 3: Update AskPanel implementation**

In `frontend/src/components/AskPanel.tsx`, update imports and settings functions:

```typescript
import { useState, useRef, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { askQuestionStream } from '../api/client'
import { CONFIDENCE_COLORS } from '../config'
import { getStorageValue, setStorageValue, DEFAULT_QA_SETTINGS } from '../utils/storage'
import { QASettingsPopover, type QASettings } from './QASettingsPopover'
import { formatElapsedTime } from './generationConstants'
import { useWikiStore, useGenerationStore } from '../stores'
import type { Citation, SearchQuality, ConfidenceLevel } from '../types'
import { ThinkingIndicator } from './ThinkingIndicator'

// ... (QAMessage interface stays the same) ...

function loadSettings(): QASettings {
  const stored = getStorageValue('qaSettings')
  return {
    quickMode: stored.quickMode ?? DEFAULT_QA_SETTINGS.quickMode,
    temperature: stored.temperature ?? DEFAULT_QA_SETTINGS.temperature,
    timeoutMinutes: stored.timeoutMinutes ?? DEFAULT_QA_SETTINGS.timeoutMinutes,
  }
}

function saveSettings(settings: QASettings): void {
  setStorageValue('qaSettings', settings)
}

// ... rest of component stays the same ...
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- src/components/AskPanel.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/AskPanel.tsx frontend/src/components/AskPanel.test.tsx
git commit -m "refactor: update AskPanel to use consolidated storage"
```

---

## Task 8: Replace generationTiming.ts with Storage Calls

**Files:**
- Delete: `frontend/src/utils/generationTiming.ts`
- Delete: `frontend/src/utils/generationTiming.test.ts`
- Modify: Files that import from generationTiming.ts

**Step 1: Find all imports of generationTiming**

Run: `cd frontend && grep -r "from.*generationTiming" src/`

**Step 2: Update imports in dependent files**

For each file that imports from `generationTiming.ts`, change:

```typescript
// From:
import { savePhaseTiming, loadPhaseTiming, clearPhaseTiming, cleanupStaleTiming, type GenerationTiming } from '../utils/generationTiming'

// To:
import { setTimingForJob, getTimingForJob, clearTimingForJob, cleanupStaleTiming, type GenerationTiming } from '../utils/storage'
```

And update function calls:
- `savePhaseTiming(jobId, timing)` → `setTimingForJob(jobId, timing)`
- `loadPhaseTiming(jobId)` → `getTimingForJob(jobId)`
- `clearPhaseTiming(jobId)` → `clearTimingForJob(jobId)`
- `cleanupStaleTiming(maxAge)` → `cleanupStaleTiming(maxAge)` (same name)

**Step 3: Delete old files**

```bash
rm frontend/src/utils/generationTiming.ts frontend/src/utils/generationTiming.test.ts
```

**Step 4: Run all tests**

Run: `cd frontend && npm run test`
Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: replace generationTiming.ts with storage module"
```

---

## Task 9: Remove Old Config Keys

**Files:**
- Modify: `frontend/src/config/storage.ts`
- Modify: `frontend/src/config/qa.ts`
- Modify: `frontend/src/config/index.ts`

**Step 1: Update config/storage.ts**

Replace entire file:

```typescript
/**
 * Local storage configuration.
 *
 * All Oya storage is now consolidated in utils/storage.ts.
 * This file is kept for re-exporting layout-related defaults.
 */

// Re-export from utils/storage for backwards compatibility during migration
export { DEFAULT_STORAGE, DEFAULT_QA_SETTINGS } from '../utils/storage'
```

**Step 2: Update config/qa.ts**

Remove `QA_STORAGE_KEY` export (keep other exports):

```typescript
/**
 * Q&A panel configuration.
 *
 * Styling for the Ask panel, which displays answers with confidence levels.
 * Confidence indicates how well the search results matched the question:
 * high = strong matches found, medium = partial matches, low = weak/no matches.
 */

// =============================================================================
// Confidence Level Colors
// =============================================================================

export const CONFIDENCE_COLORS = {
  high: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  low: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
} as const

// =============================================================================
// Q&A Settings Constraints
// =============================================================================

export const QA_CONSTRAINTS = {
  temperature: { min: 0, max: 1, step: 0.1 },
  timeout: { min: 1, max: 10, step: 1 },
} as const

// Note: QA_DEFAULTS and QA_STORAGE_KEY moved to utils/storage.ts
```

**Step 3: Run all tests**

Run: `cd frontend && npm run test`
Expected: PASS

**Step 4: Run the build**

Run: `cd frontend && npm run build`
Expected: PASS (no TypeScript errors)

**Step 5: Commit**

```bash
git add frontend/src/config/storage.ts frontend/src/config/qa.ts
git commit -m "refactor: remove old storage keys from config"
```

---

## Task 10: Update CLAUDE.md Documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add localStorage documentation**

Add to `CLAUDE.md` under the "Frontend" configuration section:

```markdown
### localStorage

All Oya data is stored under a single `oya` key in localStorage. The storage module (`frontend/src/utils/storage.ts`) handles all access with automatic snake_case conversion.

**Key conventions:**
- All property names use `snake_case` in storage
- Runtime TypeScript types use `camelCase`
- Conversion happens at the storage boundary

**Storage structure:**
```typescript
{
  dark_mode: boolean,
  ask_panel_open: boolean,
  sidebar_left_width: number,
  sidebar_right_width: number,
  current_job: { job_id, status, ... } | null,
  qa_settings: { quick_mode, temperature, timeout_minutes },
  generation_timing: { [job_id]: { job_id, job_started_at, phases } }
}
```

**Usage:**
```typescript
import { getStorageValue, setStorageValue } from '../utils/storage'

// Read
const darkMode = getStorageValue('darkMode')

// Write
setStorageValue('darkMode', true)
```

Do not access localStorage directly. Always use the storage module.
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add localStorage conventions to CLAUDE.md"
```

---

## Task 11: Final Verification

**Step 1: Run all frontend tests**

Run: `cd frontend && npm run test`
Expected: All tests pass

**Step 2: Run the build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

**Step 3: Run lint**

Run: `cd frontend && npm run lint`
Expected: No errors

**Step 4: Manual verification**

1. Start the dev server: `cd frontend && npm run dev`
2. Open browser, check localStorage - should see single `oya` key
3. Toggle dark mode - verify it persists after refresh
4. Resize sidebar - verify width persists
5. If old keys exist, refresh and verify they're migrated

**Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address final issues from verification"
```
