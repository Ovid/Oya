import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { GenerationProgress } from './GenerationProgress'
import { formatElapsedTime, PHASE_ORDER, PHASES } from './generationConstants'
import type { ProgressEvent } from '../types'
import * as client from '../api/client'
import { useUIStore, initialState } from '../stores/uiStore'
import { loadPhaseTiming, savePhaseTiming, clearPhaseTiming } from '../utils/generationTiming'

// Mock the API client
vi.mock('../api/client', () => ({
  streamJobProgress: vi.fn(),
  cancelJob: vi.fn(),
}))

vi.mock('../utils/generationTiming', () => ({
  loadPhaseTiming: vi.fn(),
  savePhaseTiming: vi.fn(),
  clearPhaseTiming: vi.fn(),
  cleanupStaleTiming: vi.fn(),
}))

/**
 * Tests for GenerationProgress phase ordering.
 *
 * The bottom-up generation pipeline runs phases in this order:
 * Sync → Files → Directories → Synthesis → Architecture → Overview → Workflows → Indexing
 *
 * The frontend must display phases in this same order to correctly show
 * which phases are completed vs in-progress.
 */

// Extract the constants from the component for testing
// This ensures the phase order matches the backend's bottom-up approach
const EXPECTED_PHASE_ORDER = [
  'syncing',
  'files',
  'directories',
  'synthesis',
  'architecture',
  'overview',
  'workflows',
  'indexing',
]

const EXPECTED_PHASES = {
  syncing: { name: 'Sync', description: 'Syncing repository and scanning code...' },
  files: { name: 'Files', description: 'Generating file-level documentation...' },
  directories: { name: 'Directories', description: 'Generating directory documentation...' },
  synthesis: { name: 'Synthesis', description: 'Synthesizing codebase understanding...' },
  architecture: { name: 'Architecture', description: 'Analyzing and documenting architecture...' },
  overview: { name: 'Overview', description: 'Generating project overview page...' },
  workflows: { name: 'Workflows', description: 'Discovering and documenting workflows...' },
  indexing: { name: 'Indexing', description: 'Indexing content for search and Q&A...' },
}

describe('GenerationProgress phase ordering', () => {
  it('should have phases in bottom-up order (files before architecture/overview)', () => {
    expect(PHASE_ORDER).toEqual(EXPECTED_PHASE_ORDER)
  })

  it('should have files phase before architecture phase', () => {
    const filesIndex = PHASE_ORDER.indexOf('files')
    const architectureIndex = PHASE_ORDER.indexOf('architecture')
    expect(filesIndex).toBeLessThan(architectureIndex)
  })

  it('should have files phase before overview phase', () => {
    const filesIndex = PHASE_ORDER.indexOf('files')
    const overviewIndex = PHASE_ORDER.indexOf('overview')
    expect(filesIndex).toBeLessThan(overviewIndex)
  })

  it('should have directories phase before synthesis phase', () => {
    const directoriesIndex = PHASE_ORDER.indexOf('directories')
    const synthesisIndex = PHASE_ORDER.indexOf('synthesis')
    expect(directoriesIndex).toBeLessThan(synthesisIndex)
  })

  it('should have synthesis phase before architecture and overview', () => {
    const synthesisIndex = PHASE_ORDER.indexOf('synthesis')
    const architectureIndex = PHASE_ORDER.indexOf('architecture')
    const overviewIndex = PHASE_ORDER.indexOf('overview')

    expect(synthesisIndex).toBeLessThan(architectureIndex)
    expect(synthesisIndex).toBeLessThan(overviewIndex)
  })

  it('should include synthesis phase', () => {
    expect(PHASE_ORDER).toContain('synthesis')
  })

  it('should include indexing phase', () => {
    expect(PHASE_ORDER).toContain('indexing')
  })

  it('should have 8 phases total', () => {
    expect(PHASE_ORDER).toHaveLength(8)
  })
})

describe('formatElapsedTime', () => {
  it('should format seconds under a minute', () => {
    expect(formatElapsedTime(0)).toBe('0s')
    expect(formatElapsedTime(1)).toBe('1s')
    expect(formatElapsedTime(45)).toBe('45s')
    expect(formatElapsedTime(59)).toBe('59s')
  })

  it('should format minutes and seconds', () => {
    expect(formatElapsedTime(60)).toBe('1m 0s')
    expect(formatElapsedTime(61)).toBe('1m 1s')
    expect(formatElapsedTime(90)).toBe('1m 30s')
    expect(formatElapsedTime(125)).toBe('2m 5s')
  })

  it('should handle larger values', () => {
    expect(formatElapsedTime(3600)).toBe('60m 0s')
    expect(formatElapsedTime(3661)).toBe('61m 1s')
  })
})

describe('GenerationProgress phase definitions', () => {
  it('should have info for all phases in PHASE_ORDER', () => {
    for (const phase of PHASE_ORDER) {
      expect(PHASES[phase]).toBeDefined()
      expect(PHASES[phase].name).toBeTruthy()
      expect(PHASES[phase].description).toBeTruthy()
    }
  })

  it('should have synthesis phase info', () => {
    expect(PHASES['synthesis']).toBeDefined()
    expect(PHASES['synthesis'].name).toBe('Synthesis')
  })

  it('should have indexing phase info', () => {
    expect(PHASES['indexing']).toBeDefined()
    expect(PHASES['indexing'].name).toBe('Indexing')
  })

  it('should match expected phase definitions', () => {
    expect(PHASES).toEqual(EXPECTED_PHASES)
  })
})

describe('GenerationProgress error handling', () => {
  let capturedOnError: ((error: Error) => void) | null = null

  beforeEach(() => {
    vi.useFakeTimers()
    capturedOnError = null
    useUIStore.setState(initialState)

    // Mock streamJobProgress to capture the onError callback
    vi.mocked(client.streamJobProgress).mockImplementation(
      (
        _jobId: string,
        _onProgress: (event: ProgressEvent) => void,
        _onComplete: (event: ProgressEvent) => void,
        onError: (error: Error) => void
      ) => {
        capturedOnError = onError
        return () => {} // cleanup function
      }
    )
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('should display error state when job fails', () => {
    const onComplete = vi.fn()
    const onError = vi.fn()

    render(<GenerationProgress jobId="test-job-123" onComplete={onComplete} onError={onError} />)

    // Simulate an error event from the SSE stream
    act(() => {
      if (capturedOnError) {
        capturedOnError(new Error('Pull failed: divergent branches'))
      }
    })

    // Error state should be displayed (inline message, not the full error text)
    expect(screen.getByText('Generation Failed')).toBeInTheDocument()
    expect(screen.getByText('An error occurred during wiki generation.')).toBeInTheDocument()
  })

  it('should call showErrorModal and onError when job fails', () => {
    const onComplete = vi.fn()
    const onError = vi.fn()

    render(<GenerationProgress jobId="test-job-123" onComplete={onComplete} onError={onError} />)

    // Simulate an error event
    act(() => {
      if (capturedOnError) {
        capturedOnError(new Error('Some error'))
      }
    })

    // showErrorModal should have been called - verify by checking state
    expect(useUIStore.getState().errorModal).toEqual({
      title: 'Generation Failed',
      message: 'Some error',
    })
    // onError callback should be called with the error message
    expect(onError).toHaveBeenCalledWith('Some error')
  })
})

describe('GenerationProgress timing persistence', () => {
  let capturedOnProgress: ((event: ProgressEvent) => void) | null = null
  let capturedOnComplete: (() => void) | null = null

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-29T12:00:00Z'))
    capturedOnProgress = null
    capturedOnComplete = null
    useUIStore.setState(initialState)

    vi.mocked(loadPhaseTiming).mockReturnValue(null)
    vi.mocked(savePhaseTiming).mockClear()
    vi.mocked(clearPhaseTiming).mockClear()

    vi.mocked(client.streamJobProgress).mockImplementation(
      (
        _jobId: string,
        onProgress: (event: ProgressEvent) => void,
        onComplete: () => void
      ) => {
        capturedOnProgress = onProgress
        capturedOnComplete = onComplete
        return () => {}
      }
    )
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('should load timing data on mount', () => {
    render(<GenerationProgress jobId="test-job" onComplete={vi.fn()} onError={vi.fn()} />)
    expect(loadPhaseTiming).toHaveBeenCalledWith('test-job')
  })

  it('should restore completed phase durations from localStorage', () => {
    vi.mocked(loadPhaseTiming).mockReturnValue({
      jobId: 'test-job',
      jobStartedAt: Date.now() - 120000,
      phases: {
        syncing: { startedAt: Date.now() - 120000, completedAt: Date.now() - 110000, duration: 10 },
        files: { startedAt: Date.now() - 110000, completedAt: Date.now() - 60000, duration: 50 },
        directories: { startedAt: Date.now() - 60000 },
      },
    })

    render(<GenerationProgress jobId="test-job" onComplete={vi.fn()} onError={vi.fn()} />)

    act(() => {
      if (capturedOnProgress) {
        capturedOnProgress({ phase: '3:directories', total_phases: 8 })
      }
    })

    expect(screen.getByText('10s')).toBeInTheDocument()
    expect(screen.getByText('50s')).toBeInTheDocument()
  })

  it('should save timing when phase changes', () => {
    render(<GenerationProgress jobId="test-job" onComplete={vi.fn()} onError={vi.fn()} />)

    act(() => {
      if (capturedOnProgress) {
        capturedOnProgress({ phase: '1:syncing', total_phases: 8 })
      }
    })

    act(() => {
      vi.advanceTimersByTime(5000)
    })
    act(() => {
      if (capturedOnProgress) {
        capturedOnProgress({ phase: '2:files', total_phases: 8 })
      }
    })

    expect(savePhaseTiming).toHaveBeenCalled()
  })

  it('should clear timing on job completion', () => {
    render(<GenerationProgress jobId="test-job" onComplete={vi.fn()} onError={vi.fn()} />)

    act(() => {
      if (capturedOnComplete) {
        capturedOnComplete()
      }
    })

    expect(clearPhaseTiming).toHaveBeenCalledWith('test-job')
  })

  it('should clear timing on job error', () => {
    let capturedOnError: ((error: Error) => void) | null = null

    vi.mocked(client.streamJobProgress).mockImplementation(
      (
        _jobId: string,
        _onProgress: (event: ProgressEvent) => void,
        _onComplete: () => void,
        onError: (error: Error) => void
      ) => {
        capturedOnError = onError
        return () => {}
      }
    )

    render(<GenerationProgress jobId="test-job" onComplete={vi.fn()} onError={vi.fn()} />)

    act(() => {
      if (capturedOnError) {
        capturedOnError(new Error('Test error'))
      }
    })

    expect(clearPhaseTiming).toHaveBeenCalledWith('test-job')
  })

  it('should clear timing on job cancellation', () => {
    let capturedOnCancelled: (() => void) | null = null

    vi.mocked(client.streamJobProgress).mockImplementation(
      (
        _jobId: string,
        _onProgress: (event: ProgressEvent) => void,
        _onComplete: () => void,
        _onError: (error: Error) => void,
        onCancelled?: () => void
      ) => {
        capturedOnCancelled = onCancelled || null
        return () => {}
      }
    )

    render(<GenerationProgress jobId="test-job" onComplete={vi.fn()} onError={vi.fn()} onCancelled={vi.fn()} />)

    act(() => {
      if (capturedOnCancelled) {
        capturedOnCancelled()
      }
    })

    expect(clearPhaseTiming).toHaveBeenCalledWith('test-job')
  })
})
