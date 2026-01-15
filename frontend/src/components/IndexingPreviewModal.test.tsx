import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { IndexingPreviewModal } from './IndexingPreviewModal'
import * as api from '../api/client'

// Mock the API module
vi.mock('../api/client', () => ({
  getIndexableItems: vi.fn(),
  updateOyaignore: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

describe('IndexingPreviewModal', () => {
  const defaultProps = {
    isOpen: false,
    onClose: vi.fn(),
    onSave: vi.fn(),
  }

  const mockIndexableItems = {
    directories: ['src', 'src/components', 'tests'],
    files: ['README.md', 'src/index.ts', 'src/components/App.tsx'],
    total_directories: 3,
    total_files: 3,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getIndexableItems).mockResolvedValue(mockIndexableItems)
  })

  describe('modal open/close behavior', () => {
    it('does not render modal content when isOpen is false', () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={false} />)

      expect(screen.queryByText('Indexing Preview')).not.toBeInTheDocument()
    })

    it('renders modal content when isOpen is true', () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      expect(screen.getByText('Indexing Preview')).toBeInTheDocument()
    })

    it('calls onClose when close button is clicked', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      const closeButton = screen.getByLabelText('Close')
      await userEvent.click(closeButton)

      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when clicking outside the modal', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      // Click on the backdrop (the overlay div)
      const backdrop = screen.getByTestId('modal-backdrop')
      await userEvent.click(backdrop)

      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  describe('data fetching and display', () => {
    it('fetches indexable items when modal opens', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(api.getIndexableItems).toHaveBeenCalledTimes(1)
      })
    })

    it('displays directories section above files section', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('Directories')).toBeInTheDocument()
        expect(screen.getByText('Files')).toBeInTheDocument()
      })

      // Check that directories section appears before files section in the DOM
      const directoriesHeading = screen.getByText('Directories')
      const filesHeading = screen.getByText('Files')

      expect(
        directoriesHeading.compareDocumentPosition(filesHeading) & Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy()
    })

    it('displays directory items', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
        expect(screen.getByText('src/components')).toBeInTheDocument()
        expect(screen.getByText('tests')).toBeInTheDocument()
      })
    })

    it('displays file items', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('README.md')).toBeInTheDocument()
        expect(screen.getByText('src/index.ts')).toBeInTheDocument()
        expect(screen.getByText('src/components/App.tsx')).toBeInTheDocument()
      })
    })

    it('displays total counts correctly', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText(/3 directories/i)).toBeInTheDocument()
        expect(screen.getByText(/3 files/i)).toBeInTheDocument()
      })
    })

    it('shows loading state while fetching', async () => {
      // Delay the API response
      vi.mocked(api.getIndexableItems).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockIndexableItems), 100))
      )

      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      expect(screen.getByText('Loading...')).toBeInTheDocument()

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      })
    })
  })

  describe('search filtering', () => {
    it('displays search input', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
      })
    })

    it('filters directories by search query', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(/search/i)
      await userEvent.type(searchInput, 'component')

      // Only src/components should be visible
      expect(screen.queryByText('src')).not.toBeInTheDocument()
      expect(screen.getByText('src/components')).toBeInTheDocument()
      expect(screen.queryByText('tests')).not.toBeInTheDocument()
    })

    it('filters files by search query', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('README.md')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(/search/i)
      await userEvent.type(searchInput, 'index')

      // Only src/index.ts should be visible
      expect(screen.queryByText('README.md')).not.toBeInTheDocument()
      expect(screen.getByText('src/index.ts')).toBeInTheDocument()
      expect(screen.queryByText('src/components/App.tsx')).not.toBeInTheDocument()
    })

    it('performs case-insensitive filtering', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('README.md')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(/search/i)
      await userEvent.type(searchInput, 'readme')

      // README.md should still be visible (case-insensitive)
      expect(screen.getByText('README.md')).toBeInTheDocument()
    })

    it('shows all items when search is cleared', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(/search/i)
      await userEvent.type(searchInput, 'component')

      // Only src/components should be visible
      expect(screen.queryByText('src')).not.toBeInTheDocument()

      // Clear the search
      await userEvent.clear(searchInput)

      // All items should be visible again
      expect(screen.getByText('src')).toBeInTheDocument()
      expect(screen.getByText('src/components')).toBeInTheDocument()
      expect(screen.getByText('tests')).toBeInTheDocument()
    })
  })

  describe('directory exclusion', () => {
    it('displays checkbox for each directory', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Each directory should have a checkbox
      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes.length).toBeGreaterThanOrEqual(3) // At least 3 directories
    })

    it('toggles directory exclusion state when checkbox is clicked', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Find the checkbox for 'src' directory
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      expect(checkbox).toBeInTheDocument()

      // Initially unchecked
      expect(checkbox).not.toBeChecked()

      // Click to check
      await userEvent.click(checkbox!)
      expect(checkbox).toBeChecked()

      // Click to uncheck
      await userEvent.click(checkbox!)
      expect(checkbox).not.toBeChecked()
    })

    it('hides files within excluded directory', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src/index.ts')).toBeInTheDocument()
        expect(screen.getByText('src/components/App.tsx')).toBeInTheDocument()
      })

      // Find and click the checkbox for 'src' directory
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Files within 'src' should be hidden
      expect(screen.queryByText('src/index.ts')).not.toBeInTheDocument()
      expect(screen.queryByText('src/components/App.tsx')).not.toBeInTheDocument()

      // README.md should still be visible (not in src)
      expect(screen.getByText('README.md')).toBeInTheDocument()
    })

    it('restores files when directory is unchecked', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src/index.ts')).toBeInTheDocument()
      })

      // Find and click the checkbox for 'src' directory
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Files should be hidden
      expect(screen.queryByText('src/index.ts')).not.toBeInTheDocument()

      // Uncheck the directory
      await userEvent.click(checkbox!)

      // Files should be restored
      expect(screen.getByText('src/index.ts')).toBeInTheDocument()
      expect(screen.getByText('src/components/App.tsx')).toBeInTheDocument()
    })
  })

  describe('file exclusion', () => {
    it('displays checkbox for each file', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('README.md')).toBeInTheDocument()
      })

      // Each file should have a checkbox
      const fileRow = screen.getByText('README.md').closest('div')
      const checkbox = fileRow?.querySelector('input[type="checkbox"]')
      expect(checkbox).toBeInTheDocument()
    })

    it('toggles file exclusion state when checkbox is clicked', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('README.md')).toBeInTheDocument()
      })

      // Find the checkbox for 'README.md' file
      const fileRow = screen.getByText('README.md').closest('div')
      const checkbox = fileRow?.querySelector('input[type="checkbox"]')
      expect(checkbox).toBeInTheDocument()

      // Initially unchecked
      expect(checkbox).not.toBeChecked()

      // Click to check
      await userEvent.click(checkbox!)
      expect(checkbox).toBeChecked()

      // Click to uncheck
      await userEvent.click(checkbox!)
      expect(checkbox).not.toBeChecked()
    })

    it('shows visual indication when file is excluded', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('README.md')).toBeInTheDocument()
      })

      // Find and click the checkbox for 'README.md' file
      const fileRow = screen.getByText('README.md').closest('div')
      const checkbox = fileRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // File text should have strikethrough styling
      const fileText = screen.getByText('README.md')
      expect(fileText).toHaveClass('line-through')
    })

    it('clears pending file exclusions when parent directory is checked', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src/index.ts')).toBeInTheDocument()
      })

      // First, exclude a file within 'src' directory
      const fileRow = screen.getByText('src/index.ts').closest('div')
      const fileCheckbox = fileRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(fileCheckbox!)

      // File should be marked as excluded (checkbox checked)
      expect(fileCheckbox).toBeChecked()

      // Now exclude the parent directory 'src'
      const srcRow = screen.getByText('src').closest('div')
      const dirCheckbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(dirCheckbox!)

      // Uncheck the directory to restore files
      await userEvent.click(dirCheckbox!)

      // The file exclusion should have been cleared - file checkbox should be unchecked
      const restoredFileRow = screen.getByText('src/index.ts').closest('div')
      const restoredFileCheckbox = restoredFileRow?.querySelector('input[type="checkbox"]')
      expect(restoredFileCheckbox).not.toBeChecked()
    })
  })

  describe('count accuracy', () => {
    it('updates counts when directories are excluded', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText(/3 directories/i)).toBeInTheDocument()
        expect(screen.getByText(/3 files/i)).toBeInTheDocument()
      })

      // Exclude 'src' directory (which contains 2 files: src/index.ts and src/components/App.tsx)
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Counts should update: 2 directories excluded (src, src/components), 2 files hidden
      // Remaining: 1 directory (tests), 1 file (README.md)
      await waitFor(() => {
        expect(screen.getByText(/1 directory/i)).toBeInTheDocument()
        expect(screen.getByText(/1 file/i)).toBeInTheDocument()
      })
    })

    it('updates counts when files are excluded', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText(/3 files/i)).toBeInTheDocument()
      })

      // Exclude README.md file
      const fileRow = screen.getByText('README.md').closest('div')
      const checkbox = fileRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // File count should decrease by 1
      await waitFor(() => {
        expect(screen.getByText(/2 files/i)).toBeInTheDocument()
      })
    })
  })

  describe('save with confirmation', () => {
    it('shows confirmation dialog when save button is clicked with exclusions', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click save button
      const saveButton = screen.getByRole('button', { name: /save/i })
      await userEvent.click(saveButton)

      // Confirmation dialog should appear
      expect(screen.getByText(/confirm exclusions/i)).toBeInTheDocument()
    })

    it('shows summary of exclusions in confirmation dialog', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory and a file
      const srcRow = screen.getByText('src').closest('div')
      const dirCheckbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(dirCheckbox!)

      // Click save button
      const saveButton = screen.getByRole('button', { name: /save/i })
      await userEvent.click(saveButton)

      // Summary should show the exclusions in the confirmation dialog
      expect(screen.getByText('Confirm Exclusions')).toBeInTheDocument()
      // The dialog should show "1 directory" in the list
      const confirmDialog = screen.getByText('Confirm Exclusions').closest('div')
      expect(confirmDialog).toBeInTheDocument()
    })

    it('calls API and closes modal on confirm', async () => {
      const onClose = vi.fn()
      vi.mocked(api.updateOyaignore).mockResolvedValue({
        added_directories: ['src/'],
        added_files: [],
        total_added: 1,
      })

      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click save button
      const saveButton = screen.getByRole('button', { name: /save/i })
      await userEvent.click(saveButton)

      // Click confirm in dialog
      const confirmButton = screen.getByRole('button', { name: /confirm/i })
      await userEvent.click(confirmButton)

      // API should be called
      await waitFor(() => {
        expect(api.updateOyaignore).toHaveBeenCalledWith({
          directories: ['src'],
          files: [],
        })
      })

      // Modal should close
      expect(onClose).toHaveBeenCalled()
    })

    it('does not call API when cancel is clicked in confirmation', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click save button
      const saveButton = screen.getByRole('button', { name: /save/i })
      await userEvent.click(saveButton)

      // Click cancel in dialog (the second Cancel button, in the confirmation dialog)
      const cancelButtons = screen.getAllByRole('button', { name: /cancel/i })
      // The confirmation dialog's cancel button is the last one
      await userEvent.click(cancelButtons[cancelButtons.length - 1])

      // API should not be called
      expect(api.updateOyaignore).not.toHaveBeenCalled()

      // Confirmation dialog should close but modal stays open
      expect(screen.queryByText(/confirm exclusions/i)).not.toBeInTheDocument()
      expect(screen.getByText('Indexing Preview')).toBeInTheDocument()
    })
  })

  describe('cancel/discard behavior', () => {
    it('closes modal without saving when cancel button is clicked', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click cancel button (in footer, not confirmation dialog)
      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      await userEvent.click(cancelButton)

      // Modal should close
      expect(onClose).toHaveBeenCalled()

      // API should not be called
      expect(api.updateOyaignore).not.toHaveBeenCalled()
    })

    it('closes modal without saving when clicking outside', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click on backdrop
      const backdrop = screen.getByTestId('modal-backdrop')
      await userEvent.click(backdrop)

      // Modal should close
      expect(onClose).toHaveBeenCalled()

      // API should not be called
      expect(api.updateOyaignore).not.toHaveBeenCalled()
    })

    it('discards pending exclusions when modal is closed and reopened', async () => {
      const { rerender } = render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Verify it's checked
      expect(checkbox).toBeChecked()

      // Close the modal
      rerender(<IndexingPreviewModal {...defaultProps} isOpen={false} />)

      // Reopen the modal
      rerender(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // The checkbox should be unchecked (exclusions discarded)
      const newSrcRow = screen.getByText('src').closest('div')
      const newCheckbox = newSrcRow?.querySelector('input[type="checkbox"]')
      expect(newCheckbox).not.toBeChecked()
    })
  })
})
