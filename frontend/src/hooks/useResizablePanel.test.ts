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
