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
