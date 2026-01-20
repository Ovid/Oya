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
    onGenerate: vi.fn(),
  }

  // New mock data structure with three categories
  const mockIndexableItems = {
    included: {
      directories: ['src', 'src/components', 'tests'],
      files: ['README.md', 'src/index.ts', 'src/components/App.tsx'],
    },
    excluded_by_oyaignore: {
      directories: ['node_modules'],
      files: ['secret.env'],
    },
    excluded_by_rule: {
      directories: ['.git'],
      files: ['package-lock.json'],
    },
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

    it('calls onClose when close button is clicked with no changes', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      const closeButton = screen.getByLabelText('Close')
      await userEvent.click(closeButton)

      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when clicking outside the modal with no changes', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

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

    it('displays included directory items', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
        expect(screen.getByText('src/components')).toBeInTheDocument()
        expect(screen.getByText('tests')).toBeInTheDocument()
      })
    })

    it('displays included file items', async () => {
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

  describe('three display states', () => {
    it('shows included files as checked by default', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Find the checkbox for 'src' directory - should be checked (included)
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      expect(checkbox).toBeChecked()
    })

    it('shows oyaignore files as unchecked with badge', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('Excluded by .oyaignore')).toBeInTheDocument()
      })

      // Check for node_modules (excluded by oyaignore)
      expect(screen.getByText('node_modules')).toBeInTheDocument()
      expect(screen.getByText('secret.env')).toBeInTheDocument()

      // Find the checkbox for 'node_modules' - should be unchecked
      const nodeModulesRow = screen.getByText('node_modules').closest('div')
      const checkbox = nodeModulesRow?.querySelector('input[type="checkbox"]')
      expect(checkbox).not.toBeChecked()
      expect(checkbox).not.toBeDisabled()

      // Check for "(from .oyaignore)" badge
      const badges = screen.getAllByText('(from .oyaignore)')
      expect(badges.length).toBeGreaterThan(0)
    })

    it('shows rule-excluded files as disabled with badge', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('Excluded by Rules')).toBeInTheDocument()
      })

      // Check for .git (excluded by rule)
      expect(screen.getByText('.git')).toBeInTheDocument()
      expect(screen.getByText('package-lock.json')).toBeInTheDocument()

      // Find the checkbox for '.git' - should be disabled
      const gitRow = screen.getByText('.git').closest('div')
      const checkbox = gitRow?.querySelector('input[type="checkbox"]')
      expect(checkbox).not.toBeChecked()
      expect(checkbox).toBeDisabled()

      // Check for "(excluded by rule)" badge
      const badges = screen.getAllByText('(excluded by rule)')
      expect(badges.length).toBeGreaterThan(0)
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

  describe('directory exclusion (inverted checkbox)', () => {
    it('displays checkbox for each directory', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Each directory should have a checkbox
      const checkboxes = screen.getAllByRole('checkbox')
      expect(checkboxes.length).toBeGreaterThanOrEqual(3) // At least 3 included directories
    })

    it('unchecking an included directory adds to pendingExclusions', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Find the checkbox for 'src' directory
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      expect(checkbox).toBeInTheDocument()

      // Initially checked (included)
      expect(checkbox).toBeChecked()

      // Click to uncheck (exclude)
      await userEvent.click(checkbox!)
      expect(checkbox).not.toBeChecked()

      // Click to check again (include)
      await userEvent.click(checkbox!)
      expect(checkbox).toBeChecked()
    })

    it('hides files within excluded directory', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src/index.ts')).toBeInTheDocument()
        expect(screen.getByText('src/components/App.tsx')).toBeInTheDocument()
      })

      // Find and click the checkbox for 'src' directory to uncheck (exclude)
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Files within 'src' should be hidden
      expect(screen.queryByText('src/index.ts')).not.toBeInTheDocument()
      expect(screen.queryByText('src/components/App.tsx')).not.toBeInTheDocument()

      // README.md should still be visible (not in src)
      expect(screen.getByText('README.md')).toBeInTheDocument()
    })

    it('restores files when directory is re-checked', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src/index.ts')).toBeInTheDocument()
      })

      // Find and click the checkbox for 'src' directory to uncheck (exclude)
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Files should be hidden
      expect(screen.queryByText('src/index.ts')).not.toBeInTheDocument()

      // Check the directory again (re-include)
      await userEvent.click(checkbox!)

      // Files should be restored
      expect(screen.getByText('src/index.ts')).toBeInTheDocument()
      expect(screen.getByText('src/components/App.tsx')).toBeInTheDocument()
    })
  })

  describe('file exclusion (inverted checkbox)', () => {
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

    it('unchecking an included file adds to pendingExclusions', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('README.md')).toBeInTheDocument()
      })

      // Find the checkbox for 'README.md' file
      const fileRow = screen.getByText('README.md').closest('div')
      const checkbox = fileRow?.querySelector('input[type="checkbox"]')
      expect(checkbox).toBeInTheDocument()

      // Initially checked (included)
      expect(checkbox).toBeChecked()

      // Click to uncheck (exclude)
      await userEvent.click(checkbox!)
      expect(checkbox).not.toBeChecked()

      // Click to check again (include)
      await userEvent.click(checkbox!)
      expect(checkbox).toBeChecked()
    })

    it('shows visual indication when file is excluded', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('README.md')).toBeInTheDocument()
      })

      // Find and click the checkbox for 'README.md' file to uncheck (exclude)
      const fileRow = screen.getByText('README.md').closest('div')
      const checkbox = fileRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // File text should have strikethrough styling
      const fileText = screen.getByText('README.md')
      expect(fileText).toHaveClass('line-through')
    })

    it('clears pending file exclusions when parent directory is unchecked', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src/index.ts')).toBeInTheDocument()
      })

      // First, exclude a file within 'src' directory (uncheck it)
      const fileRow = screen.getByText('src/index.ts').closest('div')
      const fileCheckbox = fileRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(fileCheckbox!)

      // File should be marked as excluded (checkbox unchecked)
      expect(fileCheckbox).not.toBeChecked()

      // Now exclude the parent directory 'src' (uncheck it)
      const srcRow = screen.getByText('src').closest('div')
      const dirCheckbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(dirCheckbox!)

      // Re-check the directory to restore files
      await userEvent.click(dirCheckbox!)

      // The file exclusion should have been cleared - file checkbox should be checked
      const restoredFileRow = screen.getByText('src/index.ts').closest('div')
      const restoredFileCheckbox = restoredFileRow?.querySelector('input[type="checkbox"]')
      expect(restoredFileCheckbox).toBeChecked()
    })
  })

  describe('oyaignore re-inclusion', () => {
    it('checking an oyaignore item adds to pendingInclusions', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('node_modules')).toBeInTheDocument()
      })

      // Find the checkbox for 'node_modules' (oyaignore item)
      const nodeModulesRow = screen.getByText('node_modules').closest('div')
      const checkbox = nodeModulesRow?.querySelector('input[type="checkbox"]')
      expect(checkbox).toBeInTheDocument()

      // Initially unchecked (excluded by oyaignore)
      expect(checkbox).not.toBeChecked()

      // Click to check (re-include)
      await userEvent.click(checkbox!)
      expect(checkbox).toBeChecked()

      // Click to uncheck again (keep excluded)
      await userEvent.click(checkbox!)
      expect(checkbox).not.toBeChecked()
    })

    it('updates counts when oyaignore items are re-included', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText(/3 directories/i)).toBeInTheDocument()
        expect(screen.getByText(/3 files/i)).toBeInTheDocument()
      })

      // Re-include node_modules (check the checkbox)
      const nodeModulesRow = screen.getByText('node_modules').closest('div')
      const dirCheckbox = nodeModulesRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(dirCheckbox!)

      // Directory count should increase by 1
      await waitFor(() => {
        expect(screen.getByText(/4 directories/i)).toBeInTheDocument()
      })

      // Re-include secret.env
      const secretEnvRow = screen.getByText('secret.env').closest('div')
      const fileCheckbox = secretEnvRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(fileCheckbox!)

      // File count should increase by 1
      await waitFor(() => {
        expect(screen.getByText(/4 files/i)).toBeInTheDocument()
      })
    })
  })

  describe('count accuracy', () => {
    it('updates counts when directories are excluded', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText(/3 directories/i)).toBeInTheDocument()
        expect(screen.getByText(/3 files/i)).toBeInTheDocument()
      })

      // Exclude 'src' directory by unchecking (which contains 2 files: src/index.ts and src/components/App.tsx)
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

      // Exclude README.md file by unchecking
      const fileRow = screen.getByText('README.md').closest('div')
      const checkbox = fileRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // File count should decrease by 1
      await waitFor(() => {
        expect(screen.getByText(/2 files/i)).toBeInTheDocument()
      })
    })
  })

  describe('generate wiki with confirmation', () => {
    it('shows confirmation dialog when Generate Wiki button is clicked', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Click Generate Wiki button
      const generateButton = screen.getByRole('button', { name: /generate wiki/i })
      await userEvent.click(generateButton)

      // Confirmation dialog should appear (dialog title as h3)
      expect(screen.getByRole('heading', { name: 'Generate Wiki' })).toBeInTheDocument()
    })

    it('shows summary of files to be indexed in confirmation dialog', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Click Generate Wiki button
      const generateButton = screen.getByRole('button', { name: /generate wiki/i })
      await userEvent.click(generateButton)

      // Summary should show the file count
      expect(screen.getByText(/3 files will be indexed/i)).toBeInTheDocument()
    })

    it('shows oyaignore update note when there are changes', async () => {
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory by unchecking
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click Generate Wiki button
      const generateButton = screen.getByRole('button', { name: /generate wiki/i })
      await userEvent.click(generateButton)

      // Should show oyaignore update note
      expect(screen.getByText(/\.oyaignore will be updated/i)).toBeInTheDocument()
    })

    it('calls onGenerate and onClose on confirm without changes', async () => {
      const onClose = vi.fn()
      const onGenerate = vi.fn()

      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} onGenerate={onGenerate} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Click Generate Wiki button
      const generateButton = screen.getByRole('button', { name: /generate wiki/i })
      await userEvent.click(generateButton)

      // Click Generate in dialog
      const confirmButton = screen.getByRole('button', { name: /^generate$/i })
      await userEvent.click(confirmButton)

      // onGenerate should be called
      await waitFor(() => {
        expect(onGenerate).toHaveBeenCalled()
      })

      // Modal should close
      expect(onClose).toHaveBeenCalled()

      // API should NOT be called when no changes
      expect(api.updateOyaignore).not.toHaveBeenCalled()
    })

    it('calls API with changes, onGenerate, and onClose on confirm', async () => {
      const onClose = vi.fn()
      const onGenerate = vi.fn()
      vi.mocked(api.updateOyaignore).mockResolvedValue({
        added_directories: ['src/'],
        added_files: [],
        removed: [],
        total_added: 1,
        total_removed: 0,
      })

      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} onGenerate={onGenerate} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory by unchecking
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click Generate Wiki button
      const generateButton = screen.getByRole('button', { name: /generate wiki/i })
      await userEvent.click(generateButton)

      // Click Generate in dialog
      const confirmButton = screen.getByRole('button', { name: /^generate$/i })
      await userEvent.click(confirmButton)

      // API should be called with correct structure
      await waitFor(() => {
        expect(api.updateOyaignore).toHaveBeenCalledWith({
          directories: ['src'],
          files: [],
          removals: [],
        })
      })

      // onGenerate should be called
      expect(onGenerate).toHaveBeenCalled()

      // Modal should close
      expect(onClose).toHaveBeenCalled()
    })

    it('includes removals when re-including oyaignore items', async () => {
      const onClose = vi.fn()
      const onGenerate = vi.fn()
      vi.mocked(api.updateOyaignore).mockResolvedValue({
        added_directories: [],
        added_files: [],
        removed: ['node_modules'],
        total_added: 0,
        total_removed: 1,
      })

      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} onGenerate={onGenerate} />)

      await waitFor(() => {
        expect(screen.getByText('node_modules')).toBeInTheDocument()
      })

      // Re-include node_modules by checking
      const nodeModulesRow = screen.getByText('node_modules').closest('div')
      const checkbox = nodeModulesRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click Generate Wiki button
      const generateButton = screen.getByRole('button', { name: /generate wiki/i })
      await userEvent.click(generateButton)

      // Click Generate in dialog
      const confirmButton = screen.getByRole('button', { name: /^generate$/i })
      await userEvent.click(confirmButton)

      // API should be called with removals
      await waitFor(() => {
        expect(api.updateOyaignore).toHaveBeenCalledWith({
          directories: [],
          files: [],
          removals: ['node_modules'],
        })
      })

      // onGenerate should be called
      expect(onGenerate).toHaveBeenCalled()
    })

    it('does not call API or onGenerate when cancel is clicked in confirmation', async () => {
      const onGenerate = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onGenerate={onGenerate} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Click Generate Wiki button
      const generateButton = screen.getByRole('button', { name: /generate wiki/i })
      await userEvent.click(generateButton)

      // Click Cancel in dialog
      const cancelButtons = screen.getAllByRole('button', { name: /cancel/i })
      // The confirmation dialog's cancel button is the last one
      await userEvent.click(cancelButtons[cancelButtons.length - 1])

      // API should not be called
      expect(api.updateOyaignore).not.toHaveBeenCalled()

      // onGenerate should not be called
      expect(onGenerate).not.toHaveBeenCalled()

      // Confirmation dialog should close but modal stays open
      // The dialog title should be gone (but Generate Wiki button still exists)
      expect(screen.queryByRole('heading', { name: 'Generate Wiki' })).not.toBeInTheDocument()
      expect(screen.getByText('Indexing Preview')).toBeInTheDocument()
    })
  })

  describe('unsaved changes warning', () => {
    it('shows unsaved warning when closing with pending changes', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory by unchecking
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click cancel button (in footer)
      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      await userEvent.click(cancelButton)

      // Unsaved changes warning should appear
      expect(screen.getByText('Unsaved Changes')).toBeInTheDocument()
      expect(screen.getByText(/exclusion changes that haven't been saved/i)).toBeInTheDocument()

      // Modal should not close yet
      expect(onClose).not.toHaveBeenCalled()
    })

    it('closes modal when discarding changes in warning dialog', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory by unchecking
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click cancel button (in footer)
      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      await userEvent.click(cancelButton)

      // Click Discard Changes in warning dialog
      const discardButton = screen.getByRole('button', { name: /discard changes/i })
      await userEvent.click(discardButton)

      // Modal should close
      expect(onClose).toHaveBeenCalled()

      // API should not be called
      expect(api.updateOyaignore).not.toHaveBeenCalled()
    })

    it('keeps modal open when choosing Keep Editing in warning dialog', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory by unchecking
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click cancel button (in footer)
      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      await userEvent.click(cancelButton)

      // Click Keep Editing in warning dialog
      const keepEditingButton = screen.getByRole('button', { name: /keep editing/i })
      await userEvent.click(keepEditingButton)

      // Warning dialog should close
      expect(screen.queryByText('Unsaved Changes')).not.toBeInTheDocument()

      // Modal should stay open
      expect(onClose).not.toHaveBeenCalled()
      expect(screen.getByText('Indexing Preview')).toBeInTheDocument()
    })

    it('shows unsaved warning when clicking outside with pending changes', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory by unchecking
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click on backdrop
      const backdrop = screen.getByTestId('modal-backdrop')
      await userEvent.click(backdrop)

      // Unsaved changes warning should appear
      expect(screen.getByText('Unsaved Changes')).toBeInTheDocument()

      // Modal should not close yet
      expect(onClose).not.toHaveBeenCalled()
    })

    it('shows unsaved warning when clicking close button with pending changes', async () => {
      const onClose = vi.fn()
      render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory by unchecking
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Click close button (X button in header)
      const closeButton = screen.getByLabelText('Close')
      await userEvent.click(closeButton)

      // Unsaved changes warning should appear
      expect(screen.getByText('Unsaved Changes')).toBeInTheDocument()

      // Modal should not close yet
      expect(onClose).not.toHaveBeenCalled()
    })

    it('discards pending changes when modal is closed and reopened', async () => {
      const onClose = vi.fn()
      const { rerender } = render(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // Exclude a directory by unchecking
      const srcRow = screen.getByText('src').closest('div')
      const checkbox = srcRow?.querySelector('input[type="checkbox"]')
      await userEvent.click(checkbox!)

      // Verify it's unchecked (excluded)
      expect(checkbox).not.toBeChecked()

      // Close the modal (simulating actual close after discard)
      rerender(<IndexingPreviewModal {...defaultProps} isOpen={false} onClose={onClose} />)

      // Reopen the modal
      rerender(<IndexingPreviewModal {...defaultProps} isOpen={true} onClose={onClose} />)

      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })

      // The checkbox should be checked (changes discarded, back to included)
      const newSrcRow = screen.getByText('src').closest('div')
      const newCheckbox = newSrcRow?.querySelector('input[type="checkbox"]')
      expect(newCheckbox).toBeChecked()
    })
  })
})
