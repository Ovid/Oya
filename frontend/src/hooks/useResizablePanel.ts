import { useState, useCallback, useEffect, useRef } from 'react'
import { getStorageValue, setStorageValue, hasStorageValue } from '../utils/storage'

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
    // Only use stored value if user has explicitly set a preference
    if (hasStorageValue(storageKey)) {
      const stored = getStorageValue(storageKey)
      return Math.min(maxWidth, Math.max(minWidth, stored))
    }
    return defaultWidth
  })
  const [isDragging, setIsDragging] = useState(false)
  const wasDraggingRef = useRef(false)

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
      // Persistence handled by the useEffect that watches isDragging transitions
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, side, minWidth, maxWidth, storageKey, width])

  // Persist only on drag end (transition from dragging to not dragging)
  // This avoids writing defaults on mount when user hasn't resized
  useEffect(() => {
    if (wasDraggingRef.current && !isDragging) {
      setStorageValue(storageKey, width)
    }
    wasDraggingRef.current = isDragging
  }, [width, isDragging, storageKey])

  return { width, isDragging, handleMouseDown }
}
