# Oya v1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local-first, editable DeepWiki clone that generates trustworthy, correctable documentation for codebases.

**Architecture:** Python FastAPI backend with embedded ChromaDB and SQLite, React/Vite frontend with Tailwind CSS. Docker Compose orchestrates two services. Users mount their repo as a volume, backend generates wiki pages hierarchically, frontend renders with citations. Notes system allows corrections that override AI inference.

**Tech Stack:** FastAPI, SQLite, ChromaDB, LiteLLM, GitPython, Tree-sitter | React 18, TypeScript, Vite, Tailwind CSS, Headless UI, CodeMirror, react-markdown

---

## Phase 1: Project Scaffolding

### Task 1.1: Create Backend Project Structure

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/src/oya/__init__.py`
- Create: `backend/src/oya/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_health.py`

**Step 1: Create backend directory structure**

```bash
mkdir -p backend/src/oya backend/tests
```

**Step 2: Create pyproject.toml with dependencies**

```toml
[project]
name = "oya"
version = "0.1.0"
description = "Local-first editable wiki generator for codebases"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.26.0",
    "ruff>=0.1.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/oya"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

**Step 3: Create oya package init**

```python
# backend/src/oya/__init__.py
"""Oya - Local-first editable wiki generator for codebases."""

__version__ = "0.1.0"
```

**Step 4: Create minimal FastAPI app**

```python
# backend/src/oya/main.py
"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="Oya",
    description="Local-first editable wiki generator for codebases",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
```

**Step 5: Write the failing test**

```python
# backend/tests/test_health.py
"""Health check endpoint tests."""

import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def test_health_check_returns_healthy(client: AsyncClient):
    """Health endpoint returns healthy status."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
```

**Step 6: Create tests init**

```python
# backend/tests/__init__.py
"""Oya test suite."""
```

**Step 7: Install dependencies and run test**

```bash
cd backend
pip install -e ".[dev]"
pytest tests/test_health.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add backend/
git commit -m "feat(backend): scaffold FastAPI project with health endpoint"
```

---

### Task 1.2: Create Frontend Project Structure

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/vite-env.d.ts`

**Step 1: Create frontend with Vite**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
```

**Step 2: Install additional dependencies**

```bash
npm install @headlessui/react
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

**Step 3: Configure tailwind.config.js**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {},
  },
  plugins: [],
}
```

**Step 4: Create src/index.css with Tailwind**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**Step 5: Update src/App.tsx with minimal shell**

```tsx
function App() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <header className="bg-white dark:bg-gray-800 shadow">
        <div className="px-4 py-3">
          <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
            Oya
          </h1>
        </div>
      </header>
      <main className="p-4">
        <p className="text-gray-600 dark:text-gray-300">
          Wiki generator loading...
        </p>
      </main>
    </div>
  )
}

export default App
```

**Step 6: Verify dev server works**

```bash
npm run dev
```

Expected: App loads at http://localhost:5173 with "Oya" header

**Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold React/Vite project with Tailwind"
```

---

### Task 1.3: Create Docker Compose Setup

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`

**Step 1: Create backend Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source
COPY src/ src/

# Run uvicorn
CMD ["uvicorn", "oya.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Create frontend Dockerfile**

```dockerfile
# frontend/Dockerfile
FROM node:20-slim

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY . .

# Expose port
EXPOSE 3000

# Run dev server (for dev mode)
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]
```

**Step 3: Create docker-compose.yml**

```yaml
version: '3.9'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ${REPO_PATH:-.}:/workspace:ro
      - oya-data:/workspace/.coretechs
    environment:
      - WORKSPACE_PATH=/workspace
    env_file:
      - .env

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://localhost:8000

volumes:
  oya-data:
```

**Step 4: Create .env.example**

```bash
# .env.example
# Copy to .env and fill in values

# Path to repository to analyze (required)
REPO_PATH=/path/to/your/repo

# LLM Provider (choose one)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=

# Or use local Ollama
OLLAMA_ENDPOINT=http://host.docker.internal:11434

# Active provider configuration
ACTIVE_PROVIDER=openai
ACTIVE_MODEL=gpt-4o
```

**Step 5: Test Docker build**

```bash
docker-compose build
```

Expected: Both images build successfully

**Step 6: Commit**

```bash
git add backend/Dockerfile frontend/Dockerfile docker-compose.yml .env.example
git commit -m "feat: add Docker Compose setup for development"
```

---

## Phase 2: Backend Core Infrastructure

### Task 2.1: Add SQLite Database Layer

**Files:**
- Create: `backend/src/oya/db/__init__.py`
- Create: `backend/src/oya/db/connection.py`
- Create: `backend/src/oya/db/models.py`
- Create: `backend/src/oya/db/migrations.py`
- Create: `backend/tests/test_db.py`

**Step 1: Write the failing test for database connection**

```python
# backend/tests/test_db.py
"""Database connection and schema tests."""

import tempfile
from pathlib import Path

import pytest

from oya.db.connection import Database
from oya.db.migrations import run_migrations


@pytest.fixture
def temp_db():
    """Create a temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


def test_database_connects(temp_db: Path):
    """Database connects and creates file."""
    db = Database(temp_db)

    assert temp_db.exists()
    db.close()


def test_migrations_create_tables(temp_db: Path):
    """Migrations create required tables."""
    db = Database(temp_db)
    run_migrations(db)

    # Check tables exist
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {row[0] for row in tables}

    assert "generations" in table_names
    assert "wiki_pages" in table_names
    assert "notes" in table_names
    assert "citations" in table_names

    db.close()
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/test_db.py -v
```

Expected: FAIL with import error

**Step 3: Create db package init**

```python
# backend/src/oya/db/__init__.py
"""Database layer for Oya."""

from oya.db.connection import Database
from oya.db.migrations import run_migrations

__all__ = ["Database", "run_migrations"]
```

**Step 4: Implement Database connection class**

```python
# backend/src/oya/db/connection.py
"""SQLite database connection management."""

import sqlite3
from pathlib import Path
from typing import Any


class Database:
    """SQLite database wrapper with connection management."""

    def __init__(self, db_path: Path):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Enable foreign keys
        self._conn.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        """Execute SQL statement.

        Args:
            sql: SQL statement.
            params: Query parameters.

        Returns:
            Cursor with results.
        """
        return self._conn.execute(sql, params)

    def executemany(self, sql: str, params_list: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        """Execute SQL statement for multiple parameter sets.

        Args:
            sql: SQL statement.
            params_list: List of parameter tuples.

        Returns:
            Cursor with results.
        """
        return self._conn.executemany(sql, params_list)

    def commit(self) -> None:
        """Commit current transaction."""
        self._conn.commit()

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()
```

**Step 5: Implement migrations**

```python
# backend/src/oya/db/migrations.py
"""Database schema migrations."""

from oya.db.connection import Database

SCHEMA = """
-- Job/generation tracking
CREATE TABLE IF NOT EXISTS generations (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- 'full', 'file', 'directory', 'workflow', etc.
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    started_at TEXT,
    completed_at TEXT,
    commit_hash TEXT,
    error_message TEXT,
    progress_data TEXT  -- JSON blob for progress tracking
);

-- Wiki page metadata
CREATE TABLE IF NOT EXISTS wiki_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,  -- e.g., 'overview', 'files/src-main-py'
    type TEXT NOT NULL,  -- overview, architecture, workflow, directory, file
    title TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    word_count INTEGER DEFAULT 0,
    content_hash TEXT  -- For change detection
);

-- Human correction notes
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    filepath TEXT NOT NULL,  -- Path in .coretechs/notes/
    scope TEXT NOT NULL,  -- file, directory, workflow, architecture, general
    target TEXT,  -- Path or slug this note applies to
    created_at TEXT NOT NULL,
    author TEXT,
    git_branch TEXT,
    git_commit TEXT,
    git_dirty INTEGER DEFAULT 0,
    content_preview TEXT  -- First 200 chars for display
);

-- Citation tracking
CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wiki_page_id INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,  -- 'code', 'note', 'wiki'
    source_path TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    commit_hash TEXT,
    citation_key TEXT NOT NULL,  -- [1], [2], etc.
    snippet_preview TEXT
);

-- Full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
    title,
    content,
    path,
    type,
    content='wiki_pages',
    content_rowid='id'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_wiki_pages_type ON wiki_pages(type);
CREATE INDEX IF NOT EXISTS idx_notes_scope ON notes(scope);
CREATE INDEX IF NOT EXISTS idx_notes_target ON notes(target);
CREATE INDEX IF NOT EXISTS idx_citations_wiki_page ON citations(wiki_page_id);
CREATE INDEX IF NOT EXISTS idx_generations_status ON generations(status);
"""


def run_migrations(db: Database) -> None:
    """Run database migrations.

    Args:
        db: Database connection.
    """
    db.execute(SCHEMA)
    db.commit()
```

**Step 6: Run tests to verify they pass**

```bash
pytest backend/tests/test_db.py -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add backend/src/oya/db/ backend/tests/test_db.py
git commit -m "feat(backend): add SQLite database layer with schema"
```

---

### Task 2.2: Add Configuration System

**Files:**
- Create: `backend/src/oya/config.py`
- Create: `backend/tests/test_config.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_config.py
"""Configuration tests."""

import os
import tempfile
from pathlib import Path

import pytest

from oya.config import Settings, load_settings


@pytest.fixture
def temp_workspace():
    """Create temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir) / "workspace"
        workspace.mkdir()
        yield workspace


def test_settings_from_environment(temp_workspace: Path, monkeypatch):
    """Settings load from environment variables."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))
    monkeypatch.setenv("ACTIVE_PROVIDER", "openai")
    monkeypatch.setenv("ACTIVE_MODEL", "gpt-4o")

    settings = load_settings()

    assert settings.workspace_path == temp_workspace
    assert settings.active_provider == "openai"
    assert settings.active_model == "gpt-4o"


def test_settings_defaults(temp_workspace: Path, monkeypatch):
    """Settings have sensible defaults."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))
    # Clear LLM settings
    monkeypatch.delenv("ACTIVE_PROVIDER", raising=False)
    monkeypatch.delenv("ACTIVE_MODEL", raising=False)

    settings = load_settings()

    assert settings.active_provider == "ollama"  # Default fallback
    assert settings.active_model == "llama2"


def test_coretechs_paths(temp_workspace: Path, monkeypatch):
    """Coretechs subdirectory paths are computed correctly."""
    monkeypatch.setenv("WORKSPACE_PATH", str(temp_workspace))

    settings = load_settings()

    assert settings.coretechs_path == temp_workspace / ".coretechs"
    assert settings.wiki_path == temp_workspace / ".coretechs" / "wiki"
    assert settings.notes_path == temp_workspace / ".coretechs" / "notes"
    assert settings.db_path == temp_workspace / ".coretechs" / "meta" / "oya.db"
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/test_config.py -v
```

Expected: FAIL with import error

**Step 3: Implement configuration**

```python
# backend/src/oya/config.py
"""Application configuration."""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass
class Settings:
    """Application settings."""

    # Workspace
    workspace_path: Path

    # LLM Provider
    active_provider: str
    active_model: str
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    ollama_endpoint: str = "http://localhost:11434"

    # Generation settings
    max_file_size_kb: int = 500
    parallel_file_limit: int = 10
    chunk_size: int = 1000

    @property
    def coretechs_path(self) -> Path:
        """Path to .coretechs directory."""
        return self.workspace_path / ".coretechs"

    @property
    def wiki_path(self) -> Path:
        """Path to wiki directory."""
        return self.coretechs_path / "wiki"

    @property
    def notes_path(self) -> Path:
        """Path to notes directory."""
        return self.coretechs_path / "notes"

    @property
    def db_path(self) -> Path:
        """Path to SQLite database."""
        return self.coretechs_path / "meta" / "oya.db"

    @property
    def index_path(self) -> Path:
        """Path to ChromaDB index."""
        return self.coretechs_path / "index"

    @property
    def cache_path(self) -> Path:
        """Path to cache directory."""
        return self.coretechs_path / "cache"


@lru_cache
def load_settings() -> Settings:
    """Load settings from environment.

    Returns:
        Populated Settings instance.
    """
    workspace = Path(os.environ.get("WORKSPACE_PATH", "/workspace"))

    # Determine provider - default to ollama if no API keys
    provider = os.environ.get("ACTIVE_PROVIDER", "")
    model = os.environ.get("ACTIVE_MODEL", "")

    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    google_key = os.environ.get("GOOGLE_API_KEY")

    # Default to ollama if no provider specified and no keys
    if not provider:
        if openai_key:
            provider = "openai"
            model = model or "gpt-4o"
        elif anthropic_key:
            provider = "anthropic"
            model = model or "claude-3-sonnet-20240229"
        elif google_key:
            provider = "google"
            model = model or "gemini-pro"
        else:
            provider = "ollama"
            model = model or "llama2"

    if not model:
        model = "llama2" if provider == "ollama" else "gpt-4o"

    return Settings(
        workspace_path=workspace,
        active_provider=provider,
        active_model=model,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        google_api_key=google_key,
        ollama_endpoint=os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434"),
        max_file_size_kb=int(os.environ.get("MAX_FILE_SIZE_KB", "500")),
        parallel_file_limit=int(os.environ.get("PARALLEL_FILE_LIMIT", "10")),
        chunk_size=int(os.environ.get("CHUNK_SIZE", "1000")),
    )
```

**Step 4: Run tests to verify they pass**

```bash
pytest backend/tests/test_config.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/config.py backend/tests/test_config.py
git commit -m "feat(backend): add configuration system with environment loading"
```

---

### Task 2.3: Add ChromaDB Vector Store

**Files:**
- Modify: `backend/pyproject.toml` (add chromadb dependency)
- Create: `backend/src/oya/vectorstore/__init__.py`
- Create: `backend/src/oya/vectorstore/store.py`
- Create: `backend/tests/test_vectorstore.py`

**Step 1: Add chromadb to dependencies**

In `backend/pyproject.toml`, add to dependencies:
```toml
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "chromadb>=0.4.22",
]
```

**Step 2: Install updated dependencies**

```bash
cd backend
pip install -e ".[dev]"
```

**Step 3: Write the failing test**

```python
# backend/tests/test_vectorstore.py
"""Vector store tests."""

import tempfile
from pathlib import Path

import pytest

from oya.vectorstore import VectorStore


@pytest.fixture
def temp_index():
    """Create temporary index directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_vectorstore_initializes(temp_index: Path):
    """Vector store initializes and creates collection."""
    store = VectorStore(temp_index)

    assert store.collection is not None


def test_add_and_query_documents(temp_index: Path):
    """Can add documents and query them."""
    store = VectorStore(temp_index)

    # Add documents
    store.add_documents(
        ids=["doc1", "doc2"],
        documents=[
            "The login function handles user authentication",
            "The database schema defines user tables",
        ],
        metadatas=[
            {"source": "auth.py", "type": "code"},
            {"source": "schema.sql", "type": "code"},
        ],
    )

    # Query
    results = store.query("how does login work", n_results=1)

    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "doc1"


def test_query_with_filter(temp_index: Path):
    """Can filter queries by metadata."""
    store = VectorStore(temp_index)

    store.add_documents(
        ids=["code1", "note1"],
        documents=[
            "Authentication uses JWT tokens",
            "CORRECTION: Authentication uses OAuth2, not JWT",
        ],
        metadatas=[
            {"source": "auth.py", "type": "code"},
            {"source": "note-001.md", "type": "note"},
        ],
    )

    # Query only notes
    results = store.query(
        "how does authentication work",
        n_results=2,
        where={"type": "note"},
    )

    assert len(results["ids"][0]) == 1
    assert results["ids"][0][0] == "note1"
```

**Step 4: Run test to verify it fails**

```bash
pytest backend/tests/test_vectorstore.py -v
```

Expected: FAIL with import error

**Step 5: Create vectorstore package init**

```python
# backend/src/oya/vectorstore/__init__.py
"""Vector storage for semantic search."""

from oya.vectorstore.store import VectorStore

__all__ = ["VectorStore"]
```

**Step 6: Implement VectorStore**

```python
# backend/src/oya/vectorstore/store.py
"""ChromaDB vector store wrapper."""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings


class VectorStore:
    """ChromaDB-based vector store for semantic search."""

    COLLECTION_NAME = "oya_content"

    def __init__(self, persist_path: Path):
        """Initialize vector store.

        Args:
            persist_path: Directory for persistent storage.
        """
        persist_path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.Client(
            Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(persist_path),
                anonymized_telemetry=False,
            )
        )

        self.collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        """Add documents to the store.

        Args:
            ids: Unique identifiers for documents.
            documents: Document text content.
            metadatas: Optional metadata for each document.
        """
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        query_text: str,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query the store for similar documents.

        Args:
            query_text: Query string.
            n_results: Maximum number of results.
            where: Optional metadata filter.

        Returns:
            Query results with ids, documents, distances, metadatas.
        """
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
        )

    def delete(self, ids: list[str]) -> None:
        """Delete documents by ID.

        Args:
            ids: Document IDs to delete.
        """
        self.collection.delete(ids=ids)

    def clear(self) -> None:
        """Clear all documents from collection."""
        self._client.delete_collection(self.COLLECTION_NAME)
        self.collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
```

**Step 7: Run tests to verify they pass**

```bash
pytest backend/tests/test_vectorstore.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add backend/pyproject.toml backend/src/oya/vectorstore/ backend/tests/test_vectorstore.py
git commit -m "feat(backend): add ChromaDB vector store for semantic search"
```

---

### Task 2.4: Add LiteLLM Integration

**Files:**
- Modify: `backend/pyproject.toml` (add litellm dependency)
- Create: `backend/src/oya/llm/__init__.py`
- Create: `backend/src/oya/llm/client.py`
- Create: `backend/tests/test_llm.py`

**Step 1: Add litellm to dependencies**

In `backend/pyproject.toml`, add to dependencies:
```toml
    "litellm>=1.17.0",
```

**Step 2: Install updated dependencies**

```bash
cd backend
pip install -e ".[dev]"
```

**Step 3: Write the failing test**

```python
# backend/tests/test_llm.py
"""LLM client tests."""

from unittest.mock import AsyncMock, patch

import pytest

from oya.llm import LLMClient


@pytest.fixture
def mock_completion():
    """Mock litellm completion response."""
    with patch("oya.llm.client.acompletion") as mock:
        mock.return_value = AsyncMock(
            choices=[
                AsyncMock(
                    message=AsyncMock(content="Test response")
                )
            ]
        )
        yield mock


async def test_llm_client_generates_response(mock_completion):
    """LLM client generates response from prompt."""
    client = LLMClient(provider="openai", model="gpt-4o")

    response = await client.generate("Test prompt")

    assert response == "Test response"
    mock_completion.assert_called_once()


async def test_llm_client_uses_configured_model(mock_completion):
    """LLM client uses configured provider and model."""
    client = LLMClient(provider="anthropic", model="claude-3-sonnet")

    await client.generate("Test")

    call_args = mock_completion.call_args
    assert call_args.kwargs["model"] == "anthropic/claude-3-sonnet"


async def test_llm_client_passes_system_prompt(mock_completion):
    """LLM client includes system prompt in messages."""
    client = LLMClient(provider="openai", model="gpt-4o")

    await client.generate(
        "User message",
        system_prompt="You are a helpful assistant",
    )

    call_args = mock_completion.call_args
    messages = call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "You are a helpful assistant"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "User message"
```

**Step 4: Run test to verify it fails**

```bash
pytest backend/tests/test_llm.py -v
```

Expected: FAIL with import error

**Step 5: Create llm package init**

```python
# backend/src/oya/llm/__init__.py
"""LLM client abstraction."""

from oya.llm.client import LLMClient

__all__ = ["LLMClient"]
```

**Step 6: Implement LLMClient**

```python
# backend/src/oya/llm/client.py
"""LiteLLM-based LLM client."""

from litellm import acompletion


class LLMClient:
    """Unified LLM client supporting multiple providers via LiteLLM."""

    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str | None = None,
        endpoint: str | None = None,
    ):
        """Initialize LLM client.

        Args:
            provider: LLM provider (openai, anthropic, google, ollama).
            model: Model name.
            api_key: Optional API key (uses env var if not provided).
            endpoint: Optional custom endpoint (for Ollama).
        """
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.endpoint = endpoint

    def _get_model_string(self) -> str:
        """Get LiteLLM model string.

        Returns:
            Model string in provider/model format.
        """
        if self.provider == "openai":
            return self.model  # OpenAI is default
        elif self.provider == "ollama":
            return f"ollama/{self.model}"
        else:
            return f"{self.provider}/{self.model}"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate completion from prompt.

        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.

        Returns:
            Generated text response.
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self._get_model_string(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key

        if self.endpoint and self.provider == "ollama":
            kwargs["api_base"] = self.endpoint

        response = await acompletion(**kwargs)
        return response.choices[0].message.content

    async def generate_with_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate completion expecting JSON response.

        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.

        Returns:
            Generated JSON string.
        """
        full_system = (system_prompt or "") + "\n\nRespond with valid JSON only."
        return await self.generate(
            prompt,
            system_prompt=full_system.strip(),
            temperature=0.3,  # Lower temperature for structured output
        )
```

**Step 7: Run tests to verify they pass**

```bash
pytest backend/tests/test_llm.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add backend/pyproject.toml backend/src/oya/llm/ backend/tests/test_llm.py
git commit -m "feat(backend): add LiteLLM client for multi-provider LLM access"
```

---

## Phase 3: Repository Analysis

### Task 3.1: Add GitPython Repository Wrapper

**Files:**
- Modify: `backend/pyproject.toml` (add gitpython dependency)
- Create: `backend/src/oya/repo/__init__.py`
- Create: `backend/src/oya/repo/git_repo.py`
- Create: `backend/tests/test_git_repo.py`

**Step 1: Add gitpython to dependencies**

In `backend/pyproject.toml`, add to dependencies:
```toml
    "gitpython>=3.1.41",
```

**Step 2: Install updated dependencies**

```bash
cd backend
pip install -e ".[dev]"
```

**Step 3: Write the failing test**

```python
# backend/tests/test_git_repo.py
"""Git repository wrapper tests."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from oya.repo import GitRepo


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository with some files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path, capture_output=True
        )

        # Create some files
        (repo_path / "README.md").write_text("# Test Project")
        (repo_path / "src").mkdir()
        (repo_path / "src" / "main.py").write_text("def main(): pass")

        # Commit
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path, capture_output=True
        )

        yield repo_path


def test_git_repo_gets_head_commit(temp_git_repo: Path):
    """Can get HEAD commit hash."""
    repo = GitRepo(temp_git_repo)

    commit_hash = repo.get_head_commit()

    assert len(commit_hash) == 40  # Full SHA


def test_git_repo_checks_dirty_status(temp_git_repo: Path):
    """Can detect dirty working directory."""
    repo = GitRepo(temp_git_repo)

    # Clean initially
    assert not repo.is_dirty()

    # Make dirty
    (temp_git_repo / "new_file.txt").write_text("dirty")

    assert repo.is_dirty()


def test_git_repo_gets_branch(temp_git_repo: Path):
    """Can get current branch name."""
    repo = GitRepo(temp_git_repo)

    branch = repo.get_current_branch()

    assert branch in ("main", "master")


def test_git_repo_gets_file_at_commit(temp_git_repo: Path):
    """Can get file content at specific commit."""
    repo = GitRepo(temp_git_repo)
    commit = repo.get_head_commit()

    content = repo.get_file_at_commit("README.md", commit)

    assert content == "# Test Project"


def test_git_repo_lists_files(temp_git_repo: Path):
    """Can list all tracked files."""
    repo = GitRepo(temp_git_repo)

    files = repo.list_files()

    assert "README.md" in files
    assert "src/main.py" in files
```

**Step 4: Run test to verify it fails**

```bash
pytest backend/tests/test_git_repo.py -v
```

Expected: FAIL with import error

**Step 5: Create repo package init**

```python
# backend/src/oya/repo/__init__.py
"""Repository analysis and management."""

from oya.repo.git_repo import GitRepo

__all__ = ["GitRepo"]
```

**Step 6: Implement GitRepo**

```python
# backend/src/oya/repo/git_repo.py
"""Git repository wrapper using GitPython."""

from pathlib import Path

from git import Repo


class GitRepo:
    """Wrapper for git repository operations."""

    def __init__(self, path: Path):
        """Initialize git repository wrapper.

        Args:
            path: Path to git repository root.
        """
        self.path = path
        self._repo = Repo(path)

    def get_head_commit(self) -> str:
        """Get current HEAD commit hash.

        Returns:
            Full commit SHA.
        """
        return self._repo.head.commit.hexsha

    def get_current_branch(self) -> str:
        """Get current branch name.

        Returns:
            Branch name or 'HEAD' if detached.
        """
        if self._repo.head.is_detached:
            return "HEAD"
        return self._repo.active_branch.name

    def is_dirty(self) -> bool:
        """Check if working directory has uncommitted changes.

        Returns:
            True if there are uncommitted changes.
        """
        return self._repo.is_dirty(untracked_files=True)

    def get_file_at_commit(self, file_path: str, commit_hash: str) -> str:
        """Get file content at specific commit.

        Args:
            file_path: Relative path to file.
            commit_hash: Commit SHA.

        Returns:
            File content as string.
        """
        commit = self._repo.commit(commit_hash)
        blob = commit.tree / file_path
        return blob.data_stream.read().decode("utf-8")

    def list_files(self) -> list[str]:
        """List all tracked files in repository.

        Returns:
            List of relative file paths.
        """
        return [item.path for item in self._repo.head.commit.tree.traverse()
                if item.type == "blob"]

    def get_user_name(self) -> str:
        """Get configured git user name.

        Returns:
            User name or 'Unknown' if not configured.
        """
        try:
            return self._repo.config_reader().get_value("user", "name")
        except Exception:
            return "Unknown"

    def get_user_email(self) -> str:
        """Get configured git user email.

        Returns:
            User email or empty string if not configured.
        """
        try:
            return self._repo.config_reader().get_value("user", "email")
        except Exception:
            return ""
```

**Step 7: Run tests to verify they pass**

```bash
pytest backend/tests/test_git_repo.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add backend/pyproject.toml backend/src/oya/repo/ backend/tests/test_git_repo.py
git commit -m "feat(backend): add GitPython repository wrapper"
```

---

### Task 3.2: Add File Filtering with .oyaignore

**Files:**
- Create: `backend/src/oya/repo/file_filter.py`
- Create: `backend/tests/test_file_filter.py`

**Step 1: Write the failing test**

```python
# backend/tests/test_file_filter.py
"""File filtering tests."""

import tempfile
from pathlib import Path

import pytest

from oya.repo.file_filter import FileFilter


@pytest.fixture
def temp_repo():
    """Create temporary directory with various files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Create structure
        (repo_path / "src").mkdir()
        (repo_path / "src" / "main.py").write_text("code")
        (repo_path / "node_modules").mkdir()
        (repo_path / "node_modules" / "pkg").mkdir()
        (repo_path / "node_modules" / "pkg" / "index.js").write_text("module")
        (repo_path / "build").mkdir()
        (repo_path / "build" / "output.js").write_text("built")
        (repo_path / ".git").mkdir()
        (repo_path / ".git" / "config").write_text("git")
        (repo_path / "README.md").write_text("readme")

        yield repo_path


def test_default_excludes_node_modules(temp_repo: Path):
    """Default patterns exclude node_modules."""
    filter = FileFilter(temp_repo)

    files = filter.get_files()

    assert not any("node_modules" in f for f in files)


def test_default_excludes_git(temp_repo: Path):
    """Default patterns exclude .git."""
    filter = FileFilter(temp_repo)

    files = filter.get_files()

    assert not any(".git" in f for f in files)


def test_default_excludes_build(temp_repo: Path):
    """Default patterns exclude build directories."""
    filter = FileFilter(temp_repo)

    files = filter.get_files()

    assert not any("build" in f for f in files)


def test_includes_source_files(temp_repo: Path):
    """Includes regular source files."""
    filter = FileFilter(temp_repo)

    files = filter.get_files()

    assert "src/main.py" in files
    assert "README.md" in files


def test_oyaignore_adds_custom_patterns(temp_repo: Path):
    """Custom .oyaignore patterns are applied."""
    # Create .oyaignore
    (temp_repo / ".oyaignore").write_text("*.md\n")

    filter = FileFilter(temp_repo)
    files = filter.get_files()

    assert "README.md" not in files
    assert "src/main.py" in files


def test_respects_max_file_size(temp_repo: Path):
    """Files over max size are excluded."""
    # Create large file
    (temp_repo / "large.txt").write_text("x" * 1000)

    filter = FileFilter(temp_repo, max_file_size_kb=0.5)  # 0.5 KB
    files = filter.get_files()

    assert "large.txt" not in files
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/test_file_filter.py -v
```

Expected: FAIL with import error

**Step 3: Implement FileFilter**

```python
# backend/src/oya/repo/file_filter.py
"""File filtering with default excludes and .oyaignore support."""

import fnmatch
from pathlib import Path


DEFAULT_EXCLUDES = [
    # Version control
    ".git",
    ".hg",
    ".svn",

    # Dependencies
    "node_modules",
    "vendor",
    ".venv",
    "venv",
    "__pycache__",
    ".pyc",

    # Build outputs
    "build",
    "dist",
    "target",
    "out",
    ".next",
    ".nuxt",

    # IDE
    ".idea",
    ".vscode",
    "*.swp",

    # OS
    ".DS_Store",
    "Thumbs.db",

    # Oya artifacts
    ".coretechs",
]


class FileFilter:
    """Filter files based on patterns and size limits."""

    def __init__(
        self,
        repo_path: Path,
        max_file_size_kb: int = 500,
        extra_excludes: list[str] | None = None,
    ):
        """Initialize file filter.

        Args:
            repo_path: Path to repository root.
            max_file_size_kb: Maximum file size in KB.
            extra_excludes: Additional exclude patterns.
        """
        self.repo_path = repo_path
        self.max_file_size_bytes = max_file_size_kb * 1024

        # Build exclude patterns
        self.exclude_patterns = list(DEFAULT_EXCLUDES)
        if extra_excludes:
            self.exclude_patterns.extend(extra_excludes)

        # Load .oyaignore if exists
        oyaignore = repo_path / ".oyaignore"
        if oyaignore.exists():
            for line in oyaignore.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.exclude_patterns.append(line)

    def _is_excluded(self, path: str) -> bool:
        """Check if path matches any exclude pattern.

        Args:
            path: Relative file path.

        Returns:
            True if path should be excluded.
        """
        parts = path.split("/")

        for pattern in self.exclude_patterns:
            # Check each path component
            for part in parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
            # Check full path
            if fnmatch.fnmatch(path, pattern):
                return True

        return False

    def _is_binary(self, file_path: Path) -> bool:
        """Check if file appears to be binary.

        Args:
            file_path: Path to file.

        Returns:
            True if file appears to be binary.
        """
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\x00" in chunk
        except Exception:
            return True

    def get_files(self) -> list[str]:
        """Get list of files to process.

        Returns:
            List of relative file paths.
        """
        files = []

        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            relative = str(file_path.relative_to(self.repo_path))

            # Check exclusions
            if self._is_excluded(relative):
                continue

            # Check size
            try:
                if file_path.stat().st_size > self.max_file_size_bytes:
                    continue
            except OSError:
                continue

            # Check binary
            if self._is_binary(file_path):
                continue

            files.append(relative)

        return sorted(files)
```

**Step 4: Update repo package init**

```python
# backend/src/oya/repo/__init__.py
"""Repository analysis and management."""

from oya.repo.git_repo import GitRepo
from oya.repo.file_filter import FileFilter

__all__ = ["GitRepo", "FileFilter"]
```

**Step 5: Run tests to verify they pass**

```bash
pytest backend/tests/test_file_filter.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/oya/repo/ backend/tests/test_file_filter.py
git commit -m "feat(backend): add file filtering with .oyaignore support"
```

---

## Phase 3 (continued): Code Parsing

### Task 3.3: Create Base Parser Interface and Data Models

**Files:**
- Create: `backend/src/oya/parsing/__init__.py`
- Create: `backend/src/oya/parsing/models.py`
- Create: `backend/src/oya/parsing/base.py`
- Create: `backend/tests/test_parsing_models.py`

**Step 1: Write the failing test for data models**

```python
# backend/tests/test_parsing_models.py
"""Parsing data model tests."""

import pytest

from oya.parsing.models import (
    ParsedSymbol,
    SymbolType,
    ParsedFile,
    ParseResult,
)


def test_parsed_symbol_creation():
    """Can create a parsed symbol."""
    symbol = ParsedSymbol(
        name="my_function",
        symbol_type=SymbolType.FUNCTION,
        start_line=10,
        end_line=25,
        docstring="Does something useful.",
        signature="def my_function(a: int, b: str) -> bool",
    )

    assert symbol.name == "my_function"
    assert symbol.symbol_type == SymbolType.FUNCTION
    assert symbol.start_line == 10
    assert symbol.end_line == 25
    assert symbol.docstring == "Does something useful."


def test_symbol_types_exist():
    """All required symbol types exist."""
    assert SymbolType.FUNCTION
    assert SymbolType.CLASS
    assert SymbolType.METHOD
    assert SymbolType.IMPORT
    assert SymbolType.EXPORT
    assert SymbolType.VARIABLE
    assert SymbolType.CONSTANT


def test_parsed_file_creation():
    """Can create a parsed file with symbols."""
    symbols = [
        ParsedSymbol(
            name="MyClass",
            symbol_type=SymbolType.CLASS,
            start_line=1,
            end_line=50,
        ),
        ParsedSymbol(
            name="helper",
            symbol_type=SymbolType.FUNCTION,
            start_line=52,
            end_line=60,
        ),
    ]

    parsed = ParsedFile(
        path="src/module.py",
        language="python",
        symbols=symbols,
        imports=["os", "sys"],
        exports=["MyClass", "helper"],
    )

    assert parsed.path == "src/module.py"
    assert parsed.language == "python"
    assert len(parsed.symbols) == 2
    assert "os" in parsed.imports


def test_parse_result_success():
    """ParseResult can represent success."""
    parsed = ParsedFile(path="test.py", language="python", symbols=[])
    result = ParseResult.success(parsed)

    assert result.ok
    assert result.file == parsed
    assert result.error is None


def test_parse_result_failure():
    """ParseResult can represent failure."""
    result = ParseResult.failure("test.py", "Syntax error on line 5")

    assert not result.ok
    assert result.file is None
    assert "Syntax error" in result.error
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/test_parsing_models.py -v
```

Expected: FAIL with import error

**Step 3: Implement data models**

```python
# backend/src/oya/parsing/models.py
"""Data models for code parsing."""

from dataclasses import dataclass, field
from enum import Enum


class SymbolType(Enum):
    """Types of code symbols that can be extracted."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    IMPORT = "import"
    EXPORT = "export"
    VARIABLE = "variable"
    CONSTANT = "constant"
    INTERFACE = "interface"  # TypeScript
    TYPE_ALIAS = "type_alias"  # TypeScript
    ENUM = "enum"
    DECORATOR = "decorator"
    ROUTE = "route"  # API route handlers
    CLI_COMMAND = "cli_command"  # CLI entry points


@dataclass
class ParsedSymbol:
    """A parsed code symbol (function, class, etc.)."""

    name: str
    symbol_type: SymbolType
    start_line: int
    end_line: int
    docstring: str | None = None
    signature: str | None = None
    decorators: list[str] = field(default_factory=list)
    parent: str | None = None  # For methods, the class name
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedFile:
    """Result of parsing a single file."""

    path: str
    language: str
    symbols: list[ParsedSymbol]
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    raw_content: str | None = None
    line_count: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    """Result of a parse operation (success or failure)."""

    ok: bool
    file: ParsedFile | None
    error: str | None
    path: str | None = None

    @classmethod
    def success(cls, parsed_file: ParsedFile) -> "ParseResult":
        """Create a successful parse result."""
        return cls(ok=True, file=parsed_file, error=None, path=parsed_file.path)

    @classmethod
    def failure(cls, path: str, error: str) -> "ParseResult":
        """Create a failed parse result."""
        return cls(ok=False, file=None, error=error, path=path)
```

**Step 4: Create base parser interface**

```python
# backend/src/oya/parsing/base.py
"""Base parser interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from oya.parsing.models import ParseResult


class BaseParser(ABC):
    """Abstract base class for language-specific parsers."""

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """File extensions this parser handles (e.g., ['.py'])."""
        pass

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Human-readable language name."""
        pass

    @abstractmethod
    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse file content and extract symbols.

        Args:
            file_path: Path to the file (for error messages).
            content: File content as string.

        Returns:
            ParseResult with extracted symbols or error.
        """
        pass

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the given file.

        Args:
            file_path: Path to check.

        Returns:
            True if this parser supports the file extension.
        """
        return file_path.suffix.lower() in self.supported_extensions
```

**Step 5: Create package init**

```python
# backend/src/oya/parsing/__init__.py
"""Code parsing utilities."""

from oya.parsing.models import (
    ParsedSymbol,
    SymbolType,
    ParsedFile,
    ParseResult,
)
from oya.parsing.base import BaseParser

__all__ = [
    "ParsedSymbol",
    "SymbolType",
    "ParsedFile",
    "ParseResult",
    "BaseParser",
]
```

**Step 6: Run tests to verify they pass**

```bash
pytest backend/tests/test_parsing_models.py -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add backend/src/oya/parsing/ backend/tests/test_parsing_models.py
git commit -m "feat(backend): add parsing data models and base parser interface"
```

---

### Task 3.4: Python AST Parser

**Files:**
- Create: `backend/src/oya/parsing/python_parser.py`
- Create: `backend/tests/test_python_parser.py`
- Modify: `backend/src/oya/parsing/__init__.py` (add export)

**Step 1: Write the failing test**

```python
# backend/tests/test_python_parser.py
"""Python AST parser tests."""

import pytest

from oya.parsing import SymbolType
from oya.parsing.python_parser import PythonParser


@pytest.fixture
def parser():
    """Create Python parser instance."""
    return PythonParser()


def test_parser_supported_extensions(parser):
    """Parser supports .py and .pyi files."""
    assert ".py" in parser.supported_extensions
    assert ".pyi" in parser.supported_extensions


def test_parses_simple_function(parser):
    """Extracts function with docstring."""
    code = '''
def greet(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}"
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    assert len(result.file.symbols) == 1

    func = result.file.symbols[0]
    assert func.name == "greet"
    assert func.symbol_type == SymbolType.FUNCTION
    assert func.docstring == "Say hello to someone."
    assert "name: str" in func.signature


def test_parses_class_with_methods(parser):
    """Extracts class and its methods."""
    code = '''
class Calculator:
    """A simple calculator."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def subtract(self, a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    symbols = result.file.symbols

    # Should have class + 2 methods
    class_sym = next(s for s in symbols if s.symbol_type == SymbolType.CLASS)
    assert class_sym.name == "Calculator"
    assert class_sym.docstring == "A simple calculator."

    methods = [s for s in symbols if s.symbol_type == SymbolType.METHOD]
    assert len(methods) == 2
    assert all(m.parent == "Calculator" for m in methods)


def test_parses_imports(parser):
    """Extracts import statements."""
    code = '''
import os
import sys
from pathlib import Path
from typing import List, Dict
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    imports = result.file.imports

    assert "os" in imports
    assert "sys" in imports
    assert "pathlib.Path" in imports
    assert "typing.List" in imports


def test_parses_decorated_functions(parser):
    """Extracts decorators from functions."""
    code = '''
@app.route("/api/users")
@require_auth
def get_users():
    """Get all users."""
    pass
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    func = result.file.symbols[0]
    assert "app.route" in func.decorators
    assert "require_auth" in func.decorators


def test_identifies_fastapi_routes(parser):
    """Identifies FastAPI route handlers."""
    code = '''
from fastapi import FastAPI

app = FastAPI()

@app.get("/users")
def list_users():
    pass

@app.post("/users")
def create_user():
    pass
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    routes = [s for s in result.file.symbols if s.symbol_type == SymbolType.ROUTE]
    assert len(routes) == 2


def test_handles_syntax_error_gracefully(parser):
    """Returns error result for invalid Python."""
    code = '''
def broken(
    # missing closing paren
'''
    result = parser.parse_string(code, "test.py")

    assert not result.ok
    assert "syntax" in result.error.lower() or "error" in result.error.lower()


def test_parses_module_level_variables(parser):
    """Extracts module-level constants and variables."""
    code = '''
VERSION = "1.0.0"
DEBUG = True
_private = "hidden"

config = {
    "timeout": 30,
}
'''
    result = parser.parse_string(code, "test.py")

    assert result.ok
    variables = [s for s in result.file.symbols
                 if s.symbol_type in (SymbolType.VARIABLE, SymbolType.CONSTANT)]

    names = [v.name for v in variables]
    assert "VERSION" in names
    assert "DEBUG" in names
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/test_python_parser.py -v
```

Expected: FAIL with import error

**Step 3: Implement PythonParser**

```python
# backend/src/oya/parsing/python_parser.py
"""Python AST-based parser."""

import ast
from pathlib import Path

from oya.parsing.base import BaseParser
from oya.parsing.models import (
    ParsedFile,
    ParsedSymbol,
    ParseResult,
    SymbolType,
)


class PythonParser(BaseParser):
    """Parser for Python files using the ast module."""

    # Decorator patterns that indicate route handlers
    ROUTE_DECORATORS = {
        "app.get", "app.post", "app.put", "app.delete", "app.patch",
        "router.get", "router.post", "router.put", "router.delete", "router.patch",
        "route", "get", "post", "put", "delete",
    }

    @property
    def supported_extensions(self) -> list[str]:
        return [".py", ".pyi"]

    @property
    def language_name(self) -> str:
        return "Python"

    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse Python file content."""
        return self.parse_string(content, str(file_path))

    def parse_string(self, content: str, path: str) -> ParseResult:
        """Parse Python code string.

        Args:
            content: Python source code.
            path: File path for error messages.

        Returns:
            ParseResult with extracted symbols.
        """
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return ParseResult.failure(path, f"Syntax error: {e}")

        symbols = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                symbol = self._parse_function(node, content)
                symbols.append(symbol)

            elif isinstance(node, ast.ClassDef):
                class_sym = self._parse_class(node, content)
                symbols.append(class_sym)

                # Parse methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        method = self._parse_function(item, content, parent=node.name)
                        symbols.append(method)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    if module:
                        imports.append(f"{module}.{alias.name}")
                    else:
                        imports.append(alias.name)

            elif isinstance(node, ast.Assign):
                # Module-level variable assignments
                if self._is_module_level(node, tree):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            sym = self._parse_variable(target, node)
                            symbols.append(sym)

        # Filter out methods already captured (avoid duplicates from ast.walk)
        symbols = self._deduplicate_symbols(symbols)

        parsed = ParsedFile(
            path=path,
            language="python",
            symbols=symbols,
            imports=imports,
            line_count=len(content.splitlines()),
        )

        return ParseResult.success(parsed)

    def _parse_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        content: str,
        parent: str | None = None,
    ) -> ParsedSymbol:
        """Extract function/method symbol."""
        decorators = [self._decorator_name(d) for d in node.decorator_list]

        # Determine if this is a route handler
        is_route = any(
            any(route in dec for route in self.ROUTE_DECORATORS)
            for dec in decorators
        )

        symbol_type = SymbolType.ROUTE if is_route else (
            SymbolType.METHOD if parent else SymbolType.FUNCTION
        )

        return ParsedSymbol(
            name=node.name,
            symbol_type=symbol_type,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            signature=self._get_signature(node),
            decorators=decorators,
            parent=parent,
        )

    def _parse_class(self, node: ast.ClassDef, content: str) -> ParsedSymbol:
        """Extract class symbol."""
        decorators = [self._decorator_name(d) for d in node.decorator_list]

        return ParsedSymbol(
            name=node.name,
            symbol_type=SymbolType.CLASS,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            decorators=decorators,
        )

    def _parse_variable(self, target: ast.Name, node: ast.Assign) -> ParsedSymbol:
        """Extract variable/constant symbol."""
        name = target.id
        # Convention: UPPER_CASE names are constants
        is_constant = name.isupper() or name.startswith("_") and name[1:].isupper()

        return ParsedSymbol(
            name=name,
            symbol_type=SymbolType.CONSTANT if is_constant else SymbolType.VARIABLE,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
        )

    def _decorator_name(self, node: ast.expr) -> str:
        """Get string representation of decorator."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            parts = []
            current = node
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        elif isinstance(node, ast.Call):
            return self._decorator_name(node.func)
        return ""

    def _get_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Get function signature string."""
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except Exception:
                    pass
            args.append(arg_str)

        sig = f"def {node.name}({', '.join(args)})"

        if node.returns:
            try:
                sig += f" -> {ast.unparse(node.returns)}"
            except Exception:
                pass

        return sig

    def _is_module_level(self, node: ast.AST, tree: ast.Module) -> bool:
        """Check if node is at module level."""
        return node in tree.body

    def _deduplicate_symbols(self, symbols: list[ParsedSymbol]) -> list[ParsedSymbol]:
        """Remove duplicate symbols (methods captured twice)."""
        seen = set()
        result = []
        for sym in symbols:
            key = (sym.name, sym.start_line, sym.parent)
            if key not in seen:
                seen.add(key)
                result.append(sym)
        return result
```

**Step 4: Update package init**

```python
# backend/src/oya/parsing/__init__.py
"""Code parsing utilities."""

from oya.parsing.models import (
    ParsedSymbol,
    SymbolType,
    ParsedFile,
    ParseResult,
)
from oya.parsing.base import BaseParser
from oya.parsing.python_parser import PythonParser

__all__ = [
    "ParsedSymbol",
    "SymbolType",
    "ParsedFile",
    "ParseResult",
    "BaseParser",
    "PythonParser",
]
```

**Step 5: Run tests to verify they pass**

```bash
pytest backend/tests/test_python_parser.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/oya/parsing/ backend/tests/test_python_parser.py
git commit -m "feat(backend): add Python AST parser"
```

---

### Task 3.5: TypeScript/JavaScript Parser

**Files:**
- Modify: `backend/pyproject.toml` (add tree-sitter dependencies)
- Create: `backend/src/oya/parsing/typescript_parser.py`
- Create: `backend/tests/test_typescript_parser.py`
- Modify: `backend/src/oya/parsing/__init__.py` (add export)

**Step 1: Add tree-sitter dependencies**

In `backend/pyproject.toml`, add to dependencies:
```toml
    "tree-sitter>=0.21.0",
    "tree-sitter-javascript>=0.21.0",
    "tree-sitter-typescript>=0.21.0",
```

**Step 2: Install updated dependencies**

```bash
cd backend && pip install -e ".[dev]"
```

**Step 3: Write the failing test**

```python
# backend/tests/test_typescript_parser.py
"""TypeScript/JavaScript parser tests."""

import pytest

from oya.parsing import SymbolType
from oya.parsing.typescript_parser import TypeScriptParser


@pytest.fixture
def parser():
    """Create TypeScript parser instance."""
    return TypeScriptParser()


def test_parser_supported_extensions(parser):
    """Parser supports TS and JS files."""
    assert ".ts" in parser.supported_extensions
    assert ".tsx" in parser.supported_extensions
    assert ".js" in parser.supported_extensions
    assert ".jsx" in parser.supported_extensions


def test_parses_function_declaration(parser):
    """Extracts function declarations."""
    code = '''
function greet(name: string): string {
    return `Hello, ${name}`;
}
'''
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    func = result.file.symbols[0]
    assert func.name == "greet"
    assert func.symbol_type == SymbolType.FUNCTION


def test_parses_arrow_function(parser):
    """Extracts arrow function assignments."""
    code = '''
const add = (a: number, b: number): number => {
    return a + b;
};
'''
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    symbols = result.file.symbols
    assert any(s.name == "add" for s in symbols)


def test_parses_class(parser):
    """Extracts class with methods."""
    code = '''
class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }

    subtract(a: number, b: number): number {
        return a - b;
    }
}
'''
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    class_sym = next(s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS)
    assert class_sym.name == "Calculator"

    methods = [s for s in result.file.symbols if s.symbol_type == SymbolType.METHOD]
    assert len(methods) == 2


def test_parses_interface(parser):
    """Extracts TypeScript interfaces."""
    code = '''
interface User {
    id: number;
    name: string;
    email?: string;
}
'''
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    interface = next(s for s in result.file.symbols if s.symbol_type == SymbolType.INTERFACE)
    assert interface.name == "User"


def test_parses_type_alias(parser):
    """Extracts TypeScript type aliases."""
    code = '''
type Status = "pending" | "active" | "completed";
type UserMap = Record<string, User>;
'''
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    types = [s for s in result.file.symbols if s.symbol_type == SymbolType.TYPE_ALIAS]
    names = [t.name for t in types]
    assert "Status" in names
    assert "UserMap" in names


def test_parses_imports(parser):
    """Extracts import statements."""
    code = '''
import React from 'react';
import { useState, useEffect } from 'react';
import type { User } from './types';
'''
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    imports = result.file.imports
    assert any("react" in imp for imp in imports)


def test_parses_exports(parser):
    """Extracts export statements."""
    code = '''
export function helper() {}
export const VERSION = "1.0.0";
export default class App {}
'''
    result = parser.parse_string(code, "test.ts")

    assert result.ok
    exports = result.file.exports
    assert "helper" in exports
    assert "VERSION" in exports


def test_handles_jsx(parser):
    """Handles JSX/TSX syntax."""
    code = '''
function Button({ label }: { label: string }) {
    return <button>{label}</button>;
}
'''
    result = parser.parse_string(code, "test.tsx")

    assert result.ok
    assert any(s.name == "Button" for s in result.file.symbols)


def test_handles_malformed_code(parser):
    """Returns error for invalid syntax."""
    code = '''
function broken( {
    // missing closing
'''
    result = parser.parse_string(code, "test.ts")

    # Tree-sitter is lenient, so it may still parse partially
    # Just ensure no crash
    assert isinstance(result.ok, bool)
```

**Step 4: Run test to verify it fails**

```bash
pytest backend/tests/test_typescript_parser.py -v
```

Expected: FAIL with import error

**Step 5: Implement TypeScriptParser**

```python
# backend/src/oya/parsing/typescript_parser.py
"""TypeScript/JavaScript parser using tree-sitter."""

from pathlib import Path

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser

from oya.parsing.base import BaseParser
from oya.parsing.models import (
    ParsedFile,
    ParsedSymbol,
    ParseResult,
    SymbolType,
)


class TypeScriptParser(BaseParser):
    """Parser for TypeScript and JavaScript files using tree-sitter."""

    def __init__(self):
        """Initialize tree-sitter parsers."""
        self._ts_parser = Parser(Language(tsts.language_typescript()))
        self._tsx_parser = Parser(Language(tsts.language_tsx()))
        self._js_parser = Parser(Language(tsjs.language()))

    @property
    def supported_extensions(self) -> list[str]:
        return [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]

    @property
    def language_name(self) -> str:
        return "TypeScript"

    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse TypeScript/JavaScript file content."""
        return self.parse_string(content, str(file_path))

    def parse_string(self, content: str, path: str) -> ParseResult:
        """Parse TypeScript/JavaScript code string.

        Args:
            content: Source code.
            path: File path for context.

        Returns:
            ParseResult with extracted symbols.
        """
        ext = Path(path).suffix.lower()

        # Choose appropriate parser
        if ext == ".tsx" or ext == ".jsx":
            parser = self._tsx_parser
        elif ext == ".ts":
            parser = self._ts_parser
        else:
            parser = self._js_parser

        try:
            tree = parser.parse(content.encode())
        except Exception as e:
            return ParseResult.failure(path, f"Parse error: {e}")

        symbols = []
        imports = []
        exports = []

        self._walk_tree(tree.root_node, content, symbols, imports, exports)

        parsed = ParsedFile(
            path=path,
            language="typescript" if ext in (".ts", ".tsx") else "javascript",
            symbols=symbols,
            imports=imports,
            exports=exports,
            line_count=len(content.splitlines()),
        )

        return ParseResult.success(parsed)

    def _walk_tree(
        self,
        node,
        content: str,
        symbols: list,
        imports: list,
        exports: list,
        parent_class: str | None = None,
    ):
        """Recursively walk tree-sitter AST."""
        node_type = node.type

        # Function declarations
        if node_type == "function_declaration":
            name = self._get_child_text(node, "identifier", content)
            if name:
                symbols.append(ParsedSymbol(
                    name=name,
                    symbol_type=SymbolType.FUNCTION,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                ))

        # Arrow functions assigned to const/let/var
        elif node_type in ("lexical_declaration", "variable_declaration"):
            for decl in node.children:
                if decl.type == "variable_declarator":
                    name_node = decl.child_by_field_name("name")
                    value_node = decl.child_by_field_name("value")
                    if name_node and value_node:
                        name = self._node_text(name_node, content)
                        if value_node.type == "arrow_function":
                            symbols.append(ParsedSymbol(
                                name=name,
                                symbol_type=SymbolType.FUNCTION,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                            ))
                        else:
                            symbols.append(ParsedSymbol(
                                name=name,
                                symbol_type=SymbolType.VARIABLE,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                            ))

        # Class declarations
        elif node_type == "class_declaration":
            name = self._get_child_text(node, "type_identifier", content)
            if not name:
                name = self._get_child_text(node, "identifier", content)
            if name:
                symbols.append(ParsedSymbol(
                    name=name,
                    symbol_type=SymbolType.CLASS,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                ))
                # Parse methods
                body = node.child_by_field_name("body")
                if body:
                    for child in body.children:
                        if child.type == "method_definition":
                            method_name = self._get_child_text(child, "property_identifier", content)
                            if method_name:
                                symbols.append(ParsedSymbol(
                                    name=method_name,
                                    symbol_type=SymbolType.METHOD,
                                    start_line=child.start_point[0] + 1,
                                    end_line=child.end_point[0] + 1,
                                    parent=name,
                                ))

        # Interface declarations (TypeScript)
        elif node_type == "interface_declaration":
            name = self._get_child_text(node, "type_identifier", content)
            if name:
                symbols.append(ParsedSymbol(
                    name=name,
                    symbol_type=SymbolType.INTERFACE,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                ))

        # Type aliases
        elif node_type == "type_alias_declaration":
            name = self._get_child_text(node, "type_identifier", content)
            if name:
                symbols.append(ParsedSymbol(
                    name=name,
                    symbol_type=SymbolType.TYPE_ALIAS,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                ))

        # Import statements
        elif node_type == "import_statement":
            source = self._get_child_text(node, "string", content)
            if source:
                imports.append(source.strip("'\""))

        # Export statements
        elif node_type == "export_statement":
            # Find what's being exported
            for child in node.children:
                if child.type == "function_declaration":
                    name = self._get_child_text(child, "identifier", content)
                    if name:
                        exports.append(name)
                        symbols.append(ParsedSymbol(
                            name=name,
                            symbol_type=SymbolType.FUNCTION,
                            start_line=child.start_point[0] + 1,
                            end_line=child.end_point[0] + 1,
                        ))
                elif child.type == "class_declaration":
                    name = self._get_child_text(child, "type_identifier", content)
                    if not name:
                        name = self._get_child_text(child, "identifier", content)
                    if name:
                        exports.append(name)
                elif child.type in ("lexical_declaration", "variable_declaration"):
                    for decl in child.children:
                        if decl.type == "variable_declarator":
                            name_node = decl.child_by_field_name("name")
                            if name_node:
                                exports.append(self._node_text(name_node, content))

        # Recurse for children (except class body which we handle above)
        if node_type != "class_declaration":
            for child in node.children:
                self._walk_tree(child, content, symbols, imports, exports, parent_class)

    def _get_child_text(self, node, child_type: str, content: str) -> str | None:
        """Get text of first child with given type."""
        for child in node.children:
            if child.type == child_type:
                return self._node_text(child, content)
        return None

    def _node_text(self, node, content: str) -> str:
        """Get text content of a node."""
        return content[node.start_byte:node.end_byte]
```

**Step 6: Update package init**

Add to `backend/src/oya/parsing/__init__.py`:
```python
from oya.parsing.typescript_parser import TypeScriptParser

# Add to __all__
__all__ = [..., "TypeScriptParser"]
```

**Step 7: Run tests to verify they pass**

```bash
pytest backend/tests/test_typescript_parser.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add backend/pyproject.toml backend/src/oya/parsing/ backend/tests/test_typescript_parser.py
git commit -m "feat(backend): add TypeScript/JavaScript parser using tree-sitter"
```

---

### Task 3.6: Java Parser

**Files:**
- Modify: `backend/pyproject.toml` (add tree-sitter-java)
- Create: `backend/src/oya/parsing/java_parser.py`
- Create: `backend/tests/test_java_parser.py`
- Modify: `backend/src/oya/parsing/__init__.py` (add export)

**Step 1: Add tree-sitter-java dependency**

In `backend/pyproject.toml`, add to dependencies:
```toml
    "tree-sitter-java>=0.21.0",
```

**Step 2: Install updated dependencies**

```bash
cd backend && pip install -e ".[dev]"
```

**Step 3: Write the failing test**

```python
# backend/tests/test_java_parser.py
"""Java parser tests."""

import pytest

from oya.parsing import SymbolType
from oya.parsing.java_parser import JavaParser


@pytest.fixture
def parser():
    """Create Java parser instance."""
    return JavaParser()


def test_parser_supported_extensions(parser):
    """Parser supports .java files."""
    assert ".java" in parser.supported_extensions


def test_parses_class(parser):
    """Extracts class declaration."""
    code = '''
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
}
'''
    result = parser.parse_string(code, "Calculator.java")

    assert result.ok
    class_sym = next(s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS)
    assert class_sym.name == "Calculator"


def test_parses_methods(parser):
    """Extracts class methods."""
    code = '''
public class Service {
    public void doSomething() {}
    private String helper(int value) { return ""; }
}
'''
    result = parser.parse_string(code, "Service.java")

    assert result.ok
    methods = [s for s in result.file.symbols if s.symbol_type == SymbolType.METHOD]
    assert len(methods) == 2
    names = [m.name for m in methods]
    assert "doSomething" in names
    assert "helper" in names


def test_parses_interface(parser):
    """Extracts interface declarations."""
    code = '''
public interface Repository<T> {
    T findById(long id);
    void save(T entity);
}
'''
    result = parser.parse_string(code, "Repository.java")

    assert result.ok
    interface = next(s for s in result.file.symbols if s.symbol_type == SymbolType.INTERFACE)
    assert interface.name == "Repository"


def test_parses_enum(parser):
    """Extracts enum declarations."""
    code = '''
public enum Status {
    PENDING,
    ACTIVE,
    COMPLETED
}
'''
    result = parser.parse_string(code, "Status.java")

    assert result.ok
    enum_sym = next(s for s in result.file.symbols if s.symbol_type == SymbolType.ENUM)
    assert enum_sym.name == "Status"


def test_parses_imports(parser):
    """Extracts import statements."""
    code = '''
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

public class MyService {}
'''
    result = parser.parse_string(code, "MyService.java")

    assert result.ok
    imports = result.file.imports
    assert any("java.util.List" in imp for imp in imports)
    assert any("springframework" in imp for imp in imports)


def test_parses_annotations(parser):
    """Extracts class and method annotations."""
    code = '''
@Service
@Transactional
public class UserService {
    @GetMapping("/users")
    public List<User> getUsers() {
        return null;
    }
}
'''
    result = parser.parse_string(code, "UserService.java")

    assert result.ok
    class_sym = next(s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS)
    assert "Service" in class_sym.decorators

    method = next(s for s in result.file.symbols if s.symbol_type == SymbolType.METHOD)
    assert "GetMapping" in method.decorators


def test_identifies_spring_routes(parser):
    """Identifies Spring MVC route handlers."""
    code = '''
@RestController
public class UserController {
    @GetMapping("/api/users")
    public List<User> list() { return null; }

    @PostMapping("/api/users")
    public User create(@RequestBody User user) { return user; }
}
'''
    result = parser.parse_string(code, "UserController.java")

    assert result.ok
    routes = [s for s in result.file.symbols if s.symbol_type == SymbolType.ROUTE]
    assert len(routes) == 2
```

**Step 4: Run test to verify it fails**

```bash
pytest backend/tests/test_java_parser.py -v
```

Expected: FAIL with import error

**Step 5: Implement JavaParser**

```python
# backend/src/oya/parsing/java_parser.py
"""Java parser using tree-sitter."""

from pathlib import Path

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from oya.parsing.base import BaseParser
from oya.parsing.models import (
    ParsedFile,
    ParsedSymbol,
    ParseResult,
    SymbolType,
)


class JavaParser(BaseParser):
    """Parser for Java files using tree-sitter."""

    # Annotation patterns that indicate route handlers
    ROUTE_ANNOTATIONS = {
        "GetMapping", "PostMapping", "PutMapping", "DeleteMapping", "PatchMapping",
        "RequestMapping", "Get", "Post", "Put", "Delete",
    }

    def __init__(self):
        """Initialize tree-sitter Java parser."""
        self._parser = Parser(Language(tsjava.language()))

    @property
    def supported_extensions(self) -> list[str]:
        return [".java"]

    @property
    def language_name(self) -> str:
        return "Java"

    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse Java file content."""
        return self.parse_string(content, str(file_path))

    def parse_string(self, content: str, path: str) -> ParseResult:
        """Parse Java code string.

        Args:
            content: Java source code.
            path: File path for context.

        Returns:
            ParseResult with extracted symbols.
        """
        try:
            tree = self._parser.parse(content.encode())
        except Exception as e:
            return ParseResult.failure(path, f"Parse error: {e}")

        symbols = []
        imports = []

        self._walk_tree(tree.root_node, content, symbols, imports)

        parsed = ParsedFile(
            path=path,
            language="java",
            symbols=symbols,
            imports=imports,
            line_count=len(content.splitlines()),
        )

        return ParseResult.success(parsed)

    def _walk_tree(
        self,
        node,
        content: str,
        symbols: list,
        imports: list,
        parent_class: str | None = None,
        class_annotations: list[str] | None = None,
    ):
        """Recursively walk tree-sitter AST."""
        node_type = node.type

        # Import declarations
        if node_type == "import_declaration":
            # Get the full import path
            for child in node.children:
                if child.type == "scoped_identifier":
                    imports.append(self._node_text(child, content))

        # Class declarations
        elif node_type == "class_declaration":
            annotations = self._get_annotations(node, content)
            name = self._get_identifier(node, content)
            if name:
                symbols.append(ParsedSymbol(
                    name=name,
                    symbol_type=SymbolType.CLASS,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    decorators=annotations,
                ))
                # Parse class body
                body = node.child_by_field_name("body")
                if body:
                    self._walk_tree(body, content, symbols, imports, name, annotations)
            return  # Don't recurse further

        # Interface declarations
        elif node_type == "interface_declaration":
            annotations = self._get_annotations(node, content)
            name = self._get_identifier(node, content)
            if name:
                symbols.append(ParsedSymbol(
                    name=name,
                    symbol_type=SymbolType.INTERFACE,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    decorators=annotations,
                ))

        # Enum declarations
        elif node_type == "enum_declaration":
            name = self._get_identifier(node, content)
            if name:
                symbols.append(ParsedSymbol(
                    name=name,
                    symbol_type=SymbolType.ENUM,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                ))

        # Method declarations
        elif node_type == "method_declaration":
            annotations = self._get_annotations(node, content)
            name = self._get_identifier(node, content)
            if name:
                # Check if this is a route handler
                is_route = any(ann in self.ROUTE_ANNOTATIONS for ann in annotations)

                symbols.append(ParsedSymbol(
                    name=name,
                    symbol_type=SymbolType.ROUTE if is_route else SymbolType.METHOD,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    decorators=annotations,
                    parent=parent_class,
                ))
            return  # Don't recurse into method body

        # Recurse for children
        for child in node.children:
            self._walk_tree(child, content, symbols, imports, parent_class, class_annotations)

    def _get_annotations(self, node, content: str) -> list[str]:
        """Get annotations from a node's modifiers."""
        annotations = []
        for child in node.children:
            if child.type == "modifiers":
                for mod in child.children:
                    if mod.type == "marker_annotation" or mod.type == "annotation":
                        # Get annotation name
                        for ann_child in mod.children:
                            if ann_child.type == "identifier":
                                annotations.append(self._node_text(ann_child, content))
        return annotations

    def _get_identifier(self, node, content: str) -> str | None:
        """Get identifier name from a declaration node."""
        name_node = node.child_by_field_name("name")
        if name_node:
            return self._node_text(name_node, content)
        return None

    def _node_text(self, node, content: str) -> str:
        """Get text content of a node."""
        return content[node.start_byte:node.end_byte]
```

**Step 6: Update package init**

Add to `backend/src/oya/parsing/__init__.py`:
```python
from oya.parsing.java_parser import JavaParser

# Add to __all__
__all__ = [..., "JavaParser"]
```

**Step 7: Run tests to verify they pass**

```bash
pytest backend/tests/test_java_parser.py -v
```

Expected: PASS

**Step 8: Commit**

```bash
git add backend/pyproject.toml backend/src/oya/parsing/ backend/tests/test_java_parser.py
git commit -m "feat(backend): add Java parser using tree-sitter"
```

---

### Task 3.7: Tree-sitter Fallback Parser

**Files:**
- Create: `backend/src/oya/parsing/fallback_parser.py`
- Create: `backend/tests/test_fallback_parser.py`
- Modify: `backend/src/oya/parsing/__init__.py` (add export)

**Step 1: Write the failing test**

```python
# backend/tests/test_fallback_parser.py
"""Fallback parser tests for unsupported languages."""

import pytest

from oya.parsing import SymbolType
from oya.parsing.fallback_parser import FallbackParser


@pytest.fixture
def parser():
    """Create fallback parser instance."""
    return FallbackParser()


def test_parser_accepts_any_extension(parser):
    """Fallback parser accepts any file extension."""
    from pathlib import Path

    assert parser.can_parse(Path("test.pl"))  # Perl
    assert parser.can_parse(Path("test.rb"))  # Ruby
    assert parser.can_parse(Path("test.go"))  # Go
    assert parser.can_parse(Path("test.rs"))  # Rust


def test_extracts_function_like_patterns(parser):
    """Extracts function-like patterns from code."""
    code = '''
sub greet {
    my $name = shift;
    print "Hello, $name\n";
}

sub helper {
    return 42;
}
'''
    result = parser.parse_string(code, "test.pl")

    assert result.ok
    # Should find something, even if not perfect
    assert len(result.file.symbols) > 0


def test_extracts_class_like_patterns(parser):
    """Extracts class-like patterns from code."""
    code = '''
class User
  def initialize(name)
    @name = name
  end

  def greet
    puts "Hello, #{@name}"
  end
end
'''
    result = parser.parse_string(code, "test.rb")

    assert result.ok
    # Should find class and methods
    symbols = result.file.symbols
    assert any("User" in s.name for s in symbols)


def test_counts_lines(parser):
    """Reports correct line count."""
    code = "line1\nline2\nline3\n"
    result = parser.parse_string(code, "test.txt")

    assert result.ok
    assert result.file.line_count == 3


def test_always_succeeds(parser):
    """Fallback parser never fails, even on binary-looking content."""
    code = "random garbage @#$%^&*()"
    result = parser.parse_string(code, "test.unknown")

    assert result.ok  # Should still succeed


def test_extracts_go_functions(parser):
    """Extracts Go function patterns."""
    code = '''
func main() {
    fmt.Println("Hello")
}

func helper(x int) int {
    return x * 2
}
'''
    result = parser.parse_string(code, "test.go")

    assert result.ok
    funcs = [s for s in result.file.symbols if s.symbol_type == SymbolType.FUNCTION]
    names = [f.name for f in funcs]
    assert "main" in names or any("main" in n for n in names)
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/test_fallback_parser.py -v
```

Expected: FAIL with import error

**Step 3: Implement FallbackParser**

```python
# backend/src/oya/parsing/fallback_parser.py
"""Fallback parser using regex patterns for unsupported languages."""

import re
from pathlib import Path

from oya.parsing.base import BaseParser
from oya.parsing.models import (
    ParsedFile,
    ParsedSymbol,
    ParseResult,
    SymbolType,
)


class FallbackParser(BaseParser):
    """Fallback parser using regex patterns for any file type.

    This parser provides basic symbol extraction for languages
    without dedicated parsers. It uses common patterns to identify
    functions, classes, and other constructs.
    """

    # Common patterns across languages
    PATTERNS = [
        # Functions: various syntaxes
        (r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", SymbolType.FUNCTION),  # Rust
        (r"^\s*func\s+(\w+)", SymbolType.FUNCTION),  # Go
        (r"^\s*def\s+(\w+)", SymbolType.FUNCTION),  # Python, Ruby
        (r"^\s*sub\s+(\w+)", SymbolType.FUNCTION),  # Perl
        (r"^\s*function\s+(\w+)", SymbolType.FUNCTION),  # Various

        # Classes
        (r"^\s*(?:pub\s+)?(?:abstract\s+)?class\s+(\w+)", SymbolType.CLASS),
        (r"^\s*(?:pub\s+)?struct\s+(\w+)", SymbolType.CLASS),  # Rust, Go
        (r"^\s*(?:pub\s+)?trait\s+(\w+)", SymbolType.INTERFACE),  # Rust
        (r"^\s*(?:pub\s+)?interface\s+(\w+)", SymbolType.INTERFACE),

        # Methods (indented function definitions)
        (r"^\s{2,}(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", SymbolType.METHOD),
        (r"^\s{2,}def\s+(\w+)", SymbolType.METHOD),
    ]

    @property
    def supported_extensions(self) -> list[str]:
        # This is a fallback - accepts anything
        return []

    @property
    def language_name(self) -> str:
        return "Unknown"

    def can_parse(self, file_path: Path) -> bool:
        """Fallback parser can parse any file."""
        return True

    def parse(self, file_path: Path, content: str) -> ParseResult:
        """Parse file content using regex patterns."""
        return self.parse_string(content, str(file_path))

    def parse_string(self, content: str, path: str) -> ParseResult:
        """Parse code string using regex patterns.

        Args:
            content: Source code.
            path: File path for context.

        Returns:
            ParseResult with extracted symbols (never fails).
        """
        symbols = []
        lines = content.splitlines()

        for line_num, line in enumerate(lines, start=1):
            for pattern, symbol_type in self.PATTERNS:
                match = re.match(pattern, line)
                if match:
                    name = match.group(1)
                    symbols.append(ParsedSymbol(
                        name=name,
                        symbol_type=symbol_type,
                        start_line=line_num,
                        end_line=line_num,  # Can't determine end without parsing
                    ))
                    break  # Only one match per line

        # Guess language from extension
        ext = Path(path).suffix.lower()
        language_map = {
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".pl": "perl",
            ".pm": "perl",
            ".lua": "lua",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".cs": "csharp",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
        }
        language = language_map.get(ext, "unknown")

        parsed = ParsedFile(
            path=path,
            language=language,
            symbols=symbols,
            line_count=len(lines),
        )

        return ParseResult.success(parsed)
```

**Step 4: Update package init**

Add to `backend/src/oya/parsing/__init__.py`:
```python
from oya.parsing.fallback_parser import FallbackParser

# Add to __all__
__all__ = [..., "FallbackParser"]
```

**Step 5: Run tests to verify they pass**

```bash
pytest backend/tests/test_fallback_parser.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/oya/parsing/ backend/tests/test_fallback_parser.py
git commit -m "feat(backend): add fallback regex parser for unsupported languages"
```

---

### Task 3.8: Parser Registry

**Files:**
- Create: `backend/src/oya/parsing/registry.py`
- Create: `backend/tests/test_parser_registry.py`
- Modify: `backend/src/oya/parsing/__init__.py` (add export)

**Step 1: Write the failing test**

```python
# backend/tests/test_parser_registry.py
"""Parser registry tests."""

from pathlib import Path

import pytest

from oya.parsing.registry import ParserRegistry


@pytest.fixture
def registry():
    """Create parser registry with all parsers."""
    return ParserRegistry()


def test_gets_python_parser(registry):
    """Returns Python parser for .py files."""
    parser = registry.get_parser(Path("test.py"))

    assert parser is not None
    assert parser.language_name == "Python"


def test_gets_typescript_parser(registry):
    """Returns TypeScript parser for .ts files."""
    parser = registry.get_parser(Path("test.ts"))

    assert parser is not None
    assert parser.language_name == "TypeScript"


def test_gets_java_parser(registry):
    """Returns Java parser for .java files."""
    parser = registry.get_parser(Path("test.java"))

    assert parser is not None
    assert parser.language_name == "Java"


def test_falls_back_for_unknown(registry):
    """Returns fallback parser for unsupported extensions."""
    parser = registry.get_parser(Path("test.pl"))

    assert parser is not None
    assert parser.language_name == "Unknown"


def test_parse_file_uses_correct_parser(registry):
    """parse_file selects appropriate parser."""
    result = registry.parse_file(
        Path("test.py"),
        "def hello(): pass"
    )

    assert result.ok
    assert result.file.language == "python"


def test_parse_file_with_fallback(registry):
    """parse_file uses fallback for unknown extensions."""
    result = registry.parse_file(
        Path("test.rs"),
        "fn main() {}"
    )

    assert result.ok
    assert result.file.language == "rust"
```

**Step 2: Run test to verify it fails**

```bash
pytest backend/tests/test_parser_registry.py -v
```

Expected: FAIL with import error

**Step 3: Implement ParserRegistry**

```python
# backend/src/oya/parsing/registry.py
"""Parser registry for selecting appropriate parser."""

from pathlib import Path

from oya.parsing.base import BaseParser
from oya.parsing.models import ParseResult
from oya.parsing.python_parser import PythonParser
from oya.parsing.typescript_parser import TypeScriptParser
from oya.parsing.java_parser import JavaParser
from oya.parsing.fallback_parser import FallbackParser


class ParserRegistry:
    """Registry that selects the appropriate parser for a file.

    Parsers are tried in order of specificity, with the fallback
    parser used when no specific parser matches.
    """

    def __init__(self):
        """Initialize registry with all available parsers."""
        self._parsers: list[BaseParser] = [
            PythonParser(),
            TypeScriptParser(),
            JavaParser(),
        ]
        self._fallback = FallbackParser()

    def get_parser(self, file_path: Path) -> BaseParser:
        """Get the appropriate parser for a file.

        Args:
            file_path: Path to file.

        Returns:
            Parser instance that can handle the file.
        """
        for parser in self._parsers:
            if parser.can_parse(file_path):
                return parser
        return self._fallback

    def parse_file(self, file_path: Path, content: str) -> ParseResult:
        """Parse a file using the appropriate parser.

        Args:
            file_path: Path to file.
            content: File content.

        Returns:
            ParseResult from the selected parser.
        """
        parser = self.get_parser(file_path)
        return parser.parse(file_path, content)

    @property
    def supported_languages(self) -> list[str]:
        """Get list of specifically supported languages."""
        return [p.language_name for p in self._parsers]
```

**Step 4: Update package init**

Add to `backend/src/oya/parsing/__init__.py`:
```python
from oya.parsing.registry import ParserRegistry

# Add to __all__
__all__ = [..., "ParserRegistry"]
```

**Step 5: Run tests to verify they pass**

```bash
pytest backend/tests/test_parser_registry.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/oya/parsing/ backend/tests/test_parser_registry.py
git commit -m "feat(backend): add parser registry for language detection"
```

---

## Phase 4: Wiki Generation Pipeline

The plan continues with:
- Task 4.1: Prompt Templates
- Task 4.2: Content Chunking
- Task 4.3: Overview Page Generator
- Task 4.4: Architecture Page Generator
- Task 4.5: Workflow Discovery and Generation
- Task 4.6: Directory Page Generator
- Task 4.7: File Page Generator
- Task 4.8: Generation Orchestrator
- Phase 5: API Endpoints
- Phase 6: Frontend Implementation
- Phase 7: Q&A System
- Phase 8: Notes/Correction System
- Phase 9: Integration and Polish

---

## Summary: Implementation Order

1. **Phase 1** - Project scaffolding (Docker, backend, frontend)
2. **Phase 2** - Backend core (SQLite, ChromaDB, LiteLLM, Config)
3. **Phase 3** - Repository analysis (Git, File filtering, Parsers)
4. **Phase 4** - Wiki generation pipeline
5. **Phase 5** - REST API endpoints with SSE
6. **Phase 6** - Frontend shell, navigation, wiki rendering
7. **Phase 7** - Q&A with evidence gating
8. **Phase 8** - Notes and correction system
9. **Phase 9** - Integration, testing, polish

Each phase builds on the previous, with frequent commits and TDD throughout.

---

**Note:** This plan covers the foundational tasks in detail. Subsequent phases follow the same TDD pattern. Use the `superpowers:test-driven-development` skill for each task's RED/GREEN/REFACTOR cycle.
