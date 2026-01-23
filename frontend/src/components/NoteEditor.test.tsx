import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NoteEditor } from './NoteEditor'
import { useNoteEditorStore } from '../stores'
import { initialState as noteInitial } from '../stores/noteEditorStore'

// Mock the API module
vi.mock('../api/client', () => ({
  createNote: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  useNoteEditorStore.setState(noteInitial)
})

describe('NoteEditor', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onNoteCreated: vi.fn(),
  }

  describe('dirty state tracking', () => {
    it('calls setDirty(true) when user types content', async () => {
      const user = userEvent.setup()
      render(<NoteEditor {...defaultProps} />)

      const textarea = screen.getByPlaceholderText(/describe the correction/i)
      await user.type(textarea, 'Some content')

      expect(useNoteEditorStore.getState().isDirty).toBe(true)
    })

    it('calls setDirty(false) when content is cleared', async () => {
      const user = userEvent.setup()
      render(<NoteEditor {...defaultProps} />)

      const textarea = screen.getByPlaceholderText(/describe the correction/i)

      // Type content
      await user.type(textarea, 'Some content')
      expect(useNoteEditorStore.getState().isDirty).toBe(true)

      // Clear content
      await user.clear(textarea)
      expect(useNoteEditorStore.getState().isDirty).toBe(false)
    })

    it('sets isDirty based on trimmed content', async () => {
      const user = userEvent.setup()
      render(<NoteEditor {...defaultProps} />)

      const textarea = screen.getByPlaceholderText(/describe the correction/i)

      // Type only whitespace
      await user.type(textarea, '   ')
      expect(useNoteEditorStore.getState().isDirty).toBe(false)

      // Add actual content
      await user.type(textarea, 'text')
      expect(useNoteEditorStore.getState().isDirty).toBe(true)
    })
  })

  describe('content clearing on open', () => {
    it('clears content when editor reopens', async () => {
      const user = userEvent.setup()
      const { rerender } = render(<NoteEditor {...defaultProps} isOpen={true} />)

      // Type some content
      const textarea = screen.getByPlaceholderText(/describe the correction/i)
      await user.type(textarea, 'Some content')
      expect(textarea).toHaveValue('Some content')

      // Close editor (returns null)
      rerender(<NoteEditor {...defaultProps} isOpen={false} />)
      expect(screen.queryByPlaceholderText(/describe the correction/i)).not.toBeInTheDocument()

      // Reopen editor - content should be cleared
      rerender(<NoteEditor {...defaultProps} isOpen={true} />)
      const newTextarea = screen.getByPlaceholderText(/describe the correction/i)
      expect(newTextarea).toHaveValue('')
    })

    it('clears error state when editor reopens', async () => {
      const { rerender } = render(<NoteEditor {...defaultProps} isOpen={true} />)

      // Close and reopen
      rerender(<NoteEditor {...defaultProps} isOpen={false} />)
      rerender(<NoteEditor {...defaultProps} isOpen={true} />)

      // Error message should not be present
      expect(screen.queryByText(/failed to save/i)).not.toBeInTheDocument()
    })
  })

  describe('basic rendering', () => {
    it('renders when isOpen is true', () => {
      render(<NoteEditor {...defaultProps} isOpen={true} />)

      expect(screen.getByText('Add Correction')).toBeInTheDocument()
    })

    it('does not render when isOpen is false', () => {
      render(<NoteEditor {...defaultProps} isOpen={false} />)

      expect(screen.queryByText('Add Correction')).not.toBeInTheDocument()
    })

    it('renders scope selector with all options', () => {
      render(<NoteEditor {...defaultProps} />)

      expect(screen.getByRole('button', { name: /general/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /file/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /directory/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /workflow/i })).toBeInTheDocument()
    })
  })
})
