export function formatElapsedTime(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`
  }
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
}

export interface PhaseInfo {
  name: string
  description: string
}

export const PHASES: Record<string, PhaseInfo> = {
  starting: { name: 'Starting', description: 'Initializing generation...' },
  syncing: { name: 'Sync', description: 'Syncing repository and scanning code...' },
  files: { name: 'Files', description: 'Generating file-level documentation...' },
  directories: { name: 'Directories', description: 'Generating directory documentation...' },
  synthesis: { name: 'Synthesis', description: 'Synthesizing codebase understanding...' },
  architecture: { name: 'Architecture', description: 'Analyzing and documenting architecture...' },
  overview: { name: 'Overview', description: 'Generating project overview page...' },
  workflows: { name: 'Workflows', description: 'Discovering and documenting workflows...' },
  indexing: { name: 'Indexing', description: 'Indexing content for search and Q&A...' },
}

// Ordered list of phases for progress display (bottom-up approach)
// Order: Sync → Files → Directories → Synthesis → Architecture → Overview → Workflows → Indexing
export const PHASE_ORDER = [
  'syncing',
  'files',
  'directories',
  'synthesis',
  'architecture',
  'overview',
  'workflows',
  'indexing',
]
