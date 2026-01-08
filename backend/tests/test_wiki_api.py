"""Wiki page API tests."""

import subprocess
import pytest
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.api.deps import get_settings, _reset_db_instance


@pytest.fixture
def workspace_with_wiki(tmp_path, monkeypatch):
    """Create workspace with wiki pages."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)

    # Create wiki structure
    wiki_path = workspace / ".coretechs" / "wiki"
    wiki_path.mkdir(parents=True)

    # Create overview
    (wiki_path / "overview.md").write_text("# Project Overview\n\nThis is the overview.")

    # Create architecture
    (wiki_path / "architecture.md").write_text("# Architecture\n\nSystem design here.")

    # Create workflow
    workflows = wiki_path / "workflows"
    workflows.mkdir()
    (workflows / "authentication.md").write_text("# Authentication Workflow")

    # Create directory page
    directories = wiki_path / "directories"
    directories.mkdir()
    (directories / "src.md").write_text("# src Directory")

    # Create file page
    files = wiki_path / "files"
    files.mkdir()
    (files / "src-main-py.md").write_text("# src/main.py")

    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    from oya.config import load_settings
    load_settings.cache_clear()
    get_settings.cache_clear()
    _reset_db_instance()

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


async def test_get_overview_page(client, workspace_with_wiki):
    """GET /api/wiki/overview returns overview page."""
    response = await client.get("/api/wiki/overview")

    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "Project Overview" in data["content"]
    assert data["page_type"] == "overview"


async def test_get_architecture_page(client, workspace_with_wiki):
    """GET /api/wiki/architecture returns architecture page."""
    response = await client.get("/api/wiki/architecture")

    assert response.status_code == 200
    data = response.json()
    assert "Architecture" in data["content"]


async def test_get_workflow_page(client, workspace_with_wiki):
    """GET /api/wiki/workflows/{slug} returns workflow page."""
    response = await client.get("/api/wiki/workflows/authentication")

    assert response.status_code == 200
    data = response.json()
    assert "Authentication" in data["content"]


async def test_get_directory_page(client, workspace_with_wiki):
    """GET /api/wiki/directories/{slug} returns directory page."""
    response = await client.get("/api/wiki/directories/src")

    assert response.status_code == 200
    data = response.json()
    assert "src" in data["content"]


async def test_get_file_page(client, workspace_with_wiki):
    """GET /api/wiki/files/{slug} returns file page."""
    response = await client.get("/api/wiki/files/src-main-py")

    assert response.status_code == 200
    data = response.json()
    assert "main.py" in data["content"]


async def test_get_nonexistent_page_returns_404(client, workspace_with_wiki):
    """GET /api/wiki/workflows/{nonexistent} returns 404."""
    response = await client.get("/api/wiki/workflows/nonexistent")

    assert response.status_code == 404


async def test_get_wiki_tree(client, workspace_with_wiki):
    """GET /api/wiki/tree returns full wiki structure."""
    response = await client.get("/api/wiki/tree")

    assert response.status_code == 200
    data = response.json()
    assert "overview" in data
    assert "architecture" in data
    assert "workflows" in data
    assert "directories" in data
    assert "files" in data
