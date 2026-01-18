import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useResizablePanel } from './useResizablePanel'

describe('useResizablePanel', () => {
  let localStorageMock: {
    getItem: ReturnType<typeof vi.fn>
    setItem: ReturnType<typeof vi.fn>
    removeItem: ReturnType<typeof vi.fn>
    clear: ReturnType<typeof vi.fn>
    length: number
    key: ReturnType<typeof vi.fn>
  }

  beforeEach(() => {
    // Mock localStorage
    localStorageMock = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      length: 0,
      key: vi.fn(),
    }
    vi.stubGlobal('localStorage', localStorageMock)
  })

  it('returns default width initially', () => {
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'test-width',
      })
    )
    expect(result.current.width).toBe(256)
  })

  it('loads width from localStorage', () => {
    localStorageMock.getItem.mockReturnValue('300')
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'test-width',
      })
    )
    expect(result.current.width).toBe(300)
  })

  it('clamps width to max bounds', () => {
    localStorageMock.getItem.mockReturnValue('999')
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'test-width',
      })
    )
    expect(result.current.width).toBe(400)
  })

  it('clamps width to minWidth when stored value is too small', () => {
    localStorageMock.getItem.mockReturnValue('50')
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'test-width',
      })
    )
    expect(result.current.width).toBe(180)
  })

  it('ignores invalid stored values', () => {
    localStorageMock.getItem.mockReturnValue('not-a-number')
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'test-width',
      })
    )
    expect(result.current.width).toBe(256)
  })

  it('provides isDragging state initially false', () => {
    const { result } = renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'test-width',
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
        storageKey: 'test-width',
      })
    )
    expect(typeof result.current.handleMouseDown).toBe('function')
  })

  it('persists width to localStorage after initialization', () => {
    renderHook(() =>
      useResizablePanel({
        side: 'left',
        defaultWidth: 256,
        minWidth: 180,
        maxWidth: 400,
        storageKey: 'test-width',
      })
    )
    // Persistence happens via useEffect
    expect(localStorageMock.setItem).toHaveBeenCalledWith('test-width', '256')
  })
})
