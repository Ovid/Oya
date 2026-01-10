import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import type { RepoStatus, WikiTree } from '../types';

// Mock the API module - must be before imports that use it
vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  switchWorkspace: vi.fn(),
  initRepo: vi.fn(),
  getJob: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
    }
  },
}));

// Setup global mocks for browser APIs
beforeEach(() => {
  // Mock localStorage
  const localStorageMock = {
    getItem: vi.fn(() => null),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
    length: 0,
    key: vi.fn(),
  };
  vi.stubGlobal('localStorage', localStorageMock);

  // Mock matchMedia
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })));
});

// Dynamic import to ensure mocks are set up first
let AppProvider: typeof import('./AppContext').AppProvider;
let useApp: typeof import('./AppContext').useApp;
let api: typeof import('../api/client');

beforeEach(async () => {
  vi.resetModules();
  const appContextModule = await import('./AppContext');
  AppProvider = appContextModule.AppProvider;
  useApp = appContextModule.useApp;
  api = await import('../api/client');
  vi.clearAllMocks();
});

// Test component that exposes context values
function TestConsumer({ onMount }: { onMount?: (ctx: ReturnType<typeof useApp>) => void }) {
  const ctx = useApp();
  if (onMount) {
    onMount(ctx);
  }
  return (
    <div>
      <span data-testid="repo-path">{ctx.state.repoStatus?.path ?? 'none'}</span>
      <span data-testid="current-page">{ctx.state.currentPage?.path ?? 'none'}</span>
      <span data-testid="is-dirty">{String(ctx.state.noteEditor.isDirty ?? false)}</span>
      <span data-testid="is-loading">{String(ctx.state.isLoading)}</span>
      <span data-testid="error">{ctx.state.error ?? 'none'}</span>
    </div>
  );
}

const mockRepoStatus: RepoStatus = {
  path: '/home/user/project',
  head_commit: 'abc123',
  head_message: 'Initial commit',
  branch: 'main',
  initialized: true,
  is_docker: false,
  last_generation: null,
  generation_status: null,
  embedding_metadata: null,
  current_provider: null,
  current_model: null,
  embedding_mismatch: false,
};

const mockWikiTree: WikiTree = {
  overview: true,
  architecture: true,
  workflows: [],
  directories: [],
  files: [],
};

describe('AppContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock implementations
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus);
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree);
  });

  describe('switchWorkspace', () => {
    it('updates repo status on successful switch', async () => {
      const newRepoStatus: RepoStatus = {
        ...mockRepoStatus,
        path: '/home/user/new-project',
      };
      
      vi.mocked(api.switchWorkspace).mockResolvedValue({
        status: newRepoStatus,
        message: 'Workspace switched successfully',
      });

      let contextRef: ReturnType<typeof useApp> | null = null;
      
      render(
        <AppProvider>
          <TestConsumer onMount={(ctx) => { contextRef = ctx; }} />
        </AppProvider>
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('repo-path')).toHaveTextContent('/home/user/project');
      });

      // Switch workspace
      await act(async () => {
        await contextRef!.switchWorkspace('/home/user/new-project');
      });

      expect(screen.getByTestId('repo-path')).toHaveTextContent('/home/user/new-project');
    });

    it('clears current page on workspace switch', async () => {
      const newRepoStatus: RepoStatus = {
        ...mockRepoStatus,
        path: '/home/user/new-project',
      };
      
      vi.mocked(api.switchWorkspace).mockResolvedValue({
        status: newRepoStatus,
        message: 'Workspace switched successfully',
      });

      let contextRef: ReturnType<typeof useApp> | null = null;
      
      render(
        <AppProvider>
          <TestConsumer onMount={(ctx) => { contextRef = ctx; }} />
        </AppProvider>
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false');
      });

      // Set a current page first
      act(() => {
        contextRef!.dispatch({
          type: 'SET_CURRENT_PAGE',
          payload: {
            content: 'test',
            page_type: 'overview',
            path: '/overview',
            word_count: 10,
            source_path: null,
          },
        });
      });

      expect(screen.getByTestId('current-page')).toHaveTextContent('/overview');

      // Switch workspace
      await act(async () => {
        await contextRef!.switchWorkspace('/home/user/new-project');
      });

      expect(screen.getByTestId('current-page')).toHaveTextContent('none');
    });

    it('handles errors during workspace switch', async () => {
      // Create an error that will be caught and have its message extracted
      const error = new Error('Path does not exist');
      vi.mocked(api.switchWorkspace).mockRejectedValue(error);

      let contextRef: ReturnType<typeof useApp> | null = null;
      
      render(
        <AppProvider>
          <TestConsumer onMount={(ctx) => { contextRef = ctx; }} />
        </AppProvider>
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false');
      });

      // Switch workspace - should throw and set error state
      let caughtError: Error | null = null;
      await act(async () => {
        try {
          await contextRef!.switchWorkspace('/invalid/path');
        } catch (e) {
          caughtError = e as Error;
        }
      });

      // Verify the error was thrown
      expect(caughtError).not.toBeNull();
      
      // The error message should be the fallback since it's not an ApiError instance
      expect(screen.getByTestId('error')).toHaveTextContent('Failed to switch workspace');
    });

    it('refreshes wiki tree after successful switch', async () => {
      const newRepoStatus: RepoStatus = {
        ...mockRepoStatus,
        path: '/home/user/new-project',
      };
      
      vi.mocked(api.switchWorkspace).mockResolvedValue({
        status: newRepoStatus,
        message: 'Workspace switched successfully',
      });

      let contextRef: ReturnType<typeof useApp> | null = null;
      
      render(
        <AppProvider>
          <TestConsumer onMount={(ctx) => { contextRef = ctx; }} />
        </AppProvider>
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false');
      });

      // Clear the mock call count from initial load
      vi.mocked(api.getWikiTree).mockClear();

      // Switch workspace
      await act(async () => {
        await contextRef!.switchWorkspace('/home/user/new-project');
      });

      // Should have called getWikiTree to refresh
      expect(api.getWikiTree).toHaveBeenCalled();
    });
  });

  describe('setNoteEditorDirty', () => {
    it('updates isDirty state to true', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null;
      
      render(
        <AppProvider>
          <TestConsumer onMount={(ctx) => { contextRef = ctx; }} />
        </AppProvider>
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false');
      });

      // Initially isDirty should be false
      expect(screen.getByTestId('is-dirty')).toHaveTextContent('false');

      // Set dirty state
      act(() => {
        contextRef!.setNoteEditorDirty(true);
      });

      expect(screen.getByTestId('is-dirty')).toHaveTextContent('true');
    });

    it('updates isDirty state to false', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null;
      
      render(
        <AppProvider>
          <TestConsumer onMount={(ctx) => { contextRef = ctx; }} />
        </AppProvider>
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false');
      });

      // Set dirty state to true first
      act(() => {
        contextRef!.setNoteEditorDirty(true);
      });

      expect(screen.getByTestId('is-dirty')).toHaveTextContent('true');

      // Set dirty state back to false
      act(() => {
        contextRef!.setNoteEditorDirty(false);
      });

      expect(screen.getByTestId('is-dirty')).toHaveTextContent('false');
    });

    it('resets isDirty to false when closing note editor', async () => {
      let contextRef: ReturnType<typeof useApp> | null = null;
      
      render(
        <AppProvider>
          <TestConsumer onMount={(ctx) => { contextRef = ctx; }} />
        </AppProvider>
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('is-loading')).toHaveTextContent('false');
      });

      // Open note editor and set dirty
      act(() => {
        contextRef!.openNoteEditor('general', '');
        contextRef!.setNoteEditorDirty(true);
      });

      expect(screen.getByTestId('is-dirty')).toHaveTextContent('true');

      // Close note editor
      act(() => {
        contextRef!.closeNoteEditor();
      });

      // isDirty should be reset to false
      expect(screen.getByTestId('is-dirty')).toHaveTextContent('false');
    });
  });
});
