// Common file extensions - used to identify where the extension starts in a slug
const FILE_EXTENSIONS = new Set([
  // Common languages
  'py',
  'js',
  'ts',
  'tsx',
  'jsx',
  'java',
  'go',
  'rs',
  'rb',
  'php',
  'c',
  'cpp',
  'h',
  'hpp',
  'cs',
  'swift',
  'kt',
  'scala',
  // Perl
  'pl',
  'pm',
  'pod',
  't',
  // Web
  'html',
  'css',
  'scss',
  'less',
  'sass',
  'vue',
  'svelte',
  // Config/data
  'md',
  'json',
  'yaml',
  'yml',
  'toml',
  'xml',
  'ini',
  'cfg',
  'conf',
  // Shell
  'sh',
  'bash',
  'zsh',
  'fish',
  // Other
  'sql',
  'graphql',
  'proto',
  'ex',
  'exs',
  'erl',
  'hrl',
  'clj',
  'cljs',
  'lua',
  'r',
  'jl',
  'nim',
  'zig',
  'v',
  'dart',
  'groovy',
])

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
