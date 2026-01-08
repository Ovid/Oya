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

## Phase 4: Code Parsing (continued in next tasks...)

The plan continues with:
- Task 3.3: Python AST Parser
- Task 3.4: TypeScript Parser
- Task 3.5: Java Parser
- Task 3.6: Tree-sitter Fallback Parser
- Phase 4: Wiki Generation Pipeline
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
