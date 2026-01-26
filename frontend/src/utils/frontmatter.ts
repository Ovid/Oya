/**
 * Wiki page metadata extracted from frontmatter.
 * All fields are optional as not all pages may have complete metadata.
 */
export interface WikiPageMeta {
  /** Path to the source file/directory this page documents */
  source?: string
  /** Type of documentation page: 'file', 'directory', etc. */
  type?: string
  /** ISO timestamp when the page was generated */
  generated?: string
  /** Git commit hash at generation time */
  commit?: string
  /** Architectural layer (e.g., 'api', 'core', 'ui') */
  layer?: string
}

/** Known frontmatter fields to extract */
const KNOWN_FIELDS: ReadonlySet<string> = new Set([
  'source',
  'type',
  'generated',
  'commit',
  'layer',
])

/**
 * Parse YAML-style frontmatter from wiki page content.
 *
 * Frontmatter must:
 * - Start at the very beginning of the content
 * - Be delimited by `---` on its own line
 * - Contain simple `key: value` pairs (one per line)
 *
 * @param content - The full page content including potential frontmatter
 * @returns Object with extracted metadata (or null) and the content without frontmatter
 *
 * @example
 * ```ts
 * const { meta, content } = parseFrontmatter(`---
 * source: path/to/file.py
 * type: file
 * ---
 *
 * # Page Title`)
 *
 * // meta = { source: 'path/to/file.py', type: 'file' }
 * // content = '# Page Title'
 * ```
 */
export function parseFrontmatter(content: string): {
  meta: WikiPageMeta | null
  content: string
} {
  // Frontmatter must start at the beginning with ---
  if (!content.startsWith('---')) {
    return { meta: null, content }
  }

  // Find the closing ---
  // Look for \n---\n or \n--- at end of string
  const closingMatch = content.match(/\n---(\r?\n|$)/)
  if (!closingMatch || closingMatch.index === undefined) {
    return { meta: null, content }
  }

  const closingIndex = closingMatch.index
  const frontmatterBlock = content.slice(4, closingIndex) // Skip opening ---\n
  const afterFrontmatter = content.slice(closingIndex + closingMatch[0].length)

  // Parse key: value pairs from frontmatter block
  const meta: WikiPageMeta = {}
  const lines = frontmatterBlock.split('\n')

  for (const line of lines) {
    const trimmedLine = line.trim()
    if (!trimmedLine) continue

    // Find the first colon to split key: value
    const colonIndex = trimmedLine.indexOf(':')
    if (colonIndex === -1) continue

    const key = trimmedLine.slice(0, colonIndex).trim()
    const value = trimmedLine.slice(colonIndex + 1).trim()

    // Only include known fields
    if (KNOWN_FIELDS.has(key)) {
      meta[key as keyof WikiPageMeta] = value
    }
  }

  // Trim leading whitespace from content (but preserve content structure)
  const trimmedContent = afterFrontmatter.replace(/^[\r\n]+/, '')

  return { meta, content: trimmedContent }
}
