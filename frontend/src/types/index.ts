// API Response Types

export interface EmbeddingMetadata {
  provider: string
  model: string
  indexed_at: string
}

export interface RepoStatus {
  path: string
  head_commit: string | null
  head_message: string | null
  branch: string | null
  initialized: boolean
  is_docker: boolean
  last_generation: string | null
  generation_status: string | null
  embedding_metadata: EmbeddingMetadata | null
  current_provider: string | null
  current_model: string | null
  embedding_mismatch: boolean
}

export interface JobCreated {
  job_id: string
  status: string
  message: string
}

export interface JobStatus {
  job_id: string
  type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string | null
  completed_at: string | null
  current_phase: string | null
  total_phases: number | null
  error_message: string | null
  changes_made?: boolean | null
}

export interface WikiPage {
  content: string
  page_type: 'overview' | 'architecture' | 'workflow' | 'directory' | 'file'
  path: string
  word_count: number
  source_path: string | null
}

export interface WikiTree {
  overview: boolean
  architecture: boolean
  workflows: string[]
  directories: string[]
  files: string[]
}

export interface SearchResult {
  title: string
  path: string
  snippet: string
  type: string
  score: number
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  total: number
}

// SSE Event Types
export interface ProgressEvent {
  job_id: string
  status: string
  phase: string | null
  total_phases: number | null
  current_step: number | null
  total_steps: number | null
  error?: string
}

// Q&A Types
export type ConfidenceLevel = 'high' | 'medium' | 'low'

export interface SearchQuality {
  semantic_searched: boolean
  fts_searched: boolean
  results_found: number
  results_used: number
}

export interface Citation {
  path: string
  title: string
  lines: string | null
  url: string
}

export interface QARequest {
  question: string
}

export interface QAResponse {
  answer: string
  citations: Citation[]
  confidence: ConfidenceLevel
  disclaimer: string
  search_quality: SearchQuality
}

// Notes Types
export type NoteScope = 'file' | 'directory' | 'workflow' | 'general'

export interface Note {
  id: number
  scope: NoteScope
  target: string
  content: string
  author: string | null
  updated_at: string
}

// UI State Types
export interface AppState {
  repoStatus: RepoStatus | null
  wikiTree: WikiTree | null
  currentPage: WikiPage | null
  currentJob: JobStatus | null
  isLoading: boolean
  error: string | null
}

export type PageType = 'overview' | 'architecture' | 'workflow' | 'directory' | 'file'

// Workspace Switching Types
export interface WorkspaceSwitchRequest {
  path: string
}

export interface WorkspaceSwitchResponse {
  status: RepoStatus
  message: string
}

// Generation Status Types
export interface GenerationStatus {
  status: 'incomplete'
  message: string
}

// Indexing Preview Types
export interface FileList {
  directories: string[]
  files: string[]
}

export interface IndexableItems {
  included: FileList
  excluded_by_oyaignore: FileList
  excluded_by_rule: FileList
}

export interface OyaignoreUpdateRequest {
  directories: string[]
  files: string[]
  removals: string[]
}

export interface OyaignoreUpdateResponse {
  added_directories: string[]
  added_files: string[]
  removed: string[]
  total_added: number
  total_removed: number
}

// Multi-Repo Types (v2 API)
export type RepoStatusType = 'pending' | 'cloning' | 'generating' | 'ready' | 'failed'

export interface Repo {
  id: number
  origin_url: string
  source_type: string
  local_path: string
  display_name: string
  head_commit: string | null
  branch: string | null
  created_at: string | null
  last_pulled: string | null
  last_generated: string | null
  generation_duration_secs: number | null
  files_processed: number | null
  pages_generated: number | null
  status: RepoStatusType
  error_message: string | null
}

export interface RepoListResponse {
  repos: Repo[]
  total: number
}

export interface CreateRepoRequest {
  url: string
  display_name?: string
}

export interface CreateRepoResponse {
  id: number
  origin_url: string
  source_type: string
  local_path: string
  display_name: string
  status: string
}

export interface ActivateRepoResponse {
  active_repo_id: number
}

export interface ActiveRepoResponse {
  active_repo: Repo | null
}

// Logs Types
export interface LogsResponse {
  content: string
  size_bytes: number
  entry_count: number
}

export interface DeleteLogsResponse {
  message: string
}
