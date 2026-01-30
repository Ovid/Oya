import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useResizablePanel } from './useResizablePanel'
import * as storage from '../utils/storage'

vi.mock('../utils/storage', () => ({
  getStorageValue: vi.fn(() => 256),
  setStorageValue: vi.fn(),
  hasStorageValue: vi.fn(() => false),
  getExplicitStorageValue: vi.fn(() => undefined),
  loadStorage: vi.fn(() => ({
    darkMode: false,
    askPanelOpen: false,
    sidebarLeftWidth: 256,
    sidebarRightWidth: 320,
    currentJob: null,
    qaSettings: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
    generationTiming: {},
  })),
  DEFAULT_STORAGE: {
    sidebarLeftWidth: 256,
    sidebarRightWidth: 320,
  },
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useResizablePanel', () => {
  it('returns default width when no stored preference exists', () => {
    vi.mocked(storage.hasStorageValue).mockReturnValue(false)
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

  it('loads width from storage when preference exists', () => {
    vi.mocked(storage.hasStorageValue).mockReturnValue(true)
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
    vi.mocked(storage.hasStorageValue).mockReturnValue(true)
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
    vi.mocked(storage.hasStorageValue).mockReturnValue(true)
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

  it('does not persist width on initialization (preserves no-preference state)', () => {
    vi.mocked(storage.hasStorageValue).mockReturnValue(false)
    renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'sidebarLeftWidth',
      })
    )
    // Should NOT write to storage on mount - only on drag end
    expect(storage.setStorageValue).not.toHaveBeenCalled()
  })
})
