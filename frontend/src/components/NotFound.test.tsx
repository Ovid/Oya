import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { NotFound } from './NotFound'

describe('NotFound', () => {
  it('renders page not found heading', () => {
    render(<NotFound />)
    expect(screen.getByText('Page not found')).toBeInTheDocument()
  })

  it('renders explanatory message', () => {
    render(<NotFound />)
    expect(
      screen.getByText(/The page you're looking for doesn't exist/)
    ).toBeInTheDocument()
  })

  it('renders sad face icon', () => {
    render(<NotFound />)
    // The SVG should be present
    const svg = document.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })
})
