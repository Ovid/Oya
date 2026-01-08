// API Response Types

export interface RepoStatus {
  path: string;
  head_commit: string | null;
  head_message: string | null;
  branch: string | null;
  initialized: boolean;
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
  error?: string;
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
