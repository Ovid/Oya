import { useState, useCallback, useEffect } from 'react'

interface UseResizablePanelOptions {
  side: 'left' | 'right'
  defaultWidth: number
  minWidth: number
  maxWidth: number
  storageKey: string
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
    const stored = localStorage.getItem(storageKey)
    if (stored) {
      const parsed = parseInt(stored, 10)
      if (!isNaN(parsed)) {
        return Math.min(maxWidth, Math.max(minWidth, parsed))
      }
    }
    return defaultWidth
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
      localStorage.setItem(storageKey, width.toString())
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
      localStorage.setItem(storageKey, width.toString())
    }
  }, [width, isDragging, storageKey])

  return { width, isDragging, handleMouseDown }
}
