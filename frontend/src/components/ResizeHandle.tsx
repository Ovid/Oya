/**
 * A draggable handle for resizing panels.
 *
 * Renders a thin vertical bar that shows visual feedback on hover and during
 * drag operations. Used by Layout to enable resizable sidebars.
 */

interface ResizeHandleProps {
  /** Which side of the panel this handle is on */
  side: 'left' | 'right'
  /** Position in pixels from the specified side */
  position: number
  /** Whether the panel is currently being dragged */
  isDragging: boolean
  /** Handler for mouse down events to start dragging */
  onMouseDown: (e: React.MouseEvent) => void
}

export function ResizeHandle({ side, position, isDragging, onMouseDown }: ResizeHandleProps) {
  return (
    <div
      onMouseDown={onMouseDown}
      className={`fixed top-14 bottom-0 w-1 cursor-col-resize transition-colors z-10 ${
        isDragging ? 'bg-blue-500' : 'bg-transparent hover:bg-blue-300'
      }`}
      style={{ [side]: position }}
    />
  )
}
