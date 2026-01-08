import type {
  RepoStatus,
  JobCreated,
  JobStatus,
  WikiPage,
  WikiTree,
  SearchResponse,
  ProgressEvent,
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

// Search endpoint
export async function search(query: string, type?: string): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query });
  if (type) params.append('type', type);
  return fetchJson<SearchResponse>(`/api/search?${params}`);
}

// SSE streaming for job progress
export function streamJobProgress(
  jobId: string,
  onProgress: (event: ProgressEvent) => void,
  onComplete: (event: ProgressEvent) => void,
  onError: (error: Error) => void
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
