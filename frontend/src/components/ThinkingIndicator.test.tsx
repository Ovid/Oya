import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ThinkingIndicator } from './ThinkingIndicator'

describe('ThinkingIndicator', () => {
  it('renders default "Thinking" text', () => {
    render(<ThinkingIndicator />)
    expect(screen.getByText('Thinking')).toBeInTheDocument()
  })

  it('renders custom text when provided', () => {
    render(<ThinkingIndicator text="Searching" />)
    expect(screen.getByText('Searching')).toBeInTheDocument()
  })

  it('renders three animated dots', () => {
    const { container } = render(<ThinkingIndicator />)
    const dots = container.querySelectorAll('.animate-fade-in-dot')
    expect(dots).toHaveLength(3)
  })

  it('applies italic styling', () => {
    const { container } = render(<ThinkingIndicator />)
    const wrapper = container.querySelector('.italic')
    expect(wrapper).toBeInTheDocument()
  })
})
