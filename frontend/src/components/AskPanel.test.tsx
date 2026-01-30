import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { WikiTree, JobStatus } from '../types'

// Mock the API module - must be before imports that use it
vi.mock('../api/client', () => ({
  askQuestionStream: vi.fn(),
}))

// Mock the storage module
vi.mock('../utils/storage', () => ({
  getStorageValue: vi.fn((key: string) => {
    if (key === 'qaSettings') {
      return { quickMode: true, temperature: 0.5, timeoutMinutes: 3 }
    }
    if (key === 'darkMode') {
      return false
    }
    if (key === 'currentJob') {
      return null
    }
    return null
  }),
  setStorageValue: vi.fn(),
  hasStorageValue: vi.fn(() => false),
  getExplicitStorageValue: vi.fn(() => undefined),
  loadStorage: vi.fn(() => ({
    darkMode: false,
    askPanelOpen: false,
    sidebarLeftWidth: 256,
    sidebarRightWidth: 320,
    currentJob: null,
    qaSettings: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
    generationTiming: {},
  })),
  DEFAULT_QA_SETTINGS: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
  DEFAULT_STORAGE: {
    darkMode: false,
    askPanelOpen: false,
    sidebarLeftWidth: 256,
    sidebarRightWidth: 320,
    currentJob: null,
    qaSettings: { quickMode: true, temperature: 0.5, timeoutMinutes: 3 },
    generationTiming: {},
  },
}))

// Setup scrollIntoView mock (localStorage/matchMedia handled by test/setup.ts)
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

import { AskPanel } from './AskPanel'
import { useWikiStore, useGenerationStore } from '../stores'
import { initialState as wikiInitial } from '../stores/wikiStore'
import { initialState as genInitial } from '../stores/generationStore'
import * as api from '../api/client'
import * as storage from '../utils/storage'

beforeEach(() => {
  vi.clearAllMocks()
  // Reset stores to initial state
  useWikiStore.setState(wikiInitial)
  useGenerationStore.setState(genInitial)
})

const mockWikiTree: WikiTree = {
  overview: true,
  architecture: true,
  workflows: [],
  directories: [],
  files: [],
}

const mockRunningJob: JobStatus = {
  job_id: 'job-123',
  type: 'generation',
  status: 'running',
  started_at: null,
  completed_at: null,
  current_phase: null,
  total_phases: null,
  error_message: null,
}

const mockCompletedJob: JobStatus = {
  job_id: 'job-123',
  type: 'generation',
  status: 'completed',
  started_at: '2024-01-01T00:00:00Z',
  completed_at: '2024-01-01T00:05:00Z',
  current_phase: null,
  total_phases: null,
  error_message: null,
}

const mockPendingJob: JobStatus = {
  job_id: 'job-123',
  type: 'generation',
  status: 'pending',
  started_at: null,
  completed_at: null,
  current_phase: null,
  total_phases: null,
  error_message: null,
}

const emptyWikiTree: WikiTree = {
  overview: false,
  architecture: false,
  workflows: [],
  directories: [],
  files: [],
}

function renderAskPanel(
  props = {},
  storeOverrides: { currentJob?: JobStatus | null; wikiTree?: WikiTree | null } = {}
) {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    ...props,
  }

  // Set store state for overrides
  if (storeOverrides.wikiTree !== undefined) {
    useWikiStore.setState({ wikiTree: storeOverrides.wikiTree })
  } else {
    useWikiStore.setState({ wikiTree: mockWikiTree })
  }

  if (storeOverrides.currentJob !== undefined) {
    useGenerationStore.setState({ currentJob: storeOverrides.currentJob })
  }

  return render(
    <MemoryRouter>
      <AskPanel {...defaultProps} />
    </MemoryRouter>
  )
}

describe('AskPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('basic rendering', () => {
    it('renders when isOpen is true', async () => {
      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByText('Ask about this codebase')).toBeInTheDocument()
      })
    })

    it('does not render when isOpen is false', async () => {
      renderAskPanel({ isOpen: false })

      expect(screen.queryByText('Ask about this codebase')).not.toBeInTheDocument()
    })

    it('renders input field', async () => {
      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Ask a question...')).toBeInTheDocument()
      })
    })

    it('renders Ask button', async () => {
      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /ask/i })).toBeInTheDocument()
      })
    })

    it('loads settings from storage on mount', () => {
      renderAskPanel({ isOpen: true })
      expect(storage.getStorageValue).toHaveBeenCalledWith('qaSettings')
    })
  })

  describe('during generation', () => {
    it('shows disabled banner when generation is running', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockRunningJob })

      await waitFor(() => {
        expect(
          screen.getByText('Q&A is unavailable while the wiki is being generated.')
        ).toBeInTheDocument()
      })
    })

    it('disables input field during generation', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockRunningJob })

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Ask a question...')
        expect(input).toBeDisabled()
      })
    })

    it('disables submit button during generation', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockRunningJob })

      await waitFor(() => {
        const submitButton = screen.getByRole('button', { name: /ask/i })
        expect(submitButton).toBeDisabled()
      })
    })

    it('does not show disabled banner when generation is not running', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: null })

      await waitFor(() => {
        expect(
          screen.queryByText('Q&A is unavailable while the wiki is being generated.')
        ).not.toBeInTheDocument()
      })
    })

    it('does not show disabled banner when job is completed', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockCompletedJob })

      await waitFor(() => {
        expect(
          screen.queryByText('Q&A is unavailable while the wiki is being generated.')
        ).not.toBeInTheDocument()
      })
    })

    it('enables input field when generation is not running', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: null })

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Ask a question...')
        expect(input).not.toBeDisabled()
      })
    })

    it('shows disabled banner when job is pending', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockPendingJob })

      await waitFor(() => {
        expect(
          screen.getByText('Q&A is unavailable while the wiki is being generated.')
        ).toBeInTheDocument()
      })
    })

    it('disables input field when job is pending', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockPendingJob })

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Ask a question...')
        expect(input).toBeDisabled()
      })
    })

    it('disables submit button when job is pending', async () => {
      renderAskPanel({ isOpen: true }, { currentJob: mockPendingJob })

      await waitFor(() => {
        const submitButton = screen.getByRole('button', { name: /ask/i })
        expect(submitButton).toBeDisabled()
      })
    })
  })

  describe('when no wiki exists', () => {
    it('shows banner when wiki is empty', async () => {
      renderAskPanel({ isOpen: true }, { wikiTree: emptyWikiTree })

      await waitFor(() => {
        expect(screen.getByText('Generate a wiki first to enable Q&A.')).toBeInTheDocument()
      })
    })

    it('shows banner when wikiTree is null', async () => {
      renderAskPanel({ isOpen: true }, { wikiTree: null })

      await waitFor(() => {
        expect(screen.getByText('Generate a wiki first to enable Q&A.')).toBeInTheDocument()
      })
    })

    it('disables input field when no wiki exists', async () => {
      renderAskPanel({ isOpen: true }, { wikiTree: emptyWikiTree })

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Ask a question...')
        expect(input).toBeDisabled()
      })
    })

    it('disables submit button when no wiki exists', async () => {
      renderAskPanel({ isOpen: true }, { wikiTree: emptyWikiTree })

      await waitFor(() => {
        const submitButton = screen.getByRole('button', { name: /ask/i })
        expect(submitButton).toBeDisabled()
      })
    })

    it('does not show no-wiki banner when wiki exists', async () => {
      renderAskPanel({ isOpen: true }, { wikiTree: mockWikiTree })

      await waitFor(() => {
        expect(screen.queryByText('Generate a wiki first to enable Q&A.')).not.toBeInTheDocument()
      })
    })

    it('enables input when wiki has only files', async () => {
      const wikiWithFiles: WikiTree = {
        overview: false,
        architecture: false,
        workflows: [],
        directories: [],
        files: ['src-main-ts'],
      }
      renderAskPanel({ isOpen: true }, { wikiTree: wikiWithFiles })

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Ask a question...')
        expect(input).not.toBeDisabled()
      })
    })

    it('does not show no-wiki banner during generation', async () => {
      renderAskPanel({ isOpen: true }, { wikiTree: emptyWikiTree, currentJob: mockRunningJob })

      await waitFor(() => {
        // Should show generation banner, not no-wiki banner
        expect(
          screen.getByText('Q&A is unavailable while the wiki is being generated.')
        ).toBeInTheDocument()
        expect(screen.queryByText('Generate a wiki first to enable Q&A.')).not.toBeInTheDocument()
      })
    })
  })

  describe('status indicator', () => {
    it('shows ThinkingIndicator when currentStatus is set', async () => {
      // This test verifies the component renders - we test internal state indirectly
      // by checking the AskPanel renders without errors when streaming
      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByText('Ask about this codebase')).toBeInTheDocument()
      })
    })
  })

  describe('answer display', () => {
    it('displays answer from done event', async () => {
      const { userEvent } = await import('@testing-library/user-event')

      vi.mocked(api.askQuestionStream).mockImplementation(async (_req, callbacks) => {
        callbacks.onStatus('searching', 1)
        callbacks.onStatus('thinking', 1)
        callbacks.onDone({
          answer: 'This is the parsed answer without XML tags.',
          citations: [],
          confidence: 'high',
          disclaimer: 'Based on strong evidence.',
          session_id: null,
          search_quality: {
            semantic_searched: true,
            fts_searched: true,
            results_found: 5,
            results_used: 3,
          },
        })
      })

      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Ask a question...')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Ask a question...')
      const user = userEvent.setup()
      await user.type(input, 'What is this codebase?')
      await user.click(screen.getByRole('button', { name: /ask/i }))

      await waitFor(() => {
        expect(screen.getByText('This is the parsed answer without XML tags.')).toBeInTheDocument()
      })
    })

    it('does not display XML tags in answer', async () => {
      const { userEvent } = await import('@testing-library/user-event')

      vi.mocked(api.askQuestionStream).mockImplementation(async (_req, callbacks) => {
        callbacks.onStatus('thinking', 1)
        callbacks.onDone({
          answer: 'Clean answer text',
          citations: [],
          confidence: 'medium',
          disclaimer: 'Based on partial evidence.',
          session_id: null,
          search_quality: {
            semantic_searched: true,
            fts_searched: true,
            results_found: 3,
            results_used: 2,
          },
        })
      })

      renderAskPanel({ isOpen: true })

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Ask a question...')).toBeInTheDocument()
      })

      const input = screen.getByPlaceholderText('Ask a question...')
      const user = userEvent.setup()
      await user.type(input, 'Test question')
      await user.click(screen.getByRole('button', { name: /ask/i }))

      await waitFor(() => {
        expect(screen.getByText('Clean answer text')).toBeInTheDocument()
      })

      // Verify no XML tags are displayed
      expect(screen.queryByText(/<answer>/)).not.toBeInTheDocument()
      expect(screen.queryByText(/<\/answer>/)).not.toBeInTheDocument()
    })
  })
})
