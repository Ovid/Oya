# JSONL Log Viewer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a modal dialog to view LLM query logs for the active repository, accessible from an icon button in the TopBar.

**Architecture:** New React modal component with client-side JSONL parsing, backed by two new API endpoints (GET/DELETE) that read/delete the log file. Button visible in TopBar only when a repo is active.

**Tech Stack:** React + TypeScript + Tailwind (frontend), FastAPI + Pydantic (backend), Vitest + pytest (tests)

---

## Task 1: Backend - Log Endpoints

**Files:**
- Create: `backend/src/oya/api/routers/logs.py`
- Modify: `backend/src/oya/main.py` (add router)
- Create: `backend/tests/api/test_logs.py`

### Step 1: Write the failing tests

Create `backend/tests/api/test_logs.py`:

```python
"""Tests for the logs API endpoints."""

from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

from oya.main import app
from oya.db.repo_registry import RepoRegistry
from oya.config import load_settings
from oya.api.deps import get_settings, _reset_db_instance


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Set up OYA_DATA_DIR for tests."""
    oya_dir = tmp_path / ".oya"
    oya_dir.mkdir()
    monkeypatch.setenv("OYA_DATA_DIR", str(oya_dir))

    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    yield oya_dir

    _reset_db_instance()


def _create_repo_with_logs(data_dir: Path, log_content: str) -> int:
    """Helper to create a repo and populate its logs."""
    registry = RepoRegistry(data_dir / "repos.db")
    repo_id = registry.add(
        "https://github.com/test/repo",
        "github",
        "github.com/test/repo",
        "Test Repo"
    )
    registry.set_setting("active_repo_id", str(repo_id))
    registry.close()

    # Create the log directory and file
    log_dir = data_dir / "wikis" / "github.com" / "test" / "repo" / "meta" / ".oya-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "llm-queries.jsonl").write_text(log_content)

    return repo_id


def _create_repo_without_logs(data_dir: Path) -> int:
    """Helper to create a repo without logs."""
    registry = RepoRegistry(data_dir / "repos.db")
    repo_id = registry.add(
        "https://github.com/test/repo",
        "github",
        "github.com/test/repo",
        "Test Repo"
    )
    registry.set_setting("active_repo_id", str(repo_id))
    registry.close()

    # Create the meta directory structure but no log file
    meta_dir = data_dir / "wikis" / "github.com" / "test" / "repo" / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    return repo_id


@pytest.mark.asyncio
async def test_get_logs_returns_content(data_dir):
    """GET /api/v2/repos/{repo_id}/logs/llm-queries returns log content."""
    log_content = '{"timestamp": "2024-01-01", "model": "gpt-4"}\n{"timestamp": "2024-01-02", "model": "gpt-4"}\n'
    repo_id = _create_repo_with_logs(data_dir, log_content)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v2/repos/{repo_id}/logs/llm-queries")

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == log_content
    assert data["entry_count"] == 2


@pytest.mark.asyncio
async def test_get_logs_not_found_when_no_file(data_dir):
    """GET /api/v2/repos/{repo_id}/logs/llm-queries returns 404 when no log file exists."""
    repo_id = _create_repo_without_logs(data_dir)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v2/repos/{repo_id}/logs/llm-queries")

    assert response.status_code == 404
    assert "no logs" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_logs_repo_not_found(data_dir):
    """GET /api/v2/repos/{repo_id}/logs/llm-queries returns 404 for non-existent repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v2/repos/999/logs/llm-queries")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_logs_removes_file(data_dir):
    """DELETE /api/v2/repos/{repo_id}/logs/llm-queries removes the log file."""
    log_content = '{"timestamp": "2024-01-01"}\n'
    repo_id = _create_repo_with_logs(data_dir, log_content)
    log_path = data_dir / "wikis" / "github.com" / "test" / "repo" / "meta" / ".oya-logs" / "llm-queries.jsonl"

    assert log_path.exists()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/v2/repos/{repo_id}/logs/llm-queries")

    assert response.status_code == 200
    assert "deleted" in response.json()["message"].lower()
    assert not log_path.exists()


@pytest.mark.asyncio
async def test_delete_logs_not_found_when_no_file(data_dir):
    """DELETE /api/v2/repos/{repo_id}/logs/llm-queries returns 404 when no log file exists."""
    repo_id = _create_repo_without_logs(data_dir)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/v2/repos/{repo_id}/logs/llm-queries")

    assert response.status_code == 404
    assert "no logs" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_logs_repo_not_found(data_dir):
    """DELETE /api/v2/repos/{repo_id}/logs/llm-queries returns 404 for non-existent repo."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/v2/repos/999/logs/llm-queries")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
```

### Step 2: Run tests to verify they fail

```bash
cd backend && pytest tests/api/test_logs.py -v
```

Expected: FAIL (router doesn't exist)

### Step 3: Create the logs router

Create `backend/src/oya/api/routers/logs.py`:

```python
"""API endpoints for accessing repository logs."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from oya.config import load_settings
from oya.db.repo_registry import RepoRegistry
from oya.repo.repo_paths import RepoPaths

router = APIRouter(prefix="/api/v2/repos", tags=["logs"])


class LogsResponse(BaseModel):
    """Response containing log file content."""

    content: str
    size_bytes: int
    entry_count: int


class DeleteLogsResponse(BaseModel):
    """Response after deleting logs."""

    message: str


def _get_repo_or_404(repo_id: int) -> tuple:
    """Get repo from registry or raise 404."""
    settings = load_settings()
    registry = RepoRegistry(settings.repos_db_path)
    try:
        repo = registry.get(repo_id)
        if repo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository {repo_id} not found",
            )
        return repo, settings
    finally:
        registry.close()


@router.get("/{repo_id}/logs/llm-queries", response_model=LogsResponse)
async def get_llm_logs(repo_id: int) -> LogsResponse:
    """Get the LLM query logs for a repository."""
    repo, settings = _get_repo_or_404(repo_id)
    paths = RepoPaths(settings.data_dir, repo.local_path)
    log_file = paths.oya_logs / "llm-queries.jsonl"

    if not log_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No logs found for this repository",
        )

    content = log_file.read_text()
    entry_count = sum(1 for line in content.strip().split("\n") if line.strip())

    return LogsResponse(
        content=content,
        size_bytes=log_file.stat().st_size,
        entry_count=entry_count,
    )


@router.delete("/{repo_id}/logs/llm-queries", response_model=DeleteLogsResponse)
async def delete_llm_logs(repo_id: int) -> DeleteLogsResponse:
    """Delete the LLM query logs for a repository."""
    repo, settings = _get_repo_or_404(repo_id)
    paths = RepoPaths(settings.data_dir, repo.local_path)
    log_file = paths.oya_logs / "llm-queries.jsonl"

    if not log_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No logs to delete",
        )

    log_file.unlink()

    return DeleteLogsResponse(message="Logs deleted successfully")
```

### Step 4: Register the router in main.py

In `backend/src/oya/main.py`, add the import and include:

```python
from oya.api.routers import logs

# In the router includes section:
app.include_router(logs.router)
```

### Step 5: Run tests to verify they pass

```bash
cd backend && pytest tests/api/test_logs.py -v
```

Expected: All tests pass

### Step 6: Commit

```bash
git add backend/src/oya/api/routers/logs.py backend/src/oya/main.py backend/tests/api/test_logs.py
git commit -m "feat(api): add logs endpoints for LLM query logs

- GET /api/v2/repos/{repo_id}/logs/llm-queries
- DELETE /api/v2/repos/{repo_id}/logs/llm-queries"
```

---

## Task 2: Frontend - API Client Functions

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/types/index.ts`

### Step 1: Add types

In `frontend/src/types/index.ts`, add at the end:

```typescript
// Logs Types
export interface LogsResponse {
  content: string
  size_bytes: number
  entry_count: number
}

export interface DeleteLogsResponse {
  message: string
}
```

### Step 2: Add API client functions

In `frontend/src/api/client.ts`, add after the multi-repo endpoints section:

```typescript
// =============================================================================
// Logs Endpoints
// =============================================================================

export async function getLogs(repoId: number): Promise<LogsResponse> {
  return fetchJson<LogsResponse>(`/api/v2/repos/${repoId}/logs/llm-queries`)
}

export async function deleteLogs(repoId: number): Promise<DeleteLogsResponse> {
  return fetchJson<DeleteLogsResponse>(`/api/v2/repos/${repoId}/logs/llm-queries`, {
    method: 'DELETE',
  })
}
```

Also add the imports at the top:

```typescript
import type {
  // ... existing imports ...
  LogsResponse,
  DeleteLogsResponse,
} from '../types'
```

### Step 3: Commit

```bash
git add frontend/src/api/client.ts frontend/src/types/index.ts
git commit -m "feat(frontend): add API client functions for logs endpoints"
```

---

## Task 3: Frontend - LogViewerModal Component

**Files:**
- Create: `frontend/src/components/LogViewerModal.tsx`
- Create: `frontend/src/components/LogViewerModal.test.tsx`

### Step 1: Write the failing tests

Create `frontend/src/components/LogViewerModal.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../api/client', () => ({
  getLogs: vi.fn(),
  deleteLogs: vi.fn(),
}))

import { LogViewerModal } from './LogViewerModal'
import * as api from '../api/client'

beforeEach(() => {
  vi.clearAllMocks()
})

const mockLogsResponse = {
  content: '{"timestamp":"2024-01-01","model":"gpt-4","prompt":"test"}\n{"timestamp":"2024-01-02","model":"gpt-4","prompt":"test2"}\n',
  size_bytes: 100,
  entry_count: 2,
}

describe('LogViewerModal', () => {
  it('does not render when isOpen is false', () => {
    render(
      <LogViewerModal
        isOpen={false}
        onClose={vi.fn()}
        repoId={1}
        repoName="Test Repo"
      />
    )

    expect(screen.queryByText('LLM Logs')).not.toBeInTheDocument()
  })

  it('renders modal when isOpen is true', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(
      <LogViewerModal
        isOpen={true}
        onClose={vi.fn()}
        repoId={1}
        repoName="Test Repo"
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/LLM Logs/)).toBeInTheDocument()
    })
  })

  it('displays entry count after loading', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(
      <LogViewerModal
        isOpen={true}
        onClose={vi.fn()}
        repoId={1}
        repoName="Test Repo"
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })
  })

  it('shows empty state when no logs exist', async () => {
    vi.mocked(api.getLogs).mockRejectedValue({ status: 404 })

    render(
      <LogViewerModal
        isOpen={true}
        onClose={vi.fn()}
        repoId={1}
        repoName="Test Repo"
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/No LLM logs yet/)).toBeInTheDocument()
    })
  })

  it('navigates to next entry when Next button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(
      <LogViewerModal
        isOpen={true}
        onClose={vi.fn()}
        repoId={1}
        repoName="Test Repo"
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /next/i }))

    expect(screen.getByText(/Entry 2 of 2/)).toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)
    const onClose = vi.fn()

    render(
      <LogViewerModal
        isOpen={true}
        onClose={onClose}
        repoId={1}
        repoName="Test Repo"
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/LLM Logs/)).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /close/i }))

    expect(onClose).toHaveBeenCalled()
  })

  it('shows delete confirmation when delete button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)

    render(
      <LogViewerModal
        isOpen={true}
        onClose={vi.fn()}
        repoId={1}
        repoName="Test Repo"
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    await userEvent.click(screen.getByRole('button', { name: /delete/i }))

    expect(screen.getByText(/Delete all LLM logs/)).toBeInTheDocument()
  })

  it('deletes logs when confirmed', async () => {
    vi.mocked(api.getLogs).mockResolvedValue(mockLogsResponse)
    vi.mocked(api.deleteLogs).mockResolvedValue({ message: 'Logs deleted' })

    render(
      <LogViewerModal
        isOpen={true}
        onClose={vi.fn()}
        repoId={1}
        repoName="Test Repo"
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Entry 1 of 2/)).toBeInTheDocument()
    })

    // Click delete button
    await userEvent.click(screen.getByRole('button', { name: /delete/i }))

    // Confirm deletion
    await userEvent.click(screen.getByRole('button', { name: /confirm/i }))

    await waitFor(() => {
      expect(api.deleteLogs).toHaveBeenCalledWith(1)
    })
  })
})
```

### Step 2: Run tests to verify they fail

```bash
cd frontend && npm run test -- LogViewerModal.test.tsx
```

Expected: FAIL (component doesn't exist)

### Step 3: Create the LogViewerModal component

Create `frontend/src/components/LogViewerModal.tsx`:

```typescript
import { useState, useEffect, useCallback } from 'react'
import { getLogs, deleteLogs } from '../api/client'

interface LogEntry {
  [key: string]: unknown
}

interface LogViewerModalProps {
  isOpen: boolean
  onClose: () => void
  repoId: number
  repoName: string
}

export function LogViewerModal({ isOpen, onClose, repoId, repoName }: LogViewerModalProps) {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isEmpty, setIsEmpty] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')

  const loadLogs = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    setIsEmpty(false)

    try {
      const response = await getLogs(repoId)
      const parsed = response.content
        .split('\n')
        .filter((line) => line.trim())
        .map((line) => {
          try {
            return JSON.parse(line)
          } catch {
            return { error: 'Failed to parse entry' }
          }
        })

      if (parsed.length === 0) {
        setIsEmpty(true)
      } else {
        setEntries(parsed)
        setCurrentIndex(0)
      }
    } catch (e) {
      if ((e as { status?: number }).status === 404) {
        setIsEmpty(true)
      } else {
        setError(e instanceof Error ? e.message : 'Failed to load logs')
      }
    } finally {
      setIsLoading(false)
    }
  }, [repoId])

  useEffect(() => {
    if (isOpen) {
      loadLogs()
    } else {
      // Reset state when modal closes
      setEntries([])
      setCurrentIndex(0)
      setError(null)
      setIsEmpty(false)
      setShowDeleteConfirm(false)
      setSearchTerm('')
    }
  }, [isOpen, loadLogs])

  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return

      switch (e.key) {
        case 'ArrowRight':
        case 'j':
          if (currentIndex < entries.length - 1) {
            setCurrentIndex((i) => i + 1)
          }
          break
        case 'ArrowLeft':
        case 'k':
          if (currentIndex > 0) {
            setCurrentIndex((i) => i - 1)
          }
          break
        case 'Home':
          setCurrentIndex(0)
          e.preventDefault()
          break
        case 'End':
          setCurrentIndex(entries.length - 1)
          e.preventDefault()
          break
        case 'Escape':
          onClose()
          break
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, currentIndex, entries.length, onClose])

  const handleDelete = async () => {
    try {
      await deleteLogs(repoId)
      setEntries([])
      setIsEmpty(true)
      setShowDeleteConfirm(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete logs')
    }
  }

  const handleSearch = () => {
    if (!searchTerm) return

    const searchLower = searchTerm.toLowerCase()
    for (let i = currentIndex + 1; i < entries.length; i++) {
      if (JSON.stringify(entries[i]).toLowerCase().includes(searchLower)) {
        setCurrentIndex(i)
        return
      }
    }
    // Wrap around
    for (let i = 0; i <= currentIndex; i++) {
      if (JSON.stringify(entries[i]).toLowerCase().includes(searchLower)) {
        setCurrentIndex(i)
        return
      }
    }
  }

  if (!isOpen) return null

  const currentEntry = entries[currentIndex]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl mx-4 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              LLM Logs
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">{repoName}</p>
          </div>
          <div className="flex items-center space-x-2">
            {!isEmpty && entries.length > 0 && (
              <>
                <button
                  onClick={loadLogs}
                  className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
                  title="Refresh"
                  aria-label="refresh"
                >
                  <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
                {!showDeleteConfirm ? (
                  <button
                    onClick={() => setShowDeleteConfirm(true)}
                    className="p-2 rounded-md hover:bg-red-100 dark:hover:bg-red-900/30"
                    title="Delete logs"
                    aria-label="delete"
                  >
                    <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                ) : (
                  <div className="flex items-center space-x-2 bg-red-50 dark:bg-red-900/30 px-3 py-1 rounded-md">
                    <span className="text-sm text-red-700 dark:text-red-300">Delete all LLM logs?</span>
                    <button
                      onClick={() => setShowDeleteConfirm(false)}
                      className="px-2 py-1 text-xs font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 rounded"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleDelete}
                      className="px-2 py-1 text-xs font-medium text-white bg-red-600 hover:bg-red-700 rounded"
                      aria-label="confirm"
                    >
                      Delete
                    </button>
                  </div>
                )}
              </>
            )}
            <button
              onClick={onClose}
              className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
              aria-label="close"
            >
              <svg className="w-5 h-5 text-gray-600 dark:text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <div className="flex-1 flex flex-col items-center justify-center p-8">
            <p className="text-red-600 dark:text-red-400 mb-4">{error}</p>
            <button
              onClick={loadLogs}
              className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty state */}
        {isEmpty && !isLoading && !error && (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <svg className="w-16 h-16 text-gray-300 dark:text-gray-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
              No LLM logs yet for this repository
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Logs are created when you generate documentation or use Q&A
            </p>
          </div>
        )}

        {/* Content */}
        {!isLoading && !error && !isEmpty && entries.length > 0 && (
          <>
            {/* Controls */}
            <div className="px-6 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setCurrentIndex(0)}
                  disabled={currentIndex === 0}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="first"
                >
                  First
                </button>
                <button
                  onClick={() => setCurrentIndex((i) => i - 1)}
                  disabled={currentIndex === 0}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="previous"
                >
                  Prev
                </button>
                <button
                  onClick={() => setCurrentIndex((i) => i + 1)}
                  disabled={currentIndex === entries.length - 1}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="next"
                >
                  Next
                </button>
                <button
                  onClick={() => setCurrentIndex(entries.length - 1)}
                  disabled={currentIndex === entries.length - 1}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="last"
                >
                  Last
                </button>
              </div>

              <span className="text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 px-3 py-1.5 rounded-md">
                Entry {currentIndex + 1} of {entries.length}
              </span>

              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Search..."
                  className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md dark:bg-gray-700 dark:text-gray-100"
                />
                <button
                  onClick={handleSearch}
                  className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-md"
                >
                  Find
                </button>
              </div>
            </div>

            {/* Entry metadata */}
            {currentEntry && (
              <div className="px-6 py-2 border-b border-gray-200 dark:border-gray-700 flex flex-wrap gap-4 text-sm">
                {currentEntry.timestamp && (
                  <div>
                    <span className="font-medium text-gray-700 dark:text-gray-300">Timestamp: </span>
                    <span className="text-gray-600 dark:text-gray-400">{String(currentEntry.timestamp)}</span>
                  </div>
                )}
                {currentEntry.provider && (
                  <div>
                    <span className="font-medium text-gray-700 dark:text-gray-300">Provider: </span>
                    <span className="text-gray-600 dark:text-gray-400">{String(currentEntry.provider)}</span>
                  </div>
                )}
                {currentEntry.model && (
                  <div>
                    <span className="font-medium text-gray-700 dark:text-gray-300">Model: </span>
                    <span className="text-gray-600 dark:text-gray-400">{String(currentEntry.model)}</span>
                  </div>
                )}
              </div>
            )}

            {/* JSON display */}
            <div className="flex-1 overflow-auto p-6">
              <pre className="bg-gray-900 dark:bg-gray-950 text-gray-100 p-4 rounded-lg text-sm font-mono overflow-x-auto whitespace-pre-wrap">
                <JsonDisplay data={currentEntry} />
              </pre>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function JsonDisplay({ data, indent = 0 }: { data: unknown; indent?: number }) {
  const spaces = '  '.repeat(indent)

  if (data === null) return <span className="text-purple-400">null</span>
  if (typeof data === 'boolean') return <span className="text-purple-400">{String(data)}</span>
  if (typeof data === 'number') return <span className="text-green-400">{data}</span>
  if (typeof data === 'string') return <span className="text-amber-400">"{data}"</span>

  if (Array.isArray(data)) {
    if (data.length === 0) return <span>[]</span>
    return (
      <>
        {'[\n'}
        {data.map((item, i) => (
          <span key={i}>
            {spaces}  <JsonDisplay data={item} indent={indent + 1} />
            {i < data.length - 1 ? ',' : ''}
            {'\n'}
          </span>
        ))}
        {spaces}]
      </>
    )
  }

  if (typeof data === 'object') {
    const entries = Object.entries(data as Record<string, unknown>)
    if (entries.length === 0) return <span>{'{}'}</span>
    return (
      <>
        {'{\n'}
        {entries.map(([key, value], i) => (
          <span key={key}>
            {spaces}  <span className="text-blue-400">"{key}"</span>: <JsonDisplay data={value} indent={indent + 1} />
            {i < entries.length - 1 ? ',' : ''}
            {'\n'}
          </span>
        ))}
        {spaces}{'}'}
      </>
    )
  }

  return <span>{String(data)}</span>
}
```

### Step 4: Run tests to verify they pass

```bash
cd frontend && npm run test -- LogViewerModal.test.tsx
```

Expected: All tests pass

### Step 5: Commit

```bash
git add frontend/src/components/LogViewerModal.tsx frontend/src/components/LogViewerModal.test.tsx
git commit -m "feat(frontend): add LogViewerModal component

Modal for viewing LLM query logs with navigation, search, and delete."
```

---

## Task 4: Frontend - Integrate into TopBar

**Files:**
- Modify: `frontend/src/components/TopBar.tsx`
- Modify: `frontend/src/components/TopBar.test.tsx`

### Step 1: Add failing tests

Add to `frontend/src/components/TopBar.test.tsx`:

```typescript
// Add to imports
vi.mock('../api/client', () => ({
  getRepoStatus: vi.fn(),
  getWikiTree: vi.fn(),
  getIndexableItems: vi.fn(),
  updateOyaignore: vi.fn(),
  getLogs: vi.fn(),
  deleteLogs: vi.fn(),
}))

// Add to imports from stores
import { useReposStore } from '../stores'
import { initialState as reposInitial } from '../stores/reposStore'

// Add to beforeEach
useReposStore.setState(reposInitial)

// Add new describe block
describe('Log Viewer Button', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.getRepoStatus).mockResolvedValue(mockRepoStatus)
    vi.mocked(api.getWikiTree).mockResolvedValue(mockWikiTree)

    useWikiStore.setState({
      repoStatus: mockRepoStatus,
      wikiTree: mockWikiTree,
      isLoading: false,
      error: null,
    })
  })

  it('shows log viewer button when a repo is active', async () => {
    useReposStore.setState({
      activeRepo: {
        id: 1,
        origin_url: 'https://github.com/test/repo',
        source_type: 'github',
        local_path: 'github.com/test/repo',
        display_name: 'Test Repo',
        head_commit: 'abc123',
        branch: 'main',
        created_at: null,
        last_pulled: null,
        last_generated: null,
        generation_duration_secs: null,
        files_processed: null,
        pages_generated: null,
        status: 'ready',
        error_message: null,
      },
    })

    renderTopBar()

    expect(screen.getByRole('button', { name: /view logs/i })).toBeInTheDocument()
  })

  it('hides log viewer button when no repo is active', async () => {
    useReposStore.setState({
      activeRepo: null,
    })

    renderTopBar()

    expect(screen.queryByRole('button', { name: /view logs/i })).not.toBeInTheDocument()
  })

  it('opens LogViewerModal when log button is clicked', async () => {
    vi.mocked(api.getLogs).mockResolvedValue({
      content: '{"test": true}\n',
      size_bytes: 15,
      entry_count: 1,
    })

    useReposStore.setState({
      activeRepo: {
        id: 1,
        origin_url: 'https://github.com/test/repo',
        source_type: 'github',
        local_path: 'github.com/test/repo',
        display_name: 'Test Repo',
        head_commit: 'abc123',
        branch: 'main',
        created_at: null,
        last_pulled: null,
        last_generated: null,
        generation_duration_secs: null,
        files_processed: null,
        pages_generated: null,
        status: 'ready',
        error_message: null,
      },
    })

    renderTopBar()

    await userEvent.click(screen.getByRole('button', { name: /view logs/i }))

    await waitFor(() => {
      expect(screen.getByText(/LLM Logs/)).toBeInTheDocument()
    })
  })
})
```

### Step 2: Run tests to verify they fail

```bash
cd frontend && npm run test -- TopBar.test.tsx
```

Expected: FAIL (button doesn't exist)

### Step 3: Update TopBar component

In `frontend/src/components/TopBar.tsx`:

Add import at top:

```typescript
import { LogViewerModal } from './LogViewerModal'
import { useReposStore } from '../stores'
```

Add state inside component:

```typescript
const [isLogViewerOpen, setIsLogViewerOpen] = useState(false)
const activeRepo = useReposStore((s) => s.activeRepo)
```

Add button in right section (before dark mode toggle):

```typescript
{activeRepo && (
  <button
    onClick={() => setIsLogViewerOpen(true)}
    className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
    title="View LLM logs"
    aria-label="view logs"
  >
    <svg
      className="w-5 h-5 text-gray-600 dark:text-gray-300"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  </button>
)}
```

Add modal at end of component (before closing `</header>`):

```typescript
{/* Log Viewer Modal */}
{activeRepo && (
  <LogViewerModal
    isOpen={isLogViewerOpen}
    onClose={() => setIsLogViewerOpen(false)}
    repoId={activeRepo.id}
    repoName={activeRepo.display_name}
  />
)}
```

### Step 4: Run tests to verify they pass

```bash
cd frontend && npm run test -- TopBar.test.tsx
```

Expected: All tests pass

### Step 5: Run all frontend tests

```bash
cd frontend && npm run test
```

Expected: All tests pass

### Step 6: Commit

```bash
git add frontend/src/components/TopBar.tsx frontend/src/components/TopBar.test.tsx
git commit -m "feat(frontend): add log viewer button to TopBar

Opens LogViewerModal for the active repository."
```

---

## Task 5: End-to-End Verification

**Files:** None (manual testing)

### Step 1: Start the backend

```bash
cd backend && uvicorn oya.main:app --reload
```

### Step 2: Start the frontend

```bash
cd frontend && npm run dev
```

### Step 3: Manual test checklist

1. [ ] Add a repository
2. [ ] Generate documentation (creates logs)
3. [ ] Log button appears in TopBar
4. [ ] Click log button opens modal
5. [ ] Entries display with navigation
6. [ ] Search finds entries
7. [ ] Keyboard shortcuts work (arrows, j/k, Escape)
8. [ ] Delete logs works with confirmation
9. [ ] Empty state shows after deletion
10. [ ] Dark mode styling correct
11. [ ] Light mode styling correct

### Step 4: Final commit (if any fixes needed)

```bash
git add -A
git commit -m "fix: address issues found in e2e testing"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Backend log endpoints | `logs.py`, `main.py`, `test_logs.py` |
| 2 | Frontend API client | `client.ts`, `types/index.ts` |
| 3 | LogViewerModal component | `LogViewerModal.tsx`, `LogViewerModal.test.tsx` |
| 4 | TopBar integration | `TopBar.tsx`, `TopBar.test.tsx` |
| 5 | E2E verification | Manual testing |
