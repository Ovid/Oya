import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { NoteEditor } from './NoteEditor'
import { useNoteEditorStore } from '../stores'
import { initialState as noteInitial } from '../stores/noteEditorStore'

// Mock the API module
vi.mock('../api/client', () => ({
  saveNote: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  useNoteEditorStore.setState(noteInitial)
})

describe('NoteEditor', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onSaved: vi.fn(),
    scope: 'file' as const,
    target: 'src/main.ts',
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

    it('tracks dirty state correctly in edit mode', async () => {
      const user = userEvent.setup()
      render(<NoteEditor {...defaultProps} existingContent="Original content" />)

      const textarea = screen.getByPlaceholderText(/describe the correction/i)
      expect(textarea).toHaveValue('Original content')

      // Typing same content should not be dirty
      await user.clear(textarea)
      await user.type(textarea, 'Original content')
      expect(useNoteEditorStore.getState().isDirty).toBe(false)

      // Typing different content should be dirty
      await user.type(textarea, ' modified')
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

    it('populates content when reopening with existingContent', async () => {
      const { rerender } = render(<NoteEditor {...defaultProps} isOpen={false} />)

      // Open with existing content
      rerender(<NoteEditor {...defaultProps} isOpen={true} existingContent="Existing note" />)
      const textarea = screen.getByPlaceholderText(/describe the correction/i)
      expect(textarea).toHaveValue('Existing note')
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

    it('renders Edit Correction title when editing', () => {
      render(<NoteEditor {...defaultProps} isOpen={true} existingContent="Some content" />)

      expect(screen.getByText('Edit Correction')).toBeInTheDocument()
    })

    it('does not render when isOpen is false', () => {
      render(<NoteEditor {...defaultProps} isOpen={false} />)

      expect(screen.queryByText('Add Correction')).not.toBeInTheDocument()
    })

    it('displays the scope label', () => {
      render(<NoteEditor {...defaultProps} scope="file" />)

      expect(screen.getByText('File')).toBeInTheDocument()
    })

    it('displays the target path', () => {
      render(<NoteEditor {...defaultProps} target="src/utils/helper.ts" />)

      expect(screen.getByText('src/utils/helper.ts')).toBeInTheDocument()
    })

    it('displays (general) for empty target', () => {
      render(<NoteEditor {...defaultProps} scope="general" target="" />)

      expect(screen.getByText('(general)')).toBeInTheDocument()
    })
  })
})
