import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ConfirmationDialog } from './ConfirmationDialog'

describe('ConfirmationDialog', () => {
  const defaultProps = {
    isOpen: true,
    title: 'Test Title',
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  }

  it('renders nothing when isOpen is false', () => {
    render(<ConfirmationDialog {...defaultProps} isOpen={false}>Content</ConfirmationDialog>)
    expect(screen.queryByText('Test Title')).not.toBeInTheDocument()
  })

  it('renders title and children when open', () => {
    render(<ConfirmationDialog {...defaultProps}>Test Content</ConfirmationDialog>)
    expect(screen.getByText('Test Title')).toBeInTheDocument()
    expect(screen.getByText('Test Content')).toBeInTheDocument()
  })

  it('uses default button labels', () => {
    render(<ConfirmationDialog {...defaultProps}>Content</ConfirmationDialog>)
    expect(screen.getByText('Cancel')).toBeInTheDocument()
    expect(screen.getByText('Confirm')).toBeInTheDocument()
  })

  it('uses custom button labels', () => {
    render(
      <ConfirmationDialog {...defaultProps} cancelLabel="Go Back" confirmLabel="Proceed">
        Content
      </ConfirmationDialog>
    )
    expect(screen.getByText('Go Back')).toBeInTheDocument()
    expect(screen.getByText('Proceed')).toBeInTheDocument()
  })

  it('calls onCancel when cancel button clicked', () => {
    const onCancel = vi.fn()
    render(<ConfirmationDialog {...defaultProps} onCancel={onCancel}>Content</ConfirmationDialog>)
    fireEvent.click(screen.getByText('Cancel'))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('calls onConfirm when confirm button clicked', () => {
    const onConfirm = vi.fn()
    render(<ConfirmationDialog {...defaultProps} onConfirm={onConfirm}>Content</ConfirmationDialog>)
    fireEvent.click(screen.getByText('Confirm'))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('calls onCancel when backdrop clicked', () => {
    const onCancel = vi.fn()
    render(<ConfirmationDialog {...defaultProps} onCancel={onCancel}>Content</ConfirmationDialog>)
    fireEvent.click(screen.getByTestId('confirmation-backdrop'))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('does not close when dialog content clicked', () => {
    const onCancel = vi.fn()
    render(<ConfirmationDialog {...defaultProps} onCancel={onCancel}>Test Content</ConfirmationDialog>)
    fireEvent.click(screen.getByText('Test Content'))
    expect(onCancel).not.toHaveBeenCalled()
  })
})
