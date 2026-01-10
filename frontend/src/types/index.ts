// API Response Types

export interface RepoStatus {
  path: string;
  head_commit: string | null;
  head_message: string | null;
  branch: string | null;
  initialized: boolean;
  is_docker: boolean;
  last_generation: string | null;
  generation_status: string | null;
}

export interface JobCreated {
  job_id: string;
  status: string;
  message: string;
}

export interface JobStatus {
  job_id: string;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at: string | null;
  completed_at: string | null;
  current_phase: string | null;
  total_phases: number | null;
  error_message: string | null;
}

export interface WikiPage {
  content: string;
  page_type: 'overview' | 'architecture' | 'workflow' | 'directory' | 'file';
  path: string;
  word_count: number;
  source_path: string | null;
}

export interface WikiTree {
  overview: boolean;
  architecture: boolean;
  workflows: string[];
  directories: string[];
  files: string[];
}

export interface SearchResult {
  title: string;
  path: string;
  snippet: string;
  type: string;
  score: number;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

// SSE Event Types
export interface ProgressEvent {
  job_id: string;
  status: string;
  phase: string | null;
  total_phases: number | null;
  current_step: number | null;
  total_steps: number | null;
  error?: string;
}

// Q&A Types
export type QAMode = 'gated' | 'loose';

export interface Citation {
  path: string;
  title: string;
  lines: string | null;
}

export interface QARequest {
  question: string;
  context?: {
    page_type: string;
    slug: string;
  };
  mode?: QAMode;
}

export interface QAResponse {
  answer: string;
  citations: Citation[];
  evidence_sufficient: boolean;
  disclaimer: string;
}

// Notes Types
export type NoteScope = 'file' | 'directory' | 'workflow' | 'general';

export interface NoteCreate {
  scope: NoteScope;
  target: string;
  content: string;
  author?: string;
}

export interface Note {
  id: number;
  filepath: string;
  scope: NoteScope;
  target: string;
  content: string;
  author: string | null;
  created_at: string;
}

// UI State Types
export interface AppState {
  repoStatus: RepoStatus | null;
  wikiTree: WikiTree | null;
  currentPage: WikiPage | null;
  currentJob: JobStatus | null;
  isLoading: boolean;
  error: string | null;
}

export type PageType = 'overview' | 'architecture' | 'workflow' | 'directory' | 'file';

// Workspace Switching Types
export interface WorkspaceSwitchRequest {
  path: string;
}

export interface WorkspaceSwitchResponse {
  status: RepoStatus;
  message: string;
}

// Directory Browser Types
export interface DirectoryEntry {
  name: string;
  path: string;
  is_dir: boolean;
}

export interface DirectoryListing {
  path: string;
  parent: string | null;
  entries: DirectoryEntry[];
}
