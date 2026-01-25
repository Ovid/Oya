/**
 * Known file extensions for slug-to-path conversion.
 *
 * Used by wikiSlugToPath() to identify where the file extension starts in a slug.
 * Wiki URL slugs use single-dash as separator (src-main-py), so we need to know
 * common extensions to reconstruct paths like "src/main.py".
 *
 * Extensions not in this list will cause the path to be treated as a directory
 * (all dashes become slashes). This is usually fine for browsing, but may cause
 * issues if notes are associated with files having uncommon extensions.
 */
export const FILE_EXTENSIONS = new Set([
  // Common languages
  'py',
  'js',
  'ts',
  'tsx',
  'jsx',
  'mjs',
  'cjs',
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
  'wasm',
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
  'env',
  'editorconfig',
  'gitignore',
  'dockerignore',
  'npmrc',
  'prettierrc',
  // Build files
  'gradle',
  'cmake',
  'make',
  'ninja',
  // Documentation
  'rst',
  'adoc',
  'tex',
  // Data/ML
  'csv',
  'tsv',
  'parquet',
  'pkl',
  'h5',
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
