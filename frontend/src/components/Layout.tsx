import { useState, type ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { RightSidebar } from './RightSidebar'
import { AskPanel } from './AskPanel'
import { NoteEditor } from './NoteEditor'
import { InterruptedGenerationBanner } from './InterruptedGenerationBanner'
import { useApp } from '../context/useApp'
import { useResizablePanel } from '../hooks/useResizablePanel'
import {
  SIDEBAR_WIDTH,
  SIDEBAR_MIN_WIDTH,
  SIDEBAR_MAX_WIDTH,
  RIGHT_SIDEBAR_WIDTH,
  ASK_PANEL_WIDTH,
  ASK_PANEL_MIN_WIDTH,
  ASK_PANEL_MAX_WIDTH,
} from '../config/layout'
import { STORAGE_KEY_SIDEBAR_LEFT_WIDTH, STORAGE_KEY_SIDEBAR_RIGHT_WIDTH } from '../config/storage'

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true)
  const { state, closeNoteEditor, refreshTree, setAskPanelOpen } = useApp()
  const { noteEditor, askPanelOpen } = state

  const leftPanel = useResizablePanel({
    side: 'left',
    defaultWidth: SIDEBAR_WIDTH,
    minWidth: SIDEBAR_MIN_WIDTH,
    maxWidth: SIDEBAR_MAX_WIDTH,
    storageKey: STORAGE_KEY_SIDEBAR_LEFT_WIDTH,
  })

  const rightPanel = useResizablePanel({
    side: 'right',
    defaultWidth: ASK_PANEL_WIDTH,
    minWidth: ASK_PANEL_MIN_WIDTH,
    maxWidth: ASK_PANEL_MAX_WIDTH,
    storageKey: STORAGE_KEY_SIDEBAR_RIGHT_WIDTH,
  })

  // Determine if any panel is being dragged (for global cursor style)
  const isDragging = leftPanel.isDragging || rightPanel.isDragging

  return (
    <div
      className={`min-h-screen bg-gray-50 dark:bg-gray-900 ${
        isDragging ? 'cursor-col-resize select-none' : ''
      }`}
    >
      <TopBar
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        onToggleRightSidebar={() => setRightSidebarOpen(!rightSidebarOpen)}
        onToggleAskPanel={() => setAskPanelOpen(!askPanelOpen)}
        askPanelOpen={askPanelOpen}
      />

      <div className="pt-14">
        {/* Interrupted Generation Banner */}
        <InterruptedGenerationBanner />

        <div className="flex">
          {/* Left Sidebar */}
          {sidebarOpen && (
            <>
              <aside
                className="fixed left-0 top-14 bottom-0 overflow-y-auto border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
                style={{ width: leftPanel.width }}
              >
                <Sidebar />
              </aside>
              {/* Left resize handle */}
              <div
                onMouseDown={leftPanel.handleMouseDown}
                className={`fixed top-14 bottom-0 w-1 cursor-col-resize transition-colors z-10 ${
                  leftPanel.isDragging ? 'bg-blue-500' : 'bg-transparent hover:bg-blue-300'
                }`}
                style={{ left: leftPanel.width - 2 }}
              />
            </>
          )}

          {/* Main Content */}
          <main
            className="flex-1 min-h-[calc(100vh-3.5rem)]"
            style={{
              marginLeft: sidebarOpen ? leftPanel.width : 0,
              marginRight: askPanelOpen
                ? rightPanel.width
                : rightSidebarOpen
                  ? RIGHT_SIDEBAR_WIDTH
                  : 0,
            }}
          >
            <div className="max-w-4xl mx-auto px-6 py-8">{children}</div>
          </main>

          {/* Right Sidebar - TOC (fixed width, not resizable) */}
          {rightSidebarOpen && !askPanelOpen && (
            <aside
              className="fixed right-0 top-14 bottom-0 overflow-y-auto border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
              style={{ width: RIGHT_SIDEBAR_WIDTH }}
            >
              <RightSidebar />
            </aside>
          )}

          {/* Ask Panel */}
          {askPanelOpen && (
            <>
              {/* Right resize handle */}
              <div
                onMouseDown={rightPanel.handleMouseDown}
                className={`fixed top-14 bottom-0 w-1 cursor-col-resize transition-colors z-10 ${
                  rightPanel.isDragging ? 'bg-blue-500' : 'bg-transparent hover:bg-blue-300'
                }`}
                style={{ right: rightPanel.width - 2 }}
              />
              <aside
                className="fixed right-0 top-14 bottom-0 overflow-hidden border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
                style={{ width: rightPanel.width }}
              >
                <AskPanel isOpen={askPanelOpen} onClose={() => setAskPanelOpen(false)} />
              </aside>
            </>
          )}
        </div>
      </div>

      {/* Note Editor */}
      <NoteEditor
        isOpen={noteEditor.isOpen}
        onClose={closeNoteEditor}
        onNoteCreated={() => refreshTree()}
        defaultScope={noteEditor.defaultScope}
        defaultTarget={noteEditor.defaultTarget}
      />
    </div>
  )
}
