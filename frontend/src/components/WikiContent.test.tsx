import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WikiContent } from './WikiContent'
import type { WikiPage } from '../types'

// Mock mermaid to avoid initialization issues in tests
vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({ svg: '<svg></svg>' }),
  },
}))

function createPage(content: string): WikiPage {
  return {
    content,
    page_type: 'file',
    path: '/test/page',
    word_count: content.split(/\s+/).length,
    source_path: 'src/test.ts',
  }
}

describe('WikiContent', () => {
  describe('frontmatter parsing', () => {
    it('parses frontmatter and renders PageInfo with metadata', () => {
      const content = `---
source: src/main.ts
type: file
layer: api
---

# Main File

This is the main file.`
      const page = createPage(content)

      render(<WikiContent page={page} />)

      // PageInfo should be rendered (header visible by default)
      expect(screen.getByText('Page Info')).toBeInTheDocument()
    })

    it('strips frontmatter from markdown content (not rendered twice)', () => {
      const content = `---
source: src/main.ts
type: file
---

# Main File

This is the main file.`
      const page = createPage(content)

      render(<WikiContent page={page} />)

      // The heading should appear once (in the markdown content)
      const headings = screen.getAllByRole('heading', { level: 1 })
      expect(headings).toHaveLength(1)
      expect(headings[0]).toHaveTextContent('Main File')

      // The frontmatter should NOT be rendered as content
      // (when frontmatter is not stripped, markdown renders `---` as hr,
      // and the key:value lines may appear in headings or paragraphs)
      expect(screen.queryByText(/source:/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/type: file/i)).not.toBeInTheDocument()
    })

    it('works with content that has no frontmatter (PageInfo not shown)', () => {
      const content = `# Simple Page

This page has no frontmatter.`
      const page = createPage(content)

      render(<WikiContent page={page} />)

      // PageInfo should not be rendered
      expect(screen.queryByText('Page Info')).not.toBeInTheDocument()

      // But the content should still render
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Simple Page')
      expect(screen.getByText('This page has no frontmatter.')).toBeInTheDocument()
    })

    it('handles empty frontmatter (PageInfo not shown)', () => {
      const content = `---
---

# Page with empty frontmatter`
      const page = createPage(content)

      render(<WikiContent page={page} />)

      // PageInfo should not render for empty frontmatter
      expect(screen.queryByText('Page Info')).not.toBeInTheDocument()

      // Content should still render
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
        'Page with empty frontmatter'
      )
    })
  })

  describe('markdown rendering', () => {
    it('renders markdown content after stripping frontmatter', () => {
      const content = `---
source: src/utils.ts
---

# Utilities

Some **bold** and *italic* text.

- List item 1
- List item 2`
      const page = createPage(content)

      render(<WikiContent page={page} />)

      // Check the main content rendered
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Utilities')
      expect(screen.getByText(/bold/)).toBeInTheDocument()
      expect(screen.getByText('List item 1')).toBeInTheDocument()
      expect(screen.getByText('List item 2')).toBeInTheDocument()
    })
  })
})
