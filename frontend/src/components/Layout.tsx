import { useState, type ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { RightSidebar } from './RightSidebar';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(true);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <TopBar
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        onToggleRightSidebar={() => setRightSidebarOpen(!rightSidebarOpen)}
      />

      <div className="flex pt-14">
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
          } ${rightSidebarOpen ? 'mr-56' : ''}`}
        >
          <div className="max-w-4xl mx-auto px-6 py-8">
            {children}
          </div>
        </main>

        {/* Right Sidebar */}
        {rightSidebarOpen && (
          <aside className="w-56 fixed right-0 top-14 bottom-0 overflow-y-auto border-l border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
            <RightSidebar />
          </aside>
        )}
      </div>
    </div>
  );
}
