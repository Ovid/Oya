import { useState, type ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { RightSidebar } from './RightSidebar';
import { AskPanel } from './AskPanel';
import { NoteEditor } from './NoteEditor';
import { InterruptedGenerationBanner } from './InterruptedGenerationBanner';
import { useApp } from '../context/useApp';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);
  const { state, closeNoteEditor, refreshTree, setAskPanelOpen } = useApp();
  const { noteEditor, askPanelOpen } = state;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
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
            <aside className="w-64 fixed left-0 top-14 bottom-0 overflow-y-auto border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
              <Sidebar />
            </aside>
          )}

          {/* Main Content */}
          <main
            className={`flex-1 min-h-[calc(100vh-3.5rem)] ${
              sidebarOpen ? 'ml-64' : ''
            } ${askPanelOpen ? 'mr-[350px]' : rightSidebarOpen ? 'mr-56' : ''}`}
          >
            <div className="max-w-4xl mx-auto px-6 py-8">
              {children}
            </div>
          </main>

          {/* Right Sidebar - TOC */}
          {rightSidebarOpen && !askPanelOpen && (
            <aside className="w-56 fixed right-0 top-14 bottom-0 overflow-y-auto border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
              <RightSidebar />
            </aside>
          )}

          {/* Ask Panel */}
          {askPanelOpen && (
            <aside className="w-[350px] fixed right-0 top-14 bottom-0 overflow-hidden border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
              <AskPanel
                isOpen={askPanelOpen}
                onClose={() => setAskPanelOpen(false)}
              />
            </aside>
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
  );
}
