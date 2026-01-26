import { describe, it, expect } from 'vitest'
import { parseFrontmatter, WikiPageMeta } from './frontmatter'

describe('parseFrontmatter', () => {
  it('extracts frontmatter from content with all fields', () => {
    const content = `---
source: path/to/file.py
type: file
generated: 2026-01-26T10:30:00Z
commit: abc123def456
layer: api
---

# Content starts here

Some body text.`

    const result = parseFrontmatter(content)

    expect(result.meta).toEqual({
      source: 'path/to/file.py',
      type: 'file',
      generated: '2026-01-26T10:30:00Z',
      commit: 'abc123def456',
      layer: 'api',
    } satisfies WikiPageMeta)

    expect(result.content).toBe(`# Content starts here

Some body text.`)
  })

  it('handles content with partial frontmatter', () => {
    const content = `---
source: src/main.ts
type: directory
---

# Directory Overview`

    const result = parseFrontmatter(content)

    expect(result.meta).toEqual({
      source: 'src/main.ts',
      type: 'directory',
    })
    expect(result.content).toBe('# Directory Overview')
  })

  it('returns null meta for content without frontmatter', () => {
    const content = `# Just a heading

Some text without frontmatter.`

    const result = parseFrontmatter(content)

    expect(result.meta).toBeNull()
    expect(result.content).toBe(content)
  })

  it('returns null meta for content with incomplete frontmatter (no closing)', () => {
    const content = `---
source: file.py
type: file

# This never closes the frontmatter`

    const result = parseFrontmatter(content)

    expect(result.meta).toBeNull()
    expect(result.content).toBe(content)
  })

  it('handles empty content', () => {
    const result = parseFrontmatter('')

    expect(result.meta).toBeNull()
    expect(result.content).toBe('')
  })

  it('handles frontmatter only (no content after)', () => {
    const content = `---
source: empty.md
---`

    const result = parseFrontmatter(content)

    expect(result.meta).toEqual({
      source: 'empty.md',
    })
    expect(result.content).toBe('')
  })

  it('handles values with colons in them', () => {
    const content = `---
source: C:/Users/path/file.ts
generated: 2026-01-26T10:30:00Z
---

Content`

    const result = parseFrontmatter(content)

    expect(result.meta).toEqual({
      source: 'C:/Users/path/file.ts',
      generated: '2026-01-26T10:30:00Z',
    })
    expect(result.content).toBe('Content')
  })

  it('trims whitespace from values', () => {
    const content = `---
source:   file.py
type:	directory
---

Content`

    const result = parseFrontmatter(content)

    expect(result.meta).toEqual({
      source: 'file.py',
      type: 'directory',
    })
  })

  it('ignores unknown frontmatter fields', () => {
    const content = `---
source: file.py
unknown_field: some value
another_unknown: value
type: file
---

Content`

    const result = parseFrontmatter(content)

    expect(result.meta).toEqual({
      source: 'file.py',
      type: 'file',
    })
    // Unknown fields should not be in the result
    expect(result.meta).not.toHaveProperty('unknown_field')
    expect(result.meta).not.toHaveProperty('another_unknown')
  })

  it('handles frontmatter that does not start at beginning', () => {
    const content = `Some text before
---
source: file.py
---

Content`

    const result = parseFrontmatter(content)

    // Frontmatter must be at the start
    expect(result.meta).toBeNull()
    expect(result.content).toBe(content)
  })

  it('handles empty frontmatter block', () => {
    const content = `---
---

Content after empty frontmatter`

    const result = parseFrontmatter(content)

    expect(result.meta).toEqual({})
    expect(result.content).toBe('Content after empty frontmatter')
  })
})
