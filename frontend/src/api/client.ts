import type {
  RepoStatus,
  JobCreated,
  JobStatus,
  WikiPage,
  WikiTree,
  SearchResponse,
  ProgressEvent,
  QARequest,
  QAResponse,
  NoteCreate,
  Note,
  WorkspaceSwitchResponse,
  DirectoryListing,
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text || response.statusText);
  }

  return response.json();
}

// Repository endpoints
export async function getRepoStatus(): Promise<RepoStatus> {
  return fetchJson<RepoStatus>('/api/repos/status');
}

export async function initRepo(): Promise<JobCreated> {
  return fetchJson<JobCreated>('/api/repos/init', { method: 'POST' });
}

export async function switchWorkspace(path: string): Promise<WorkspaceSwitchResponse> {
  return fetchJson<WorkspaceSwitchResponse>('/api/repos/workspace', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}

export async function listDirectories(path?: string): Promise<DirectoryListing> {
  const params = path ? `?path=${encodeURIComponent(path)}` : '';
  return fetchJson<DirectoryListing>(`/api/repos/directories${params}`);
}

// Wiki endpoints
export async function getWikiTree(): Promise<WikiTree> {
  return fetchJson<WikiTree>('/api/wiki/tree');
}

export async function getOverview(): Promise<WikiPage> {
  return fetchJson<WikiPage>('/api/wiki/overview');
}

export async function getArchitecture(): Promise<WikiPage> {
  return fetchJson<WikiPage>('/api/wiki/architecture');
}

export async function getWorkflow(slug: string): Promise<WikiPage> {
  return fetchJson<WikiPage>(`/api/wiki/workflows/${slug}`);
}

export async function getDirectory(slug: string): Promise<WikiPage> {
  return fetchJson<WikiPage>(`/api/wiki/directories/${slug}`);
}

export async function getFile(slug: string): Promise<WikiPage> {
  return fetchJson<WikiPage>(`/api/wiki/files/${slug}`);
}

// Job endpoints
export async function listJobs(limit = 20): Promise<JobStatus[]> {
  return fetchJson<JobStatus[]>(`/api/jobs?limit=${limit}`);
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return fetchJson<JobStatus>(`/api/jobs/${jobId}`);
}

export async function cancelJob(jobId: string): Promise<{ job_id: string; status: string; cancelled_at: string }> {
  return fetchJson<{ job_id: string; status: string; cancelled_at: string }>(`/api/jobs/${jobId}/cancel`, {
    method: 'POST',
  });
}

// Search endpoint
export async function search(query: string, type?: string): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query });
  if (type) params.append('type', type);
  return fetchJson<SearchResponse>(`/api/search?${params}`);
}

// Q&A endpoint
export async function askQuestion(request: QARequest): Promise<QAResponse> {
  return fetchJson<QAResponse>('/api/qa/ask', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// Notes endpoints
export async function createNote(note: NoteCreate): Promise<Note> {
  return fetchJson<Note>('/api/notes', {
    method: 'POST',
    body: JSON.stringify(note),
  });
}

export async function listNotes(target?: string): Promise<Note[]> {
  const params = target ? `?target=${encodeURIComponent(target)}` : '';
  return fetchJson<Note[]>(`/api/notes${params}`);
}

export async function getNote(noteId: number): Promise<Note> {
  return fetchJson<Note>(`/api/notes/${noteId}`);
}

export async function deleteNote(noteId: number): Promise<void> {
  await fetch(`${API_BASE}/api/notes/${noteId}`, { method: 'DELETE' });
}

// SSE streaming for job progress
export function streamJobProgress(
  jobId: string,
  onProgress: (event: ProgressEvent) => void,
  onComplete: (event: ProgressEvent) => void,
  onError: (error: Error) => void,
  onCancelled?: (event: ProgressEvent) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/api/jobs/${jobId}/stream`);

  eventSource.addEventListener('progress', (e) => {
    const data = JSON.parse(e.data) as ProgressEvent;
    onProgress(data);
  });

  eventSource.addEventListener('complete', (e) => {
    const data = JSON.parse(e.data) as ProgressEvent;
    onComplete(data);
    eventSource.close();
  });

  eventSource.addEventListener('cancelled', (e) => {
    const data = JSON.parse(e.data) as ProgressEvent;
    if (onCancelled) {
      onCancelled(data);
    }
    eventSource.close();
  });

  eventSource.addEventListener('error', (e) => {
    const data = JSON.parse((e as MessageEvent).data) as ProgressEvent;
    onError(new Error(data.error || 'Job failed'));
    eventSource.close();
  });

  eventSource.onerror = () => {
    onError(new Error('Connection lost'));
    eventSource.close();
  };

  // Return cleanup function
  return () => eventSource.close();
}

export { ApiError };
