import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ToastContainer } from './ToastContainer'
import { useUIStore, initialState } from '../stores/uiStore'

beforeEach(() => {
  vi.clearAllMocks()
  useUIStore.setState(initialState)
})

describe('ToastContainer', () => {
  it('renders nothing when no toasts', () => {
    const { container } = render(<ToastContainer />)
    expect(container.firstChild).toBeNull()
  })

  it('renders a toast message', () => {
    useUIStore.getState().addToast('Test error message', 'error')

    render(<ToastContainer />)

    expect(screen.getByText('Test error message')).toBeInTheDocument()
  })

  it('renders multiple toasts', () => {
    useUIStore.getState().addToast('First message', 'error')
    useUIStore.getState().addToast('Second message', 'warning')

    render(<ToastContainer />)

    expect(screen.getByText('First message')).toBeInTheDocument()
    expect(screen.getByText('Second message')).toBeInTheDocument()
  })

  it('dismisses toast when X button clicked', () => {
    useUIStore.getState().addToast('Dismissable', 'info')

    render(<ToastContainer />)
    const dismissButton = screen.getByRole('button', { name: /dismiss/i })
    fireEvent.click(dismissButton)

    expect(screen.queryByText('Dismissable')).not.toBeInTheDocument()
  })

  it('limits visible toasts to max', () => {
    // Add more than TOAST_MAX_VISIBLE toasts
    useUIStore.getState().addToast('First', 'error')
    useUIStore.getState().addToast('Second', 'error')
    useUIStore.getState().addToast('Third', 'error')
    useUIStore.getState().addToast('Fourth', 'error')

    render(<ToastContainer />)

    // Should only show 3 (TOAST_MAX_VISIBLE)
    const toasts = screen.getAllByRole('alert')
    expect(toasts.length).toBeLessThanOrEqual(3)
  })

  it('applies correct styling for error type', () => {
    useUIStore.getState().addToast('Error toast', 'error')

    render(<ToastContainer />)

    const toast = screen.getByRole('alert')
    expect(toast.className).toContain('bg-red')
  })

  it('applies correct styling for warning type', () => {
    useUIStore.getState().addToast('Warning toast', 'warning')

    render(<ToastContainer />)

    const toast = screen.getByRole('alert')
    expect(toast.className).toContain('bg-amber')
  })

  it('applies correct styling for info type', () => {
    useUIStore.getState().addToast('Info toast', 'info')

    render(<ToastContainer />)

    const toast = screen.getByRole('alert')
    expect(toast.className).toContain('bg-blue')
  })
})
