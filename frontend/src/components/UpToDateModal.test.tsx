import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UpToDateModal } from './UpToDateModal'

describe('UpToDateModal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(<UpToDateModal isOpen={false} onClose={() => {}} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders modal content when open', () => {
    render(<UpToDateModal isOpen={true} onClose={() => {}} />)
    expect(screen.getByText('Wiki is up-to-date')).toBeInTheDocument()
    expect(screen.getByText('No changes detected since last generation.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Got it' })).toBeInTheDocument()
  })

  it('calls onClose when button is clicked', () => {
    const onClose = vi.fn()
    render(<UpToDateModal isOpen={true} onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: 'Got it' }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when backdrop is clicked', () => {
    const onClose = vi.fn()
    render(<UpToDateModal isOpen={true} onClose={onClose} />)
    // The backdrop is the first fixed div with bg-black/50
    const backdrop = document.querySelector('.bg-black\\/50')
    fireEvent.click(backdrop!)
    expect(onClose).toHaveBeenCalledOnce()
  })
})
