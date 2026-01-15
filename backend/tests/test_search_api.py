"""Search API tests."""

import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_settings, _reset_db_instance, get_db


@pytest.fixture
def workspace_with_content(tmp_path, monkeypatch):
    """Create workspace with searchable content."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)

    # Create wiki with content
    wiki = workspace / ".oyawiki" / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "overview.md").write_text(
        "# Authentication System\n\nThis handles user login and OAuth."
    )
    (wiki / "architecture.md").write_text("# Architecture\n\nThe system uses FastAPI.")

    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    from oya.config import load_settings

    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

    # Index content in FTS
    db = get_db()
    db.execute(
        "INSERT INTO fts_content (content, title, path, type) VALUES (?, ?, ?, ?)",
        ("This handles user login and OAuth authentication", "Overview", "overview.md", "wiki"),
    )
    db.execute(
        "INSERT INTO fts_content (content, title, path, type) VALUES (?, ?, ?, ?)",
        ("The system uses FastAPI for the backend", "Architecture", "architecture.md", "wiki"),
    )
    db.commit()

    yield workspace

    _reset_db_instance()


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def test_search_returns_results(client, workspace_with_content):
    """GET /api/search?q=... returns matching results."""
    response = await client.get("/api/search", params={"q": "authentication"})

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) > 0


async def test_search_returns_empty_for_no_match(client, workspace_with_content):
    """GET /api/search?q=... returns empty for no matches."""
    response = await client.get("/api/search", params={"q": "nonexistent_term_xyz"})

    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []


async def test_search_requires_query(client, workspace_with_content):
    """GET /api/search without q returns 422."""
    response = await client.get("/api/search")

    assert response.status_code == 422


async def test_search_result_contains_snippet(client, workspace_with_content):
    """Search results include snippet and metadata."""
    response = await client.get("/api/search", params={"q": "FastAPI"})

    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0
    result = data["results"][0]
    assert "title" in result
    assert "path" in result
    assert "snippet" in result
    assert "type" in result
