import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../api/client', () => ({
  getLogs: vi.fn(),
  deleteLogs: vi.fn(),
}))

import { LogViewerModal } from './LogViewerModal'
import * as api from '../api/client'

beforeEach(() => {
  vi.clearAllMocks()
})

const mockLogsResponse = {
  content:
    '{"timestamp":"2024-01-01","model":"gpt-4","prompt":"test"}\n{"timestamp":"2024-01-02","model":"gpt-4","prompt":"test2"}\n',
  size_bytes: 100,
  entry_count: 2,
}

describe('LogViewerModal', () => {
  it('does not render when isOpen is false', () => {
    render(<LogViewerModal isOpen={false} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    expect(screen.queryByText('LLM Logs')).not.toBeInTheDocument()
  })

  it('renders modal when isOpen is true', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/LLM Logs/)).toBeInTheDocument()
    })
  })

  it('displays entry count after loading', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })
  })

  it('shows empty state when no logs exist', async () => {
    vi.mocked(api.getLogs).mockRejectedValue({ status: 404 })

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/No LLM logs yet/)).toBeInTheDocument()
    })
  })

  it('navigates to next entry when Next button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    expect(screen.getByText(/Entry 2 of 2/)).toBeInTheDocument()
  })

  it('navigates to previous entry when Prev button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Go to entry 2
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText(/Entry 2 of 2/)).toBeInTheDocument()

    // Go back to entry 1
    await userEvent.click(screen.getByRole('button', { name: /previous/i }))
    expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
  })

  it('navigates to first entry when First button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Go to entry 2
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText(/Entry 2 of 2/)).toBeInTheDocument()

    // Go to first
    await userEvent.click(screen.getByRole('button', { name: /first/i }))
    expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
  })

  it('navigates to last entry when Last button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Go to last
    await userEvent.click(screen.getByRole('button', { name: /last/i }))
    expect(screen.getByText(/Entry 2 of 2/)).toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)
    const onClose = vi.fn()

    render(<LogViewerModal isOpen={true} onClose={onClose} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/LLM Logs/)).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /close/i }))

    expect(onClose).toHaveBeenCalled()
  })

  it('shows delete confirmation when delete button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /delete/i }))

    expect(screen.getByText(/Delete all LLM logs/)).toBeInTheDocument()
  })

  it('hides delete confirmation when cancel is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Show delete confirmation
    await userEvent.click(screen.getByRole('button', { name: /delete/i }))
    expect(screen.getByText(/Delete all LLM logs/)).toBeInTheDocument()

    // Cancel
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(screen.queryByText(/Delete all LLM logs/)).not.toBeInTheDocument()
  })

  it('deletes logs when confirmed', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)
    vi.mocked(api.deleteLogs).mockResolvedValue({ message: 'Logs deleted' })

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Click delete button
    await userEvent.click(screen.getByRole('button', { name: /delete/i }))

    // Confirm deletion
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))

    await waitFor(() => {
      expect(api.deleteLogs).toHaveBeenCalledWith(1)
    })
  })

  it('shows empty state after successful deletion', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)
    vi.mocked(api.deleteLogs).mockResolvedValue({ message: 'Logs deleted' })

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Delete logs
    await userEvent.click(screen.getByRole('button', { name: /delete/i }))
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))

    // Should show empty state
    await waitFor(() => {
      expect(screen.getByText(/No LLM logs yet/)).toBeInTheDocument()
    })
  })

  it('shows error state with retry option when loading fails', async () => {
    vi.mocked(api.getLogs).mockRejectedValue(new Error('Network error'))

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Network error/)).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('retries loading when retry button is clicked', async () => {
    vi.mocked(api.getLogs)
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Network error/)).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /retry/i }))

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    expect(api.getLogs).toHaveBeenCalledTimes(2)
  })

  it('displays repo name in the modal', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(
      <LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="My Test Repository" />
    )

    await waitFor(() => {
      expect(screen.getByText('My Test Repository')).toBeInTheDocument()
    })
  })

  it('shows loading state while fetching logs', async () => {
    let resolvePromise: (value: typeof mockLogsResponse) => void
    vi.mocked(api.getLogs).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePromise = resolve
        })
    )

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    // Should show loading indicator
    expect(screen.getByText(/LLM Logs/)).toBeInTheDocument()

    // Resolve the promise
    resolvePromise!(mockLogsResponse)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })
  })

  it('calls onClose when backdrop is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)
    const onClose = vi.fn()

    render(<LogViewerModal isOpen={true} onClose={onClose} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/LLM Logs/)).toBeInTheDocument()
    })

    // Click backdrop
    const backdrop = screen.getByTestId('modal-backdrop')
    await userEvent.click(backdrop)

    expect(onClose).toHaveBeenCalled()
  })

  it('searches and finds matching entries', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Type search term
    const searchInput = screen.getByPlaceholderText(/search/i)
    await userEvent.type(searchInput, 'test2')

    // Click find
    await userEvent.click(screen.getByRole('button', { name: /find/i }))

    // Should navigate to entry 2 which contains "test2"
    expect(screen.getByText(/Entry 2 of 2/)).toBeInTheDocument()
  })

  it('wraps around when searching', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Go to last entry
    await userEvent.click(screen.getByRole('button', { name: /last/i }))
    expect(screen.getByText(/Entry 2 of 2/)).toBeInTheDocument()

    // Search for something in entry 1
    const searchInput = screen.getByPlaceholderText(/search/i)
    await userEvent.type(searchInput, '2024-01-01')
    await userEvent.click(screen.getByRole('button', { name: /find/i }))

    // Should wrap around to entry 1
    expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
  })

  it('disables Prev and First buttons on first entry', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: /first/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /previous/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /next/i })).not.toBeDisabled()
    expect(screen.getByRole('button', { name: /last/i })).not.toBeDisabled()
  })

  it('disables Next and Last buttons on last entry', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Go to last entry
    await userEvent.click(screen.getByRole('button', { name: /last/i }))

    expect(screen.getByRole('button', { name: /first/i })).not.toBeDisabled()
    expect(screen.getByRole('button', { name: /previous/i })).not.toBeDisabled()
    expect(screen.getByRole('button', { name: /next/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /last/i })).toBeDisabled()
  })

  it('resets state when modal is closed and reopened', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    const { rerender } = render(
      <LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />
    )

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Go to entry 2
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByText(/Entry 2 of 2/)).toBeInTheDocument()

    // Close the modal
    rerender(<LogViewerModal isOpen={false} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    // Reopen the modal
    rerender(<LogViewerModal isOpen={true} onClose={vi.fn()} repoId={1} repoName="Test Repo" />)

    // Should be back to entry 1
    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })
  })
})
