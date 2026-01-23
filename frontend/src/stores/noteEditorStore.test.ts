import { describe, it, expect, beforeEach } from 'vitest'
import { useNoteEditorStore, initialState } from './noteEditorStore'

beforeEach(() => {
  useNoteEditorStore.setState(initialState)
})

describe('noteEditorStore', () => {
  describe('initial state', () => {
    it('has correct initial values', () => {
      const state = useNoteEditorStore.getState()
      expect(state.isOpen).toBe(false)
      expect(state.isDirty).toBe(false)
      expect(state.defaultScope).toBe('general')
      expect(state.defaultTarget).toBe('')
    })
  })

  describe('open', () => {
    it('opens editor with default values', () => {
      useNoteEditorStore.getState().open()

      const state = useNoteEditorStore.getState()
      expect(state.isOpen).toBe(true)
      expect(state.defaultScope).toBe('general')
      expect(state.defaultTarget).toBe('')
    })

    it('opens editor with specified scope and target', () => {
      useNoteEditorStore.getState().open('file', '/src/main.ts')

      const state = useNoteEditorStore.getState()
      expect(state.isOpen).toBe(true)
      expect(state.defaultScope).toBe('file')
      expect(state.defaultTarget).toBe('/src/main.ts')
    })

    it('resets isDirty when opening', () => {
      useNoteEditorStore.setState({ isDirty: true })

      useNoteEditorStore.getState().open()

      expect(useNoteEditorStore.getState().isDirty).toBe(false)
    })
  })

  describe('close', () => {
    it('closes editor and resets isDirty', () => {
      useNoteEditorStore.setState({ isOpen: true, isDirty: true })

      useNoteEditorStore.getState().close()

      const state = useNoteEditorStore.getState()
      expect(state.isOpen).toBe(false)
      expect(state.isDirty).toBe(false)
    })
  })

  describe('setDirty', () => {
    it('sets dirty state', () => {
      useNoteEditorStore.getState().setDirty(true)

      expect(useNoteEditorStore.getState().isDirty).toBe(true)
    })
  })
})
