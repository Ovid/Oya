import { FILE_EXTENSIONS } from '../config'

/**
 * Convert a wiki URL slug back to a file/directory path.
 *
 * Wiki URL slugs use single-dash (-) as separators for both path components
 * and the file extension dot. This is different from notes file slugs which
 * use double-dash (--) for path separators and preserve dots.
 *
 * Examples:
 *   "lib-MooseX-Extended-pm" -> "lib/MooseX/Extended.pm"
 *   "src-api" -> "src/api" (directory, no extension detected)
 *
 * We use known file extensions to identify where the extension starts.
 */
export function wikiSlugToPath(slug: string): string {
  const parts = slug.split('-')

  if (parts.length === 0) return slug

  // Check if last part is a known extension (case-insensitive lookup)
  const lastPart = parts[parts.length - 1]
  if (FILE_EXTENSIONS.has(lastPart.toLowerCase()) && parts.length >= 2) {
    // Join all but last with /, then add .extension
    const pathParts = parts.slice(0, -1)
    return pathParts.join('/') + '.' + lastPart
  }

  // Fallback: just replace dashes with slashes (for directories)
  return slug.replace(/-/g, '/')
}

/**
 * Convert a slug to a human-readable title.
 *
 * Replaces hyphens with spaces and title-cases each word.
 *
 * Examples:
 *   "repos-v2" -> "Repos V2"
 *   "route-workflows" -> "Route Workflows"
 *   "qa" -> "QA"
 */
export function slugToTitle(slug: string): string {
  return slug
    .replace(/-/g, ' ')
    .split(' ')
    .map((word) => {
      // Handle common abbreviations that should be all uppercase
      const upperWord = word.toUpperCase()
      if (['QA', 'API', 'UI', 'ID', 'URL', 'HTTP', 'CLI', 'DB'].includes(upperWord)) {
        return upperWord
      }
      // Handle version strings like "v1", "v2" -> "V1", "V2"
      if (/^v\d+$/i.test(word)) {
        return word.toUpperCase()
      }
      // Standard title case
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    })
    .join(' ')
}
