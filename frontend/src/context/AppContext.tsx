import { createContext, useContext, useReducer, useEffect, type ReactNode } from 'react';
import type { RepoStatus, WikiTree, WikiPage, JobStatus } from '../types';
import * as api from '../api/client';

interface AppState {
  repoStatus: RepoStatus | null;
  wikiTree: WikiTree | null;
  currentPage: WikiPage | null;
  currentJob: JobStatus | null;
  isLoading: boolean;
  error: string | null;
}

type Action =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_REPO_STATUS'; payload: RepoStatus }
  | { type: 'SET_WIKI_TREE'; payload: WikiTree }
  | { type: 'SET_CURRENT_PAGE'; payload: WikiPage | null }
  | { type: 'SET_CURRENT_JOB'; payload: JobStatus | null };

const initialState: AppState = {
  repoStatus: null,
  wikiTree: null,
  currentPage: null,
  currentJob: null,
  isLoading: true,
  error: null,
};

function appReducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false };
    case 'SET_REPO_STATUS':
      return { ...state, repoStatus: action.payload };
    case 'SET_WIKI_TREE':
      return { ...state, wikiTree: action.payload };
    case 'SET_CURRENT_PAGE':
      return { ...state, currentPage: action.payload };
    case 'SET_CURRENT_JOB':
      return { ...state, currentJob: action.payload };
    default:
      return state;
  }
}

interface AppContextValue {
  state: AppState;
  dispatch: React.Dispatch<Action>;
  refreshStatus: () => Promise<void>;
  refreshTree: () => Promise<void>;
  startGeneration: () => Promise<string | null>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  const refreshStatus = async () => {
    try {
      const status = await api.getRepoStatus();
      dispatch({ type: 'SET_REPO_STATUS', payload: status });
    } catch (err) {
      dispatch({ type: 'SET_ERROR', payload: 'Failed to fetch repo status' });
    }
  };

  const refreshTree = async () => {
    try {
      const tree = await api.getWikiTree();
      dispatch({ type: 'SET_WIKI_TREE', payload: tree });
    } catch {
      // Wiki tree may not exist yet, ignore error
    }
  };

  const startGeneration = async (): Promise<string | null> => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true });
      const result = await api.initRepo();

      // Start polling job status
      const job = await api.getJob(result.job_id);
      dispatch({ type: 'SET_CURRENT_JOB', payload: job });

      return result.job_id;
    } catch (err) {
      dispatch({ type: 'SET_ERROR', payload: 'Failed to start generation' });
      return null;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  // Initial data load
  useEffect(() => {
    const init = async () => {
      dispatch({ type: 'SET_LOADING', payload: true });
      await refreshStatus();
      await refreshTree();
      dispatch({ type: 'SET_LOADING', payload: false });
    };
    init();
  }, []);

  return (
    <AppContext.Provider value={{ state, dispatch, refreshStatus, refreshTree, startGeneration }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
}
