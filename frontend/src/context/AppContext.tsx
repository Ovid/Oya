import { createContext, useReducer, useEffect, type ReactNode } from 'react'
import type {
  RepoStatus,
  WikiTree,
  WikiPage,
  JobStatus,
  NoteScope,
  GenerationStatus,
} from '../types'
import { STORAGE_KEY_ASK_PANEL_OPEN, STORAGE_KEY_DARK_MODE } from '../config'
import * as api from '../api/client'

interface NoteEditorState {
  isOpen: boolean
  isDirty: boolean
  defaultScope: NoteScope
  defaultTarget: string
}

interface AppState {
  repoStatus: RepoStatus | null
  wikiTree: WikiTree | null
  currentPage: WikiPage | null
  currentJob: JobStatus | null
  isLoading: boolean
  error: string | null
  noteEditor: NoteEditorState
  darkMode: boolean
  generationStatus: GenerationStatus | null
  askPanelOpen: boolean
  showUpToDateModal: boolean
}

type Action =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_REPO_STATUS'; payload: RepoStatus }
  | { type: 'SET_WIKI_TREE'; payload: WikiTree }
  | { type: 'SET_CURRENT_PAGE'; payload: WikiPage | null }
  | { type: 'SET_CURRENT_JOB'; payload: JobStatus | null }
  | { type: 'OPEN_NOTE_EDITOR'; payload: { scope: NoteScope; target: string } }
  | { type: 'CLOSE_NOTE_EDITOR' }
  | { type: 'SET_NOTE_EDITOR_DIRTY'; payload: boolean }
  | { type: 'SET_DARK_MODE'; payload: boolean }
  | { type: 'SET_GENERATION_STATUS'; payload: GenerationStatus | null }
  | { type: 'SET_ASK_PANEL_OPEN'; payload: boolean }
  | { type: 'SET_UP_TO_DATE_MODAL'; payload: boolean }

function getInitialDarkMode(): boolean {
  if (typeof window === 'undefined') return false
  const stored = localStorage.getItem(STORAGE_KEY_DARK_MODE)
  if (stored !== null) return stored === 'true'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function getInitialAskPanelOpen(): boolean {
  if (typeof window === 'undefined') return false
  const stored = localStorage.getItem(STORAGE_KEY_ASK_PANEL_OPEN)
  return stored === 'true'
}

const initialState: AppState = {
  repoStatus: null,
  wikiTree: null,
  currentPage: null,
  currentJob: null,
  isLoading: true,
  error: null,
  noteEditor: {
    isOpen: false,
    isDirty: false,
    defaultScope: 'general',
    defaultTarget: '',
  },
  darkMode: getInitialDarkMode(),
  generationStatus: null,
  askPanelOpen: getInitialAskPanelOpen(),
  showUpToDateModal: false,
}

function appReducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload }
    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false }
    case 'SET_REPO_STATUS':
      return { ...state, repoStatus: action.payload }
    case 'SET_WIKI_TREE':
      return { ...state, wikiTree: action.payload }
    case 'SET_CURRENT_PAGE':
      return { ...state, currentPage: action.payload }
    case 'SET_CURRENT_JOB':
      return { ...state, currentJob: action.payload }
    case 'OPEN_NOTE_EDITOR':
      return {
        ...state,
        noteEditor: {
          ...state.noteEditor,
          isOpen: true,
          defaultScope: action.payload.scope,
          defaultTarget: action.payload.target,
        },
      }
    case 'CLOSE_NOTE_EDITOR':
      return {
        ...state,
        noteEditor: { ...state.noteEditor, isOpen: false, isDirty: false },
      }
    case 'SET_NOTE_EDITOR_DIRTY':
      return {
        ...state,
        noteEditor: { ...state.noteEditor, isDirty: action.payload },
      }
    case 'SET_DARK_MODE':
      return { ...state, darkMode: action.payload }
    case 'SET_GENERATION_STATUS':
      return { ...state, generationStatus: action.payload }
    case 'SET_ASK_PANEL_OPEN':
      return { ...state, askPanelOpen: action.payload }
    case 'SET_UP_TO_DATE_MODAL':
      return { ...state, showUpToDateModal: action.payload }
    default:
      return state
  }
}

interface AppContextValue {
  state: AppState
  dispatch: React.Dispatch<Action>
  refreshStatus: () => Promise<void>
  refreshTree: () => Promise<void>
  startGeneration: () => Promise<string | null>
  openNoteEditor: (scope?: NoteScope, target?: string) => void
  closeNoteEditor: () => void
  toggleDarkMode: () => void
  switchWorkspace: (path: string) => Promise<void>
  setNoteEditorDirty: (isDirty: boolean) => void
  dismissGenerationStatus: () => void
  setAskPanelOpen: (open: boolean) => void
  dismissUpToDateModal: () => void
}

const AppContext = createContext<AppContextValue | null>(null)

export { AppContext }

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState)

  const refreshStatus = async () => {
    try {
      const status = await api.getRepoStatus()
      dispatch({ type: 'SET_REPO_STATUS', payload: status })
    } catch {
      dispatch({ type: 'SET_ERROR', payload: 'Failed to fetch repo status' })
    }
  }

  const refreshTree = async () => {
    try {
      const tree = await api.getWikiTree()
      dispatch({ type: 'SET_WIKI_TREE', payload: tree })
    } catch {
      // Wiki tree may not exist yet, ignore error
    }
  }

  const startGeneration = async (): Promise<string | null> => {
    try {
      dispatch({ type: 'SET_LOADING', payload: true })
      // Clear any previous interrupted status when starting a new generation
      dispatch({ type: 'SET_GENERATION_STATUS', payload: null })
      const result = await api.initRepo()

      // Start polling job status
      const job = await api.getJob(result.job_id)

      // Check if job completed instantly with no changes
      if (job.status === 'completed' && job.changes_made === false) {
        dispatch({ type: 'SET_UP_TO_DATE_MODAL', payload: true })
        return null
      }

      dispatch({ type: 'SET_CURRENT_JOB', payload: job })

      return result.job_id
    } catch {
      dispatch({ type: 'SET_ERROR', payload: 'Failed to start generation' })
      return null
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false })
    }
  }

  const openNoteEditor = (scope: NoteScope = 'general', target: string = '') => {
    dispatch({ type: 'OPEN_NOTE_EDITOR', payload: { scope, target } })
  }

  const closeNoteEditor = () => {
    dispatch({ type: 'CLOSE_NOTE_EDITOR' })
  }

  const toggleDarkMode = () => {
    const newValue = !state.darkMode
    localStorage.setItem(STORAGE_KEY_DARK_MODE, String(newValue))
    dispatch({ type: 'SET_DARK_MODE', payload: newValue })
  }

  const setAskPanelOpen = (open: boolean) => {
    localStorage.setItem(STORAGE_KEY_ASK_PANEL_OPEN, String(open))
    dispatch({ type: 'SET_ASK_PANEL_OPEN', payload: open })
  }

  const switchWorkspace = async (path: string) => {
    dispatch({ type: 'SET_LOADING', payload: true })
    dispatch({ type: 'SET_ERROR', payload: null })

    try {
      const result = await api.switchWorkspace(path)
      dispatch({ type: 'SET_REPO_STATUS', payload: result.status })
      dispatch({ type: 'SET_CURRENT_PAGE', payload: null })
      await refreshTree()
    } catch (err) {
      const message = err instanceof api.ApiError ? err.message : 'Failed to switch workspace'
      dispatch({ type: 'SET_ERROR', payload: message })
      throw err
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false })
    }
  }

  const setNoteEditorDirty = (isDirty: boolean) => {
    dispatch({ type: 'SET_NOTE_EDITOR_DIRTY', payload: isDirty })
  }

  // Apply dark mode class to document
  useEffect(() => {
    if (state.darkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [state.darkMode])

  // Initial data load
  useEffect(() => {
    const init = async () => {
      dispatch({ type: 'SET_LOADING', payload: true })
      await refreshStatus()

      // Check for incomplete build FIRST
      let hasIncompleteBuild = false
      try {
        const genStatus = await api.getGenerationStatus()
        if (genStatus && genStatus.status === 'incomplete') {
          dispatch({ type: 'SET_GENERATION_STATUS', payload: genStatus })
          hasIncompleteBuild = true
          // Clear wiki tree when build is incomplete
          dispatch({
            type: 'SET_WIKI_TREE',
            payload: {
              overview: false,
              architecture: false,
              workflows: [],
              directories: [],
              files: [],
            },
          })
        }
      } catch {
        // Ignore errors when checking generation status
      }

      // Only load wiki tree if build is complete
      if (!hasIncompleteBuild) {
        await refreshTree()
      }

      // Check for any running jobs to restore generation progress after refresh
      try {
        const jobs = await api.listJobs(1)
        const runningJob = jobs.find((job) => job.status === 'running')
        if (runningJob) {
          dispatch({ type: 'SET_CURRENT_JOB', payload: runningJob })
        }
      } catch {
        // Ignore errors when checking for running jobs
      }

      dispatch({ type: 'SET_LOADING', payload: false })
    }
    init()
  }, [])

  const dismissGenerationStatus = () => {
    dispatch({ type: 'SET_GENERATION_STATUS', payload: null })
  }

  const dismissUpToDateModal = () => {
    dispatch({ type: 'SET_UP_TO_DATE_MODAL', payload: false })
  }

  const contextValue: AppContextValue = {
    state,
    dispatch,
    refreshStatus,
    refreshTree,
    startGeneration,
    openNoteEditor,
    closeNoteEditor,
    toggleDarkMode,
    switchWorkspace,
    setNoteEditorDirty,
    dismissGenerationStatus,
    setAskPanelOpen,
    dismissUpToDateModal,
  }

  return <AppContext.Provider value={contextValue}>{children}</AppContext.Provider>
}
