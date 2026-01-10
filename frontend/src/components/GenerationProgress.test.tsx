import { describe, it, expect } from 'vitest';

/**
 * Tests for GenerationProgress phase ordering.
 * 
 * The bottom-up generation pipeline runs phases in this order:
 * Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows → Indexing
 * 
 * The frontend must display phases in this same order to correctly show
 * which phases are completed vs in-progress.
 */

// Extract the constants from the component for testing
// This ensures the phase order matches the backend's bottom-up approach
const EXPECTED_PHASE_ORDER = [
  'analysis',
  'files', 
  'directories',
  'synthesis',
  'architecture',
  'overview',
  'workflows',
  'indexing'
];

const EXPECTED_PHASES = {
  'starting': { name: 'Starting', description: 'Initializing generation...' },
  'analysis': { name: 'Analysis', description: 'Scanning repository and parsing code...' },
  'files': { name: 'Files', description: 'Generating file-level documentation...' },
  'directories': { name: 'Directories', description: 'Generating directory documentation...' },
  'synthesis': { name: 'Synthesis', description: 'Synthesizing codebase understanding...' },
  'architecture': { name: 'Architecture', description: 'Analyzing and documenting architecture...' },
  'overview': { name: 'Overview', description: 'Generating project overview page...' },
  'workflows': { name: 'Workflows', description: 'Discovering and documenting workflows...' },
  'indexing': { name: 'Indexing', description: 'Indexing content for search and Q&A...' },
};

// Import the actual constants from the component
// We re-declare them here to test against expected values
import { PHASE_ORDER, PHASES } from './GenerationProgress';

describe('GenerationProgress phase ordering', () => {
  it('should have phases in bottom-up order (files before architecture/overview)', () => {
    expect(PHASE_ORDER).toEqual(EXPECTED_PHASE_ORDER);
  });

  it('should have files phase before architecture phase', () => {
    const filesIndex = PHASE_ORDER.indexOf('files');
    const architectureIndex = PHASE_ORDER.indexOf('architecture');
    expect(filesIndex).toBeLessThan(architectureIndex);
  });

  it('should have files phase before overview phase', () => {
    const filesIndex = PHASE_ORDER.indexOf('files');
    const overviewIndex = PHASE_ORDER.indexOf('overview');
    expect(filesIndex).toBeLessThan(overviewIndex);
  });

  it('should have directories phase before synthesis phase', () => {
    const directoriesIndex = PHASE_ORDER.indexOf('directories');
    const synthesisIndex = PHASE_ORDER.indexOf('synthesis');
    expect(directoriesIndex).toBeLessThan(synthesisIndex);
  });

  it('should have synthesis phase before architecture and overview', () => {
    const synthesisIndex = PHASE_ORDER.indexOf('synthesis');
    const architectureIndex = PHASE_ORDER.indexOf('architecture');
    const overviewIndex = PHASE_ORDER.indexOf('overview');
    
    expect(synthesisIndex).toBeLessThan(architectureIndex);
    expect(synthesisIndex).toBeLessThan(overviewIndex);
  });

  it('should include synthesis phase', () => {
    expect(PHASE_ORDER).toContain('synthesis');
  });

  it('should include indexing phase', () => {
    expect(PHASE_ORDER).toContain('indexing');
  });

  it('should have 8 phases total', () => {
    expect(PHASE_ORDER).toHaveLength(8);
  });
});

describe('GenerationProgress phase definitions', () => {
  it('should have info for all phases in PHASE_ORDER', () => {
    for (const phase of PHASE_ORDER) {
      expect(PHASES[phase]).toBeDefined();
      expect(PHASES[phase].name).toBeTruthy();
      expect(PHASES[phase].description).toBeTruthy();
    }
  });

  it('should have synthesis phase info', () => {
    expect(PHASES['synthesis']).toBeDefined();
    expect(PHASES['synthesis'].name).toBe('Synthesis');
  });

  it('should have indexing phase info', () => {
    expect(PHASES['indexing']).toBeDefined();
    expect(PHASES['indexing'].name).toBe('Indexing');
  });

  it('should match expected phase definitions', () => {
    expect(PHASES).toEqual(EXPECTED_PHASES);
  });
});
