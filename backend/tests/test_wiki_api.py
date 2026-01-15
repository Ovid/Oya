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
    wiki_path = workspace / ".oyawiki" / "wiki"
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


class TestSourcePathExtraction:
    """Tests for source_path extraction from wiki page content."""

    async def test_file_page_extracts_source_path_from_backticks(self, client, workspace_with_wiki):
        """File page extracts source_path from backtick-quoted title."""
        wiki_path = workspace_with_wiki / ".oyawiki" / "wiki" / "files"
        (wiki_path / "lib-utils-py.md").write_text("# `lib/utils.py`\n\nUtility functions.")

        response = await client.get("/api/wiki/files/lib-utils-py")

        assert response.status_code == 200
        data = response.json()
        assert data["source_path"] == "lib/utils.py"

    async def test_file_page_extracts_source_path_from_double_quotes(
        self, client, workspace_with_wiki
    ):
        """File page extracts source_path from double-quoted title."""
        wiki_path = workspace_with_wiki / ".oyawiki" / "wiki" / "files"
        (wiki_path / "src-app-ts.md").write_text('# "src/app.ts"\n\nMain app.')

        response = await client.get("/api/wiki/files/src-app-ts")

        assert response.status_code == 200
        data = response.json()
        assert data["source_path"] == "src/app.ts"

    async def test_file_page_extracts_source_path_from_single_quotes(
        self, client, workspace_with_wiki
    ):
        """File page extracts source_path from single-quoted title."""
        wiki_path = workspace_with_wiki / ".oyawiki" / "wiki" / "files"
        (wiki_path / "config-json.md").write_text("# 'config.json'\n\nConfiguration.")

        response = await client.get("/api/wiki/files/config-json")

        assert response.status_code == 200
        data = response.json()
        assert data["source_path"] == "config.json"

    async def test_directory_page_extracts_source_path(self, client, workspace_with_wiki):
        """Directory page extracts source_path from title."""
        wiki_path = workspace_with_wiki / ".oyawiki" / "wiki" / "directories"
        (wiki_path / "src-components.md").write_text("# `src/components`\n\nReact components.")

        response = await client.get("/api/wiki/directories/src-components")

        assert response.status_code == 200
        data = response.json()
        assert data["source_path"] == "src/components"

    async def test_file_page_without_quoted_title_returns_null_source_path(
        self, client, workspace_with_wiki
    ):
        """File page without quoted title returns null source_path."""
        # The existing src-main-py.md has "# src/main.py" without backticks
        response = await client.get("/api/wiki/files/src-main-py")

        assert response.status_code == 200
        data = response.json()
        assert data["source_path"] is None

    async def test_overview_page_has_null_source_path(self, client, workspace_with_wiki):
        """Overview page has null source_path."""
        response = await client.get("/api/wiki/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["source_path"] is None

    async def test_architecture_page_has_null_source_path(self, client, workspace_with_wiki):
        """Architecture page has null source_path."""
        response = await client.get("/api/wiki/architecture")

        assert response.status_code == 200
        data = response.json()
        assert data["source_path"] is None
