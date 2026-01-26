import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PageInfo } from './PageInfo'
import type { WikiPageMeta } from '../utils/frontmatter'

describe('PageInfo', () => {
  describe('null handling', () => {
    it('renders nothing when meta is null', () => {
      const { container } = render(<PageInfo meta={null} />)
      expect(container).toBeEmptyDOMElement()
    })
  })

  describe('basic rendering', () => {
    it('renders Page Info header when meta has data', () => {
      const meta: WikiPageMeta = { source: 'src/main.ts' }
      render(<PageInfo meta={meta} />)
      expect(screen.getByText('Page Info')).toBeInTheDocument()
    })

    it('shows source when present', async () => {
      const user = userEvent.setup()
      const meta: WikiPageMeta = { source: 'src/utils/helper.ts' }
      render(<PageInfo meta={meta} />)
      await user.click(screen.getByRole('button', { name: /expand page info/i }))
      expect(screen.getByText('Source')).toBeInTheDocument()
      expect(screen.getByText('src/utils/helper.ts')).toBeInTheDocument()
    })

    it('shows type when present', async () => {
      const user = userEvent.setup()
      const meta: WikiPageMeta = { type: 'file' }
      render(<PageInfo meta={meta} />)
      await user.click(screen.getByRole('button', { name: /expand page info/i }))
      expect(screen.getByText('Type')).toBeInTheDocument()
      expect(screen.getByText('file')).toBeInTheDocument()
    })

    it('shows layer when present', async () => {
      const user = userEvent.setup()
      const meta: WikiPageMeta = { layer: 'api' }
      render(<PageInfo meta={meta} />)
      await user.click(screen.getByRole('button', { name: /expand page info/i }))
      expect(screen.getByText('Layer')).toBeInTheDocument()
      expect(screen.getByText('api')).toBeInTheDocument()
    })

    it('shows commit when present', async () => {
      const user = userEvent.setup()
      const meta: WikiPageMeta = { commit: 'abc1234' }
      render(<PageInfo meta={meta} />)
      await user.click(screen.getByRole('button', { name: /expand page info/i }))
      expect(screen.getByText('Commit')).toBeInTheDocument()
      expect(screen.getByText('abc1234')).toBeInTheDocument()
    })
  })

  describe('date formatting', () => {
    it('formats generated date nicely', async () => {
      const user = userEvent.setup()
      const meta: WikiPageMeta = { generated: '2024-03-15T10:30:00Z' }
      render(<PageInfo meta={meta} />)
      await user.click(screen.getByRole('button', { name: /expand page info/i }))
      expect(screen.getByText('Generated')).toBeInTheDocument()
      // Should format as "Mar 15, 2024" (US locale)
      expect(screen.getByText('Mar 15, 2024')).toBeInTheDocument()
    })
  })

  describe('missing fields', () => {
    it('skips missing fields (no undefined shown)', async () => {
      const user = userEvent.setup()
      const meta: WikiPageMeta = { source: 'src/main.ts' }
      render(<PageInfo meta={meta} />)
      await user.click(screen.getByRole('button', { name: /expand page info/i }))

      // Only source should be shown
      expect(screen.getByText('Source')).toBeInTheDocument()
      expect(screen.queryByText('Type')).not.toBeInTheDocument()
      expect(screen.queryByText('Layer')).not.toBeInTheDocument()
      expect(screen.queryByText('Generated')).not.toBeInTheDocument()
      expect(screen.queryByText('Commit')).not.toBeInTheDocument()
      expect(screen.queryByText('undefined')).not.toBeInTheDocument()
    })

    it('renders nothing when meta is empty object', () => {
      const { container } = render(<PageInfo meta={{}} />)
      expect(container).toBeEmptyDOMElement()
    })
  })

  describe('collapse/expand behavior', () => {
    it('starts collapsed by default', () => {
      const meta: WikiPageMeta = { source: 'src/main.ts' }
      render(<PageInfo meta={meta} />)

      // Header should be visible, content should not
      expect(screen.getByText('Page Info')).toBeInTheDocument()
      expect(screen.queryByText('src/main.ts')).not.toBeInTheDocument()
    })

    it('expands when clicked', async () => {
      const user = userEvent.setup()
      const meta: WikiPageMeta = { source: 'src/main.ts' }
      render(<PageInfo meta={meta} />)

      // Click to expand
      await user.click(screen.getByRole('button', { name: /expand page info/i }))

      expect(screen.getByText('src/main.ts')).toBeInTheDocument()
    })

    it('collapses when clicked again', async () => {
      const user = userEvent.setup()
      const meta: WikiPageMeta = { source: 'src/main.ts' }
      render(<PageInfo meta={meta} />)

      // Expand
      await user.click(screen.getByRole('button', { name: /expand page info/i }))
      expect(screen.getByText('src/main.ts')).toBeInTheDocument()

      // Collapse
      await user.click(screen.getByRole('button', { name: /collapse page info/i }))
      expect(screen.queryByText('src/main.ts')).not.toBeInTheDocument()
    })
  })
})
