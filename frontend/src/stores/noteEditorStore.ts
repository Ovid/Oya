import { create } from 'zustand'
import type { NoteScope } from '../types'

interface NoteEditorState {
  isOpen: boolean
  isDirty: boolean
  defaultScope: NoteScope
  defaultTarget: string
}

interface NoteEditorActions {
  open: (scope?: NoteScope, target?: string) => void
  close: () => void
  setDirty: (isDirty: boolean) => void
}

export const initialState: NoteEditorState = {
  isOpen: false,
  isDirty: false,
  defaultScope: 'general',
  defaultTarget: '',
}

export const useNoteEditorStore = create<NoteEditorState & NoteEditorActions>()((set) => ({
  ...initialState,

  open: (scope = 'general', target = '') => {
    set({ isOpen: true, defaultScope: scope, defaultTarget: target })
  },

  close: () => {
    set({ isOpen: false, isDirty: false })
  },

  setDirty: (isDirty) => set({ isDirty }),
}))
