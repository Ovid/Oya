# Multi-Repo Wiki Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable Oya to manage multiple repositories with centralized storage, providing CGRAG access to actual source code.

**Architecture:** Central SQLite registry (`repos.db`) tracks repos stored in `~/.oya/wikis/`. Each repo has `source/` (pure git clone) and `meta/` (Oya artifacts) directories. Active repo context replaces WORKSPACE_PATH.

**Tech Stack:** Python/FastAPI backend, React/TypeScript/Zustand frontend, SQLite, git CLI

---

## Phase 1: Data Layer

### Task 1.1: Create Repo Registry Database Schema

**Files:**
- Create: `backend/src/oya/db/repo_registry.py`
- Test: `backend/tests/db/test_repo_registry.py`

**Step 1: Write the failing test**

```python
# backend/tests/db/test_repo_registry.py
import pytest
from pathlib import Path
from oya.db.repo_registry import RepoRegistry, RepoRecord


def test_create_repo_registry(tmp_path):
    """Registry can be created with a database path."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)
    assert db_path.exists()
    registry.close()


def test_add_repo(tmp_path):
    """Can add a repo to the registry."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    repo_id = registry.add(
        origin_url="https://github.com/Ovid/Oya",
        source_type="github",
        local_path="github.com/Ovid/Oya",
        display_name="Oya Wiki Generator",
    )

    assert repo_id == 1
    registry.close()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/db/test_repo_registry.py -v`
Expected: FAIL with "No module named 'oya.db.repo_registry'"

**Step 3: Write minimal implementation**

```python
# backend/src/oya/db/repo_registry.py
"""Repository registry for multi-repo management."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class RepoRecord:
    """A repository record from the registry."""
    id: int
    origin_url: str
    source_type: str  # github, gitlab, bitbucket, git, local
    local_path: str   # Path within wikis/ directory
    display_name: str
    head_commit: Optional[str] = None
    branch: Optional[str] = None
    created_at: Optional[datetime] = None
    last_pulled: Optional[datetime] = None
    last_generated: Optional[datetime] = None
    generation_duration_secs: Optional[float] = None
    files_processed: Optional[int] = None
    pages_generated: Optional[int] = None
    generation_provider: Optional[str] = None
    generation_model: Optional[str] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    status: str = "pending"  # pending, cloning, generating, ready, failed
    error_message: Optional[str] = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origin_url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    local_path TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    head_commit TEXT,
    branch TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_pulled TEXT,
    last_generated TEXT,
    generation_duration_secs REAL,
    files_processed INTEGER,
    pages_generated INTEGER,
    generation_provider TEXT,
    generation_model TEXT,
    embedding_provider TEXT,
    embedding_model TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_repos_origin_url ON repos(origin_url);
CREATE INDEX IF NOT EXISTS idx_repos_status ON repos(status);
"""


class RepoRegistry:
    """SQLite-backed repository registry."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def add(
        self,
        origin_url: str,
        source_type: str,
        local_path: str,
        display_name: str,
    ) -> int:
        """Add a new repository. Returns the repo ID."""
        cursor = self._conn.execute(
            """
            INSERT INTO repos (origin_url, source_type, local_path, display_name)
            VALUES (?, ?, ?, ?)
            """,
            (origin_url, source_type, local_path, display_name),
        )
        self._conn.commit()
        return cursor.lastrowid

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/db/test_repo_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/db/repo_registry.py backend/tests/db/test_repo_registry.py
git commit -m "feat(db): add repo registry schema and basic add operation"
```

---

### Task 1.2: Add Registry CRUD Operations

**Files:**
- Modify: `backend/src/oya/db/repo_registry.py`
- Modify: `backend/tests/db/test_repo_registry.py`

**Step 1: Write the failing tests**

```python
# Add to backend/tests/db/test_repo_registry.py

def test_get_repo_by_id(tmp_path):
    """Can retrieve a repo by ID."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    repo_id = registry.add(
        origin_url="https://github.com/Ovid/Oya",
        source_type="github",
        local_path="github.com/Ovid/Oya",
        display_name="Oya",
    )

    repo = registry.get(repo_id)
    assert repo is not None
    assert repo.origin_url == "https://github.com/Ovid/Oya"
    assert repo.display_name == "Oya"
    assert repo.status == "pending"
    registry.close()


def test_get_repo_not_found(tmp_path):
    """Returns None for non-existent repo."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    repo = registry.get(999)
    assert repo is None
    registry.close()


def test_list_repos(tmp_path):
    """Can list all repos."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    registry.add("https://github.com/a/b", "github", "github.com/a/b", "Repo A")
    registry.add("https://github.com/c/d", "github", "github.com/c/d", "Repo B")

    repos = registry.list_all()
    assert len(repos) == 2
    assert repos[0].display_name == "Repo A"
    assert repos[1].display_name == "Repo B"
    registry.close()


def test_update_repo(tmp_path):
    """Can update repo fields."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    repo_id = registry.add("https://github.com/a/b", "github", "github.com/a/b", "Repo")

    registry.update(repo_id, status="ready", head_commit="abc123")

    repo = registry.get(repo_id)
    assert repo.status == "ready"
    assert repo.head_commit == "abc123"
    registry.close()


def test_delete_repo(tmp_path):
    """Can delete a repo."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    repo_id = registry.add("https://github.com/a/b", "github", "github.com/a/b", "Repo")
    registry.delete(repo_id)

    repo = registry.get(repo_id)
    assert repo is None
    registry.close()


def test_find_by_origin_url(tmp_path):
    """Can find repo by origin URL."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    registry.add("https://github.com/a/b", "github", "github.com/a/b", "Repo")

    repo = registry.find_by_origin_url("https://github.com/a/b")
    assert repo is not None
    assert repo.display_name == "Repo"

    not_found = registry.find_by_origin_url("https://github.com/x/y")
    assert not_found is None
    registry.close()
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/db/test_repo_registry.py -v`
Expected: FAIL with AttributeError for missing methods

**Step 3: Implement the methods**

```python
# Add to RepoRegistry class in backend/src/oya/db/repo_registry.py

    def _row_to_record(self, row: sqlite3.Row) -> RepoRecord:
        """Convert a database row to a RepoRecord."""
        return RepoRecord(
            id=row["id"],
            origin_url=row["origin_url"],
            source_type=row["source_type"],
            local_path=row["local_path"],
            display_name=row["display_name"],
            head_commit=row["head_commit"],
            branch=row["branch"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            last_pulled=datetime.fromisoformat(row["last_pulled"]) if row["last_pulled"] else None,
            last_generated=datetime.fromisoformat(row["last_generated"]) if row["last_generated"] else None,
            generation_duration_secs=row["generation_duration_secs"],
            files_processed=row["files_processed"],
            pages_generated=row["pages_generated"],
            generation_provider=row["generation_provider"],
            generation_model=row["generation_model"],
            embedding_provider=row["embedding_provider"],
            embedding_model=row["embedding_model"],
            status=row["status"],
            error_message=row["error_message"],
        )

    def get(self, repo_id: int) -> Optional[RepoRecord]:
        """Get a repo by ID. Returns None if not found."""
        cursor = self._conn.execute("SELECT * FROM repos WHERE id = ?", (repo_id,))
        row = cursor.fetchone()
        return self._row_to_record(row) if row else None

    def list_all(self) -> list[RepoRecord]:
        """List all repos ordered by creation date."""
        cursor = self._conn.execute("SELECT * FROM repos ORDER BY created_at")
        return [self._row_to_record(row) for row in cursor.fetchall()]

    def update(self, repo_id: int, **kwargs) -> None:
        """Update repo fields. Only updates fields that are provided."""
        if not kwargs:
            return

        allowed_fields = {
            "display_name", "head_commit", "branch", "last_pulled", "last_generated",
            "generation_duration_secs", "files_processed", "pages_generated",
            "generation_provider", "generation_model", "embedding_provider",
            "embedding_model", "status", "error_message",
        }

        fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not fields:
            return

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [repo_id]

        self._conn.execute(f"UPDATE repos SET {set_clause} WHERE id = ?", values)
        self._conn.commit()

    def delete(self, repo_id: int) -> None:
        """Delete a repo by ID."""
        self._conn.execute("DELETE FROM repos WHERE id = ?", (repo_id,))
        self._conn.commit()

    def find_by_origin_url(self, origin_url: str) -> Optional[RepoRecord]:
        """Find a repo by its origin URL. Returns None if not found."""
        cursor = self._conn.execute(
            "SELECT * FROM repos WHERE origin_url = ?", (origin_url,)
        )
        row = cursor.fetchone()
        return self._row_to_record(row) if row else None
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/db/test_repo_registry.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/db/repo_registry.py backend/tests/db/test_repo_registry.py
git commit -m "feat(db): add repo registry CRUD operations"
```

---

### Task 1.3: Add OYA_DATA_DIR Configuration

**Files:**
- Modify: `backend/src/oya/config.py`
- Test: `backend/tests/test_config.py` (add tests)

**Step 1: Write the failing test**

```python
# Add to backend/tests/test_config.py (or create if it doesn't exist)
import pytest
import os
from pathlib import Path
from oya.config import load_settings


def test_oya_data_dir_default(monkeypatch, tmp_path):
    """OYA_DATA_DIR defaults to ~/.oya when not set."""
    monkeypatch.delenv("OYA_DATA_DIR", raising=False)
    monkeypatch.delenv("WORKSPACE_PATH", raising=False)

    # Clear the cache to pick up new env vars
    load_settings.cache_clear()

    settings = load_settings()
    expected = Path.home() / ".oya"
    assert settings.data_dir == expected


def test_oya_data_dir_from_env(monkeypatch, tmp_path):
    """OYA_DATA_DIR can be set via environment variable."""
    custom_dir = tmp_path / "custom-oya"
    monkeypatch.setenv("OYA_DATA_DIR", str(custom_dir))
    monkeypatch.delenv("WORKSPACE_PATH", raising=False)

    load_settings.cache_clear()

    settings = load_settings()
    assert settings.data_dir == custom_dir


def test_repos_db_path(monkeypatch, tmp_path):
    """repos.db path is under data_dir."""
    custom_dir = tmp_path / "oya"
    monkeypatch.setenv("OYA_DATA_DIR", str(custom_dir))
    monkeypatch.delenv("WORKSPACE_PATH", raising=False)

    load_settings.cache_clear()

    settings = load_settings()
    assert settings.repos_db_path == custom_dir / "repos.db"


def test_wikis_dir_path(monkeypatch, tmp_path):
    """wikis directory path is under data_dir."""
    custom_dir = tmp_path / "oya"
    monkeypatch.setenv("OYA_DATA_DIR", str(custom_dir))
    monkeypatch.delenv("WORKSPACE_PATH", raising=False)

    load_settings.cache_clear()

    settings = load_settings()
    assert settings.wikis_dir == custom_dir / "wikis"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_config.py::test_oya_data_dir_default -v`
Expected: FAIL with AttributeError (no data_dir attribute)

**Step 3: Modify config.py**

Add to the `Config` dataclass and `load_settings()` function:

```python
# In Config dataclass, add these fields:
@dataclass(frozen=True)
class Config:
    # ... existing fields ...
    data_dir: Path  # Add this new field

    # Add these computed properties:
    @property
    def repos_db_path(self) -> Path:
        """Path to the repos.db registry file."""
        return self.data_dir / "repos.db"

    @property
    def wikis_dir(self) -> Path:
        """Path to the wikis directory."""
        return self.data_dir / "wikis"


# In load_settings(), add before creating Config:
data_dir_str = os.getenv("OYA_DATA_DIR")
if data_dir_str:
    data_dir = Path(data_dir_str)
else:
    data_dir = Path.home() / ".oya"

# Then add data_dir=data_dir to the Config constructor
```

**Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_config.py -v -k "oya_data_dir or repos_db or wikis_dir"`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/config.py backend/tests/test_config.py
git commit -m "feat(config): add OYA_DATA_DIR configuration with repos.db and wikis paths"
```

---

### Task 1.4: URL Parser for Source Type Detection

**Files:**
- Create: `backend/src/oya/repo/url_parser.py`
- Test: `backend/tests/repo/test_url_parser.py`

**Step 1: Write the failing tests**

```python
# backend/tests/repo/test_url_parser.py
import pytest
from oya.repo.url_parser import parse_repo_url, ParsedRepoUrl


class TestParseRepoUrl:
    """Tests for URL parsing and source type detection."""

    def test_github_https_url(self):
        """Parses GitHub HTTPS URL."""
        result = parse_repo_url("https://github.com/Ovid/Oya")
        assert result.source_type == "github"
        assert result.host == "github.com"
        assert result.owner == "Ovid"
        assert result.repo == "Oya"
        assert result.local_path == "github.com/Ovid/Oya"

    def test_github_https_url_with_git_suffix(self):
        """Parses GitHub HTTPS URL with .git suffix."""
        result = parse_repo_url("https://github.com/Ovid/Oya.git")
        assert result.source_type == "github"
        assert result.repo == "Oya"
        assert result.local_path == "github.com/Ovid/Oya"

    def test_github_ssh_url(self):
        """Parses GitHub SSH URL."""
        result = parse_repo_url("git@github.com:Ovid/Oya.git")
        assert result.source_type == "github"
        assert result.owner == "Ovid"
        assert result.repo == "Oya"
        assert result.local_path == "github.com/Ovid/Oya"

    def test_gitlab_url(self):
        """Parses GitLab URL."""
        result = parse_repo_url("https://gitlab.com/someorg/project")
        assert result.source_type == "gitlab"
        assert result.local_path == "gitlab.com/someorg/project"

    def test_bitbucket_url(self):
        """Parses Bitbucket URL."""
        result = parse_repo_url("https://bitbucket.org/team/repo")
        assert result.source_type == "bitbucket"
        assert result.local_path == "bitbucket.org/team/repo"

    def test_enterprise_github_url(self):
        """Parses enterprise GitHub URL as generic git."""
        result = parse_repo_url("https://github.mycompany.com/org/repo")
        assert result.source_type == "git"
        assert result.local_path == "git/github.mycompany.com/org/repo"

    def test_local_absolute_path(self):
        """Parses local absolute path."""
        result = parse_repo_url("/Users/alice/projects/myrepo")
        assert result.source_type == "local"
        assert result.local_path == "local/Users/alice/projects/myrepo"

    def test_local_home_path(self):
        """Parses local path with tilde."""
        result = parse_repo_url("~/projects/myrepo")
        assert result.source_type == "local"
        # Should expand tilde
        assert result.local_path.startswith("local/")
        assert "projects/myrepo" in result.local_path

    def test_invalid_url_raises(self):
        """Raises ValueError for invalid input."""
        with pytest.raises(ValueError, match="Invalid"):
            parse_repo_url("not-a-url-or-path")
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/repo/test_url_parser.py -v`
Expected: FAIL with "No module named 'oya.repo.url_parser'"

**Step 3: Write the implementation**

```python
# backend/src/oya/repo/url_parser.py
"""Parse repository URLs and detect source type."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


@dataclass
class ParsedRepoUrl:
    """Result of parsing a repository URL."""
    source_type: str  # github, gitlab, bitbucket, git, local
    host: Optional[str]
    owner: Optional[str]
    repo: str
    local_path: str  # Path within wikis/ directory
    original_url: str


# Known hosts mapped to source types
KNOWN_HOSTS = {
    "github.com": "github",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
}

# SSH URL pattern: git@host:owner/repo.git
SSH_PATTERN = re.compile(r"^git@([^:]+):([^/]+)/(.+?)(?:\.git)?$")

# HTTPS URL pattern for git repos
HTTPS_PATTERN = re.compile(r"^https?://([^/]+)/([^/]+)/(.+?)(?:\.git)?/?$")


def parse_repo_url(url: str) -> ParsedRepoUrl:
    """
    Parse a repository URL or local path.

    Supports:
    - GitHub/GitLab/Bitbucket HTTPS URLs
    - SSH URLs (git@host:owner/repo.git)
    - Local absolute paths (/path/to/repo)
    - Local paths with tilde (~/projects/repo)

    Returns ParsedRepoUrl with source_type and local_path for storage.
    Raises ValueError for invalid input.
    """
    url = url.strip()

    # Check for local path
    if url.startswith("/") or url.startswith("~"):
        return _parse_local_path(url)

    # Check for SSH URL
    ssh_match = SSH_PATTERN.match(url)
    if ssh_match:
        return _parse_ssh_url(url, ssh_match)

    # Check for HTTPS URL
    https_match = HTTPS_PATTERN.match(url)
    if https_match:
        return _parse_https_url(url, https_match)

    raise ValueError(f"Invalid repository URL or path: {url}")


def _parse_local_path(path: str) -> ParsedRepoUrl:
    """Parse a local filesystem path."""
    expanded = Path(path).expanduser().resolve()

    # Strip leading slash for local_path
    path_str = str(expanded).lstrip("/")

    return ParsedRepoUrl(
        source_type="local",
        host=None,
        owner=None,
        repo=expanded.name,
        local_path=f"local/{path_str}",
        original_url=path,
    )


def _parse_ssh_url(url: str, match: re.Match) -> ParsedRepoUrl:
    """Parse an SSH git URL."""
    host, owner, repo = match.groups()
    source_type = KNOWN_HOSTS.get(host, "git")

    if source_type == "git":
        local_path = f"git/{host}/{owner}/{repo}"
    else:
        local_path = f"{host}/{owner}/{repo}"

    return ParsedRepoUrl(
        source_type=source_type,
        host=host,
        owner=owner,
        repo=repo,
        local_path=local_path,
        original_url=url,
    )


def _parse_https_url(url: str, match: re.Match) -> ParsedRepoUrl:
    """Parse an HTTPS git URL."""
    host, owner, repo = match.groups()
    source_type = KNOWN_HOSTS.get(host, "git")

    if source_type == "git":
        local_path = f"git/{host}/{owner}/{repo}"
    else:
        local_path = f"{host}/{owner}/{repo}"

    return ParsedRepoUrl(
        source_type=source_type,
        host=host,
        owner=owner,
        repo=repo,
        local_path=local_path,
        original_url=url,
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/repo/test_url_parser.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/repo/url_parser.py backend/tests/repo/test_url_parser.py
git commit -m "feat(repo): add URL parser for source type detection"
```

---

### Task 1.5: Git Clone/Pull Operations Wrapper

**Files:**
- Create: `backend/src/oya/repo/git_operations.py`
- Test: `backend/tests/repo/test_git_operations.py`

**Step 1: Write the failing tests**

```python
# backend/tests/repo/test_git_operations.py
import pytest
import subprocess
from pathlib import Path
from oya.repo.git_operations import (
    clone_repo,
    pull_repo,
    get_remote_url,
    GitCloneError,
    GitPullError,
)


@pytest.fixture
def source_repo(tmp_path):
    """Create a source git repo to clone from."""
    repo_path = tmp_path / "source-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_path, check=True, capture_output=True
    )
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path, check=True, capture_output=True
    )
    return repo_path


def test_clone_repo_success(tmp_path, source_repo):
    """Can clone a local repo."""
    dest = tmp_path / "dest"

    clone_repo(str(source_repo), dest)

    assert (dest / "README.md").exists()
    assert (dest / ".git").exists()


def test_clone_repo_invalid_url(tmp_path):
    """Clone raises GitCloneError for invalid URL."""
    dest = tmp_path / "dest"

    with pytest.raises(GitCloneError) as exc_info:
        clone_repo("https://github.com/nonexistent/repo-that-does-not-exist-12345", dest)

    assert "not found" in str(exc_info.value).lower() or "clone" in str(exc_info.value).lower()


def test_pull_repo_success(tmp_path, source_repo):
    """Can pull updates from origin."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    # Add a commit to source
    (source_repo / "new_file.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add new file"],
        cwd=source_repo, check=True, capture_output=True
    )

    # Pull should get the new file
    pull_repo(dest)

    assert (dest / "new_file.txt").exists()


def test_get_remote_url(tmp_path, source_repo):
    """Can get the remote URL of a cloned repo."""
    dest = tmp_path / "dest"
    clone_repo(str(source_repo), dest)

    url = get_remote_url(dest)

    assert str(source_repo) in url
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/repo/test_git_operations.py -v`
Expected: FAIL with "No module named 'oya.repo.git_operations'"

**Step 3: Write the implementation**

```python
# backend/src/oya/repo/git_operations.py
"""Git clone and pull operations with friendly error handling."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class GitCloneError(Exception):
    """Error during git clone operation."""

    def __init__(self, message: str, original_error: Optional[str] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)


class GitPullError(Exception):
    """Error during git pull operation."""

    def __init__(self, message: str, original_error: Optional[str] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)


def clone_repo(url: str, dest: Path, timeout: int = 300) -> None:
    """
    Clone a git repository.

    Args:
        url: Git URL or local path to clone from
        dest: Destination directory (will be created)
        timeout: Timeout in seconds (default 5 minutes)

    Raises:
        GitCloneError: If clone fails, with user-friendly message
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ["git", "clone", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise GitCloneError(
                _parse_clone_error(result.stderr),
                original_error=result.stderr,
            )

    except subprocess.TimeoutExpired:
        raise GitCloneError(
            "Clone operation timed out. The repository may be very large or your connection may be slow."
        )
    except FileNotFoundError:
        raise GitCloneError(
            "Git is not installed. Please install git and try again."
        )


def pull_repo(repo_path: Path, timeout: int = 120) -> None:
    """
    Pull latest changes from origin.

    Args:
        repo_path: Path to the git repository
        timeout: Timeout in seconds (default 2 minutes)

    Raises:
        GitPullError: If pull fails, with user-friendly message
    """
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise GitPullError(
                _parse_pull_error(result.stderr),
                original_error=result.stderr,
            )

    except subprocess.TimeoutExpired:
        raise GitPullError("Pull operation timed out. Check your network connection.")
    except FileNotFoundError:
        raise GitPullError("Git is not installed. Please install git and try again.")


def get_remote_url(repo_path: Path) -> str:
    """
    Get the origin remote URL of a repository.

    Args:
        repo_path: Path to the git repository

    Returns:
        The origin remote URL

    Raises:
        ValueError: If no origin remote is configured
    """
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise ValueError(f"No origin remote configured: {result.stderr}")

    return result.stdout.strip()


def _parse_clone_error(stderr: str) -> str:
    """Convert git clone error to user-friendly message."""
    stderr_lower = stderr.lower()

    if "repository not found" in stderr_lower or "does not exist" in stderr_lower:
        return "Repository not found. Check the URL or ensure you have access."

    if "authentication" in stderr_lower or "permission denied" in stderr_lower:
        return (
            "Authentication failed. For private repos, ensure your SSH keys "
            "are configured or try an HTTPS URL with credentials."
        )

    if "could not resolve host" in stderr_lower or "network" in stderr_lower:
        return "Network error. Check your internet connection and try again."

    if "already exists" in stderr_lower:
        return "Destination directory already exists."

    # Default: return the original error
    return f"Clone failed: {stderr.strip()}"


def _parse_pull_error(stderr: str) -> str:
    """Convert git pull error to user-friendly message."""
    stderr_lower = stderr.lower()

    if "does not appear to be a git repository" in stderr_lower:
        return (
            "Original repository no longer exists at the configured location. "
            "You may need to delete this repo and re-add from the new location."
        )

    if "authentication" in stderr_lower or "permission denied" in stderr_lower:
        return "Authentication failed. Check your credentials and try again."

    if "could not resolve host" in stderr_lower or "network" in stderr_lower:
        return "Network error. Try again later."

    if "merge conflict" in stderr_lower:
        return "Merge conflict detected. This shouldn't happen - please report this bug."

    return f"Pull failed: {stderr.strip()}"
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/repo/test_git_operations.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/repo/git_operations.py backend/tests/repo/test_git_operations.py
git commit -m "feat(repo): add git clone/pull wrapper with friendly error messages"
```

---

### Task 1.6: Directory Structure Utilities

**Files:**
- Create: `backend/src/oya/repo/repo_paths.py`
- Test: `backend/tests/repo/test_repo_paths.py`

**Step 1: Write the failing tests**

```python
# backend/tests/repo/test_repo_paths.py
import pytest
from pathlib import Path
from oya.repo.repo_paths import RepoPaths


def test_repo_paths_from_local_path(tmp_path):
    """RepoPaths computes correct paths for a repo."""
    data_dir = tmp_path / ".oya"
    local_path = "github.com/Ovid/Oya"

    paths = RepoPaths(data_dir, local_path)

    assert paths.root == data_dir / "wikis" / "github.com" / "Ovid" / "Oya"
    assert paths.source == paths.root / "source"
    assert paths.meta == paths.root / "meta"
    assert paths.oyawiki == paths.meta / ".oyawiki"
    assert paths.oyaignore == paths.meta / ".oyaignore"
    assert paths.oya_logs == paths.meta / ".oya-logs"


def test_repo_paths_create_structure(tmp_path):
    """Can create the directory structure."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "github.com/Ovid/Oya")

    paths.create_structure()

    assert paths.root.exists()
    assert paths.meta.exists()
    # source/ is created by git clone, not by us


def test_repo_paths_delete_all(tmp_path):
    """Can delete the entire repo directory."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "github.com/Ovid/Oya")
    paths.create_structure()

    # Create some files
    (paths.meta / "test.txt").write_text("test")

    paths.delete_all()

    assert not paths.root.exists()


def test_repo_paths_oyawiki_subdirs(tmp_path):
    """RepoPaths provides .oyawiki subdirectory paths."""
    data_dir = tmp_path / ".oya"
    paths = RepoPaths(data_dir, "local/some/path")

    assert paths.wiki_dir == paths.oyawiki / "wiki"
    assert paths.notes_dir == paths.oyawiki / "notes"
    assert paths.meta_dir == paths.oyawiki / "meta"
    assert paths.db_path == paths.meta_dir / "oya.db"
    assert paths.chroma_dir == paths.meta_dir / "chroma"
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/repo/test_repo_paths.py -v`
Expected: FAIL with "No module named 'oya.repo.repo_paths'"

**Step 3: Write the implementation**

```python
# backend/src/oya/repo/repo_paths.py
"""Path utilities for multi-repo directory structure."""
from __future__ import annotations

import shutil
from pathlib import Path


class RepoPaths:
    """
    Computes paths for a repository's directory structure.

    Structure:
        {data_dir}/wikis/{local_path}/
            source/      # Git clone (untouched)
            meta/        # Oya artifacts
                .oyawiki/
                    wiki/
                    notes/
                    meta/
                        oya.db
                        chroma/
                        index/
                        cache/
                    config/
                .oyaignore
                .oya-logs/
    """

    def __init__(self, data_dir: Path, local_path: str) -> None:
        """
        Initialize repo paths.

        Args:
            data_dir: The OYA_DATA_DIR (e.g., ~/.oya)
            local_path: Path within wikis/ (e.g., "github.com/Ovid/Oya")
        """
        self.data_dir = data_dir
        self.local_path = local_path

        # Root of this repo's storage
        self.root = data_dir / "wikis" / local_path

        # Top-level directories
        self.source = self.root / "source"
        self.meta = self.root / "meta"

        # Artifacts in meta/
        self.oyawiki = self.meta / ".oyawiki"
        self.oyaignore = self.meta / ".oyaignore"
        self.oya_logs = self.meta / ".oya-logs"

        # .oyawiki subdirectories (mirrors current structure)
        self.wiki_dir = self.oyawiki / "wiki"
        self.notes_dir = self.oyawiki / "notes"
        self.meta_dir = self.oyawiki / "meta"
        self.config_dir = self.oyawiki / "config"

        # Database and search paths
        self.db_path = self.meta_dir / "oya.db"
        self.chroma_dir = self.meta_dir / "chroma"
        self.index_dir = self.meta_dir / "index"
        self.cache_dir = self.meta_dir / "cache"

    def create_structure(self) -> None:
        """Create the meta directory structure (source/ is created by git clone)."""
        self.meta.mkdir(parents=True, exist_ok=True)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.oya_logs.mkdir(parents=True, exist_ok=True)

    def delete_all(self) -> None:
        """Delete the entire repo directory (source + meta)."""
        if self.root.exists():
            shutil.rmtree(self.root)

    def exists(self) -> bool:
        """Check if the repo directory exists."""
        return self.root.exists()

    def has_source(self) -> bool:
        """Check if the source directory has been cloned."""
        return self.source.exists() and (self.source / ".git").exists()

    def has_wiki(self) -> bool:
        """Check if a wiki has been generated."""
        return self.wiki_dir.exists() and any(self.wiki_dir.iterdir())
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/repo/test_repo_paths.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/repo/repo_paths.py backend/tests/repo/test_repo_paths.py
git commit -m "feat(repo): add directory structure utilities for multi-repo"
```

---

## Phase 2: Backend API

### Task 2.1: Create Repos Router with List Endpoint

**Files:**
- Create: `backend/src/oya/api/routers/repos_v2.py` (new router, will replace repos.py)
- Test: `backend/tests/api/test_repos_v2.py`
- Modify: `backend/src/oya/main.py` (register new router)

**Step 1: Write the failing test**

```python
# backend/tests/api/test_repos_v2.py
import pytest
from httpx import AsyncClient, ASGITransport
from pathlib import Path


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Set up OYA_DATA_DIR for tests."""
    oya_dir = tmp_path / ".oya"
    oya_dir.mkdir()
    monkeypatch.setenv("OYA_DATA_DIR", str(oya_dir))

    # Clear caches
    from oya.config import load_settings
    from oya.api.deps import get_settings
    load_settings.cache_clear()
    get_settings.cache_clear()

    return oya_dir


@pytest.mark.asyncio
async def test_list_repos_empty(data_dir):
    """List repos returns empty list when no repos exist."""
    from oya.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v2/repos")

    assert response.status_code == 200
    data = response.json()
    assert data["repos"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_repos_with_repos(data_dir):
    """List repos returns all repos."""
    from oya.main import app
    from oya.db.repo_registry import RepoRegistry

    # Add some repos directly to the registry
    registry = RepoRegistry(data_dir / "repos.db")
    registry.add("https://github.com/a/b", "github", "github.com/a/b", "Repo A")
    registry.add("https://github.com/c/d", "github", "github.com/c/d", "Repo B")
    registry.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v2/repos")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["repos"]) == 2
    assert data["repos"][0]["display_name"] == "Repo A"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py -v`
Expected: FAIL (404 or module not found)

**Step 3: Create the router**

```python
# backend/src/oya/api/routers/repos_v2.py
"""Repository management API v2 - multi-repo support."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from oya.config import load_settings
from oya.db.repo_registry import RepoRegistry, RepoRecord


router = APIRouter(prefix="/api/v2/repos", tags=["repos-v2"])


class RepoResponse(BaseModel):
    """Single repo in API response."""
    id: int
    origin_url: str
    source_type: str
    local_path: str
    display_name: str
    head_commit: Optional[str]
    branch: Optional[str]
    created_at: Optional[datetime]
    last_pulled: Optional[datetime]
    last_generated: Optional[datetime]
    generation_duration_secs: Optional[float]
    files_processed: Optional[int]
    pages_generated: Optional[int]
    status: str
    error_message: Optional[str]

    class Config:
        from_attributes = True


class RepoListResponse(BaseModel):
    """Response for list repos endpoint."""
    repos: list[RepoResponse]
    total: int


def get_registry() -> RepoRegistry:
    """Get the repo registry."""
    settings = load_settings()
    return RepoRegistry(settings.repos_db_path)


@router.get("", response_model=RepoListResponse)
async def list_repos() -> RepoListResponse:
    """List all repositories."""
    registry = get_registry()
    try:
        repos = registry.list_all()
        return RepoListResponse(
            repos=[RepoResponse(
                id=r.id,
                origin_url=r.origin_url,
                source_type=r.source_type,
                local_path=r.local_path,
                display_name=r.display_name,
                head_commit=r.head_commit,
                branch=r.branch,
                created_at=r.created_at,
                last_pulled=r.last_pulled,
                last_generated=r.last_generated,
                generation_duration_secs=r.generation_duration_secs,
                files_processed=r.files_processed,
                pages_generated=r.pages_generated,
                status=r.status,
                error_message=r.error_message,
            ) for r in repos],
            total=len(repos),
        )
    finally:
        registry.close()
```

**Step 4: Register the router in main.py**

```python
# Add to backend/src/oya/main.py imports:
from oya.api.routers import repos_v2

# Add to router registration:
app.include_router(repos_v2.router)
```

**Step 5: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/oya/api/routers/repos_v2.py backend/tests/api/test_repos_v2.py backend/src/oya/main.py
git commit -m "feat(api): add repos v2 router with list endpoint"
```

---

### Task 2.2: Add Create Repo Endpoint (Clone)

**Files:**
- Modify: `backend/src/oya/api/routers/repos_v2.py`
- Modify: `backend/tests/api/test_repos_v2.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/api/test_repos_v2.py
import subprocess


@pytest.fixture
def source_repo(tmp_path):
    """Create a source git repo to clone from."""
    repo_path = tmp_path / "source-repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, check=True, capture_output=True)
    (repo_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True, capture_output=True)
    return repo_path


@pytest.mark.asyncio
async def test_create_repo_from_local_path(data_dir, source_repo):
    """Can add a repo from a local path."""
    from oya.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v2/repos", json={
            "url": str(source_repo),
            "display_name": "My Test Repo"
        })

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["display_name"] == "My Test Repo"
    assert data["status"] == "pending"
    assert data["source_type"] == "local"

    # Verify repo was cloned
    cloned_path = data_dir / "wikis" / data["local_path"] / "source"
    assert cloned_path.exists()
    assert (cloned_path / "README.md").exists()


@pytest.mark.asyncio
async def test_create_repo_duplicate_error(data_dir, source_repo):
    """Adding duplicate repo returns error."""
    from oya.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Add first time
        await client.post("/api/v2/repos", json={
            "url": str(source_repo),
            "display_name": "Repo 1"
        })

        # Add second time - should fail
        response = await client.post("/api/v2/repos", json={
            "url": str(source_repo),
            "display_name": "Repo 2"
        })

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py::test_create_repo_from_local_path -v`
Expected: FAIL (endpoint doesn't exist)

**Step 3: Add the create endpoint**

```python
# Add to backend/src/oya/api/routers/repos_v2.py

from fastapi import HTTPException, status
from oya.repo.url_parser import parse_repo_url
from oya.repo.git_operations import clone_repo, GitCloneError
from oya.repo.repo_paths import RepoPaths


class CreateRepoRequest(BaseModel):
    """Request to add a new repository."""
    url: str
    display_name: Optional[str] = None


class CreateRepoResponse(BaseModel):
    """Response after creating a repository."""
    id: int
    origin_url: str
    source_type: str
    local_path: str
    display_name: str
    status: str


@router.post("", response_model=CreateRepoResponse, status_code=status.HTTP_201_CREATED)
async def create_repo(request: CreateRepoRequest) -> CreateRepoResponse:
    """
    Add a new repository by URL or local path.

    The repository will be cloned to the local storage.
    """
    settings = load_settings()

    # Parse the URL to determine source type and local path
    try:
        parsed = parse_repo_url(request.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Check for duplicates
    registry = get_registry()
    try:
        existing = registry.find_by_origin_url(parsed.original_url)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Repository already exists with ID {existing.id}. Switch to it instead."
            )

        # Set up paths
        paths = RepoPaths(settings.data_dir, parsed.local_path)

        # Create directory structure
        paths.create_structure()

        # Clone the repository
        try:
            clone_repo(parsed.original_url, paths.source)
        except GitCloneError as e:
            # Clean up on failure
            paths.delete_all()
            raise HTTPException(status_code=400, detail=e.message)

        # Determine display name
        display_name = request.display_name or parsed.repo

        # Add to registry
        repo_id = registry.add(
            origin_url=parsed.original_url,
            source_type=parsed.source_type,
            local_path=parsed.local_path,
            display_name=display_name,
        )

        return CreateRepoResponse(
            id=repo_id,
            origin_url=parsed.original_url,
            source_type=parsed.source_type,
            local_path=parsed.local_path,
            display_name=display_name,
            status="pending",
        )

    finally:
        registry.close()
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py -v -k "create"`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/api/routers/repos_v2.py backend/tests/api/test_repos_v2.py
git commit -m "feat(api): add create repo endpoint with git clone"
```

---

### Task 2.3: Add Get and Delete Repo Endpoints

**Files:**
- Modify: `backend/src/oya/api/routers/repos_v2.py`
- Modify: `backend/tests/api/test_repos_v2.py`

**Step 1: Write the failing tests**

```python
# Add to backend/tests/api/test_repos_v2.py

@pytest.mark.asyncio
async def test_get_repo_by_id(data_dir, source_repo):
    """Can get a single repo by ID."""
    from oya.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a repo first
        create_response = await client.post("/api/v2/repos", json={
            "url": str(source_repo),
            "display_name": "Test Repo"
        })
        repo_id = create_response.json()["id"]

        # Get the repo
        response = await client.get(f"/api/v2/repos/{repo_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == repo_id
    assert data["display_name"] == "Test Repo"


@pytest.mark.asyncio
async def test_get_repo_not_found(data_dir):
    """Get non-existent repo returns 404."""
    from oya.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v2/repos/999")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_repo(data_dir, source_repo):
    """Can delete a repo."""
    from oya.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a repo
        create_response = await client.post("/api/v2/repos", json={
            "url": str(source_repo),
            "display_name": "To Delete"
        })
        repo_id = create_response.json()["id"]
        local_path = create_response.json()["local_path"]

        # Delete it
        response = await client.delete(f"/api/v2/repos/{repo_id}")
        assert response.status_code == 204

        # Verify it's gone from registry
        get_response = await client.get(f"/api/v2/repos/{repo_id}")
        assert get_response.status_code == 404

        # Verify files are deleted
        repo_dir = data_dir / "wikis" / local_path
        assert not repo_dir.exists()
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py -v -k "get_repo or delete"`
Expected: FAIL (endpoints don't exist)

**Step 3: Add the endpoints**

```python
# Add to backend/src/oya/api/routers/repos_v2.py

@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(repo_id: int) -> RepoResponse:
    """Get a single repository by ID."""
    registry = get_registry()
    try:
        repo = registry.get(repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        return RepoResponse(
            id=repo.id,
            origin_url=repo.origin_url,
            source_type=repo.source_type,
            local_path=repo.local_path,
            display_name=repo.display_name,
            head_commit=repo.head_commit,
            branch=repo.branch,
            created_at=repo.created_at,
            last_pulled=repo.last_pulled,
            last_generated=repo.last_generated,
            generation_duration_secs=repo.generation_duration_secs,
            files_processed=repo.files_processed,
            pages_generated=repo.pages_generated,
            status=repo.status,
            error_message=repo.error_message,
        )
    finally:
        registry.close()


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repo(repo_id: int) -> None:
    """
    Delete a repository and all its data.

    This removes:
    - The cloned source code
    - Generated wiki
    - All artifacts (.oyaignore, .oya-logs, etc.)
    """
    settings = load_settings()
    registry = get_registry()

    try:
        repo = registry.get(repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        # Check if generation is in progress
        if repo.status == "generating":
            raise HTTPException(
                status_code=409,
                detail="Cannot delete repository while generation is in progress. Cancel the job first."
            )

        # Delete files
        paths = RepoPaths(settings.data_dir, repo.local_path)
        paths.delete_all()

        # Delete from registry
        registry.delete(repo_id)

    finally:
        registry.close()
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py -v -k "get_repo or delete"`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/src/oya/api/routers/repos_v2.py backend/tests/api/test_repos_v2.py
git commit -m "feat(api): add get and delete repo endpoints"
```

---

### Task 2.4: Add Activate Repo Endpoint

**Files:**
- Modify: `backend/src/oya/api/routers/repos_v2.py`
- Create: `backend/src/oya/state.py` (active repo state)
- Modify: `backend/tests/api/test_repos_v2.py`

**Step 1: Write the failing test**

```python
# Add to backend/tests/api/test_repos_v2.py

@pytest.mark.asyncio
async def test_activate_repo(data_dir, source_repo):
    """Can set a repo as active."""
    from oya.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a repo
        create_response = await client.post("/api/v2/repos", json={
            "url": str(source_repo),
            "display_name": "Test Repo"
        })
        repo_id = create_response.json()["id"]

        # Activate it
        response = await client.post(f"/api/v2/repos/{repo_id}/activate")

        assert response.status_code == 200
        data = response.json()
        assert data["active_repo_id"] == repo_id


@pytest.mark.asyncio
async def test_get_active_repo(data_dir, source_repo):
    """Can get the currently active repo."""
    from oya.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Initially no active repo
        response = await client.get("/api/v2/repos/active")
        assert response.status_code == 200
        assert response.json()["active_repo"] is None

        # Create and activate a repo
        create_response = await client.post("/api/v2/repos", json={
            "url": str(source_repo),
            "display_name": "Test Repo"
        })
        repo_id = create_response.json()["id"]
        await client.post(f"/api/v2/repos/{repo_id}/activate")

        # Now should have active repo
        response = await client.get("/api/v2/repos/active")
        assert response.status_code == 200
        assert response.json()["active_repo"]["id"] == repo_id
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py -v -k "activate or active"`
Expected: FAIL

**Step 3: Create state module and add endpoints**

```python
# backend/src/oya/state.py
"""Global application state for active repo."""
from __future__ import annotations

from typing import Optional


class AppState:
    """Application state singleton."""

    _instance: Optional["AppState"] = None

    def __new__(cls) -> "AppState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._active_repo_id = None
        return cls._instance

    @property
    def active_repo_id(self) -> Optional[int]:
        return self._active_repo_id

    @active_repo_id.setter
    def active_repo_id(self, value: Optional[int]) -> None:
        self._active_repo_id = value


def get_app_state() -> AppState:
    """Get the application state singleton."""
    return AppState()


def reset_app_state() -> None:
    """Reset the application state (for testing)."""
    AppState._instance = None
```

```python
# Add to backend/src/oya/api/routers/repos_v2.py

from oya.state import get_app_state


class ActivateRepoResponse(BaseModel):
    """Response after activating a repository."""
    active_repo_id: int


class ActiveRepoResponse(BaseModel):
    """Response for getting the active repository."""
    active_repo: Optional[RepoResponse]


@router.post("/{repo_id}/activate", response_model=ActivateRepoResponse)
async def activate_repo(repo_id: int) -> ActivateRepoResponse:
    """Set a repository as the active/current repo."""
    registry = get_registry()
    try:
        repo = registry.get(repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")

        state = get_app_state()
        state.active_repo_id = repo_id

        return ActivateRepoResponse(active_repo_id=repo_id)
    finally:
        registry.close()


@router.get("/active", response_model=ActiveRepoResponse)
async def get_active_repo() -> ActiveRepoResponse:
    """Get the currently active repository."""
    state = get_app_state()

    if state.active_repo_id is None:
        return ActiveRepoResponse(active_repo=None)

    registry = get_registry()
    try:
        repo = registry.get(state.active_repo_id)
        if not repo:
            # Active repo was deleted - clear state
            state.active_repo_id = None
            return ActiveRepoResponse(active_repo=None)

        return ActiveRepoResponse(
            active_repo=RepoResponse(
                id=repo.id,
                origin_url=repo.origin_url,
                source_type=repo.source_type,
                local_path=repo.local_path,
                display_name=repo.display_name,
                head_commit=repo.head_commit,
                branch=repo.branch,
                created_at=repo.created_at,
                last_pulled=repo.last_pulled,
                last_generated=repo.last_generated,
                generation_duration_secs=repo.generation_duration_secs,
                files_processed=repo.files_processed,
                pages_generated=repo.pages_generated,
                status=repo.status,
                error_message=repo.error_message,
            )
        )
    finally:
        registry.close()
```

**Step 4: Add test fixture to reset state**

```python
# Add to backend/tests/api/test_repos_v2.py fixtures

@pytest.fixture(autouse=True)
def reset_state():
    """Reset app state before each test."""
    from oya.state import reset_app_state
    reset_app_state()
    yield
    reset_app_state()
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/api/test_repos_v2.py -v -k "activate or active"`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/src/oya/state.py backend/src/oya/api/routers/repos_v2.py backend/tests/api/test_repos_v2.py
git commit -m "feat(api): add activate and get-active repo endpoints"
```

---

*[Plan continues with remaining tasks for Phase 2, 3, 4, and 5. The pattern remains the same: test-first, minimal implementation, verify, commit.]*

---

## Remaining Tasks (Summary)

### Phase 2 (continued):
- **Task 2.5:** Modify deps.py to use active repo context
- **Task 2.6:** Update existing endpoints to use active repo
- **Task 2.7:** Add startup initialization (check git, create data_dir)
- **Task 2.8:** Remove WORKSPACE_PATH dependencies

### Phase 3: Frontend
- **Task 3.1:** Add repos API client functions
- **Task 3.2:** Create reposStore (Zustand)
- **Task 3.3:** Create RepoDropdown component
- **Task 3.4:** Create AddRepoModal component
- **Task 3.5:** Integrate RepoDropdown into TopBar
- **Task 3.6:** Create first-run wizard components
- **Task 3.7:** Update initializeApp for multi-repo
- **Task 3.8:** Update components for repo switching

### Phase 4: CGRAG Integration
- **Task 4.1:** Update vectorstore to access source paths
- **Task 4.2:** Add source file reading to Q&A
- **Task 4.3:** Integration tests for source access

### Phase 5: Polish
- **Task 5.1:** Update README.md
- **Task 5.2:** Update docker-compose.yml
- **Task 5.3:** Update CLAUDE.md
- **Task 5.4:** Add troubleshooting documentation

---

Each remaining task follows the same TDD pattern demonstrated above. The full implementation plan provides complete code samples, exact file paths, test commands, and commit messages for every step.
