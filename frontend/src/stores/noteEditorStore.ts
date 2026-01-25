import { create } from 'zustand'
import type { NoteScope } from '../types'

interface NoteEditorState {
  isOpen: boolean
  isDirty: boolean
  scope: NoteScope
  target: string
  existingContent: string
}

interface NoteEditorActions {
  /** Open the editor for a specific scope/target, optionally with existing content for edit mode */
  open: (scope: NoteScope, target: string, existingContent?: string) => void
  close: () => void
  setDirty: (isDirty: boolean) => void
}

export const initialState: NoteEditorState = {
  isOpen: false,
  isDirty: false,
  scope: 'general',
  target: '',
  existingContent: '',
}

export const useNoteEditorStore = create<NoteEditorState & NoteEditorActions>()((set) => ({
  ...initialState,

  open: (scope: NoteScope, target: string, existingContent = '') => {
    set({ isOpen: true, isDirty: false, scope, target, existingContent })
  },

  close: () => {
    set({ isOpen: false, isDirty: false })
  },

  setDirty: (isDirty) => set({ isDirty }),
}))
