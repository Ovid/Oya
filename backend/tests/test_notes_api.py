"""Notes API endpoint tests."""

import subprocess
import pytest
from unittest.mock import MagicMock
from datetime import datetime, UTC
from httpx import ASGITransport, AsyncClient

from oya.main import app
from oya.notes.schemas import Note, NoteScope


@pytest.fixture
def workspace(setup_active_repo):
    """Create workspace with notes directory using active repo fixture."""
    wiki_path = setup_active_repo["wiki_path"]
    source_path = setup_active_repo["source_path"]

    # Initialize git in source directory
    source_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=source_path, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=source_path, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=source_path, capture_output=True)
    (source_path / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=source_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=source_path, capture_output=True)

    # Create notes directory in wiki
    (wiki_path.parent / "notes").mkdir(exist_ok=True)

    return setup_active_repo


@pytest.fixture
def mock_notes_service():
    """Mock NotesService for testing."""
    service = MagicMock()
    service.create.return_value = Note(
        id=1,
        filepath="2024-01-01-file-src-main-py.md",
        scope=NoteScope.FILE,
        target="src/main.py",
        content="Test correction content",
        author="test@test.com",
        created_at=datetime.now(UTC),
    )
    service.list_by_target.return_value = [
        Note(
            id=1,
            filepath="note1.md",
            scope=NoteScope.FILE,
            target="src/main.py",
            content="Note 1",
            author=None,
            created_at=datetime.now(UTC),
        ),
    ]
    return service


class TestNotesEndpoints:
    """Tests for notes API endpoints."""

    @pytest.mark.asyncio
    async def test_create_note_returns_created(self, workspace, mock_notes_service):
        """POST /api/notes creates a note and returns 201."""
        from oya.api.routers.notes import get_notes_service

        app.dependency_overrides[get_notes_service] = lambda: mock_notes_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/api/notes",
                    json={
                        "scope": "file",
                        "target": "src/main.py",
                        "content": "This needs refactoring.",
                    },
                )

            assert response.status_code == 201
            data = response.json()
            assert "id" in data
            assert data["scope"] == "file"
            assert data["target"] == "src/main.py"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_create_note_requires_content(self, workspace):
        """POST /api/notes requires content field."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/notes",
                json={
                    "scope": "file",
                    "target": "src/main.py",
                    # Missing content
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_note_validates_scope(self, workspace):
        """POST /api/notes validates scope enum."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/notes",
                json={
                    "scope": "invalid_scope",
                    "target": "src/main.py",
                    "content": "Test",
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_notes_by_target(self, workspace, mock_notes_service):
        """GET /api/notes?target=path lists notes for target."""
        from oya.api.routers.notes import get_notes_service

        app.dependency_overrides[get_notes_service] = lambda: mock_notes_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/notes?target=src/main.py")

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            mock_notes_service.list_by_target.assert_called_with("src/main.py")
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_list_notes_without_target(self, workspace, mock_notes_service):
        """GET /api/notes without target lists all notes."""
        from oya.api.routers.notes import get_notes_service

        app.dependency_overrides[get_notes_service] = lambda: mock_notes_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/notes")

            assert response.status_code == 200
            mock_notes_service.list_by_target.assert_called_with(None)
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_note_by_id(self, workspace, mock_notes_service):
        """GET /api/notes/{id} returns single note."""
        from oya.api.routers.notes import get_notes_service

        mock_notes_service.get.return_value = Note(
            id=1,
            filepath="note.md",
            scope=NoteScope.FILE,
            target="src/main.py",
            content="Full content",
            author=None,
            created_at=datetime.now(UTC),
        )

        app.dependency_overrides[get_notes_service] = lambda: mock_notes_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/notes/1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["content"] == "Full content"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_nonexistent_note_returns_404(self, workspace, mock_notes_service):
        """GET /api/notes/{id} returns 404 for missing note."""
        from oya.api.routers.notes import get_notes_service

        mock_notes_service.get.return_value = None

        app.dependency_overrides[get_notes_service] = lambda: mock_notes_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.get("/api/notes/999")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_note(self, workspace, mock_notes_service):
        """DELETE /api/notes/{id} deletes note."""
        from oya.api.routers.notes import get_notes_service

        mock_notes_service.delete.return_value = True

        app.dependency_overrides[get_notes_service] = lambda: mock_notes_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.delete("/api/notes/1")

            assert response.status_code == 204
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_note_returns_404(self, workspace, mock_notes_service):
        """DELETE /api/notes/{id} returns 404 for missing note."""
        from oya.api.routers.notes import get_notes_service

        mock_notes_service.delete.return_value = False

        app.dependency_overrides[get_notes_service] = lambda: mock_notes_service
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.delete("/api/notes/999")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()
