import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ErrorModal } from './ErrorModal'
import { useUIStore, initialState } from '../stores/uiStore'

beforeEach(() => {
  vi.clearAllMocks()
  useUIStore.setState(initialState)
})

describe('ErrorModal', () => {
  it('renders nothing when no error modal state', () => {
    const { container } = render(<ErrorModal />)
    expect(container.firstChild).toBeNull()
  })

  it('renders modal with title and message', () => {
    useUIStore.getState().showErrorModal('Error Title', 'Error details here')

    render(<ErrorModal />)

    expect(screen.getByText('Error Title')).toBeInTheDocument()
    expect(screen.getByText('Error details here')).toBeInTheDocument()
  })

  it('dismisses modal when Dismiss button clicked', () => {
    useUIStore.getState().showErrorModal('Title', 'Message')

    render(<ErrorModal />)
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }))

    expect(useUIStore.getState().errorModal).toBeNull()
  })

  it('dismisses modal when backdrop clicked', () => {
    useUIStore.getState().showErrorModal('Title', 'Message')

    render(<ErrorModal />)
    // Click the backdrop (the outer fixed div)
    const backdrop = screen.getByTestId('error-modal-backdrop')
    fireEvent.click(backdrop)

    expect(useUIStore.getState().errorModal).toBeNull()
  })

  it('shows error icon', () => {
    useUIStore.getState().showErrorModal('Title', 'Message')

    render(<ErrorModal />)

    // Icon container should have red styling
    const iconContainer = screen.getByTestId('error-modal-icon')
    expect(iconContainer.className).toContain('bg-red')
  })
})
