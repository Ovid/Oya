"""Notes API endpoint tests."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from oya.main import app
from oya.api.routers.notes import get_notes_service
from oya.notes.schemas import Note, NoteScope


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_notes_service():
    """Mock NotesService with dependency override."""
    service = MagicMock()
    app.dependency_overrides[get_notes_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


class TestListNotes:
    """Tests for GET /api/notes."""

    def test_returns_all_notes(self, client, mock_notes_service):
        """Returns list of all notes."""
        mock_notes_service.list.return_value = [
            Note(
                id=1,
                scope=NoteScope.FILE,
                target="src/main.py",
                content="Content 1",
                author=None,
                updated_at="2024-01-01T00:00:00",
            ),
        ]

        response = client.get("/api/notes")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["target"] == "src/main.py"

    def test_filters_by_scope(self, client, mock_notes_service):
        """Filters by scope query parameter."""
        mock_notes_service.list.return_value = []

        client.get("/api/notes?scope=file")

        mock_notes_service.list.assert_called_once_with(NoteScope.FILE)


class TestGetNote:
    """Tests for GET /api/notes/{scope}/{target}."""

    def test_returns_note(self, client, mock_notes_service):
        """Returns note by scope and target."""
        mock_notes_service.get.return_value = Note(
            id=1,
            scope=NoteScope.FILE,
            target="src/main.py",
            content="Test content",
            author="alice",
            updated_at="2024-01-01T00:00:00",
        )

        response = client.get("/api/notes/file/src/main.py")

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Test content"
        assert data["author"] == "alice"

    def test_returns_404_when_not_found(self, client, mock_notes_service):
        """Returns 404 when note doesn't exist."""
        mock_notes_service.get.return_value = None

        response = client.get("/api/notes/file/nonexistent.py")

        assert response.status_code == 404


class TestUpsertNote:
    """Tests for PUT /api/notes/{scope}/{target}."""

    def test_creates_note(self, client, mock_notes_service):
        """Creates new note."""
        mock_notes_service.upsert.return_value = Note(
            id=1,
            scope=NoteScope.FILE,
            target="src/main.py",
            content="New content",
            author=None,
            updated_at="2024-01-01T00:00:00",
        )

        response = client.put(
            "/api/notes/file/src/main.py",
            json={"content": "New content"},
        )

        assert response.status_code == 200
        mock_notes_service.upsert.assert_called_once()

    def test_updates_existing_note(self, client, mock_notes_service):
        """Updates existing note."""
        mock_notes_service.upsert.return_value = Note(
            id=1,
            scope=NoteScope.FILE,
            target="src/main.py",
            content="Updated content",
            author="bob",
            updated_at="2024-01-02T00:00:00",
        )

        response = client.put(
            "/api/notes/file/src/main.py",
            json={"content": "Updated content", "author": "bob"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated content"


class TestDeleteNote:
    """Tests for DELETE /api/notes/{scope}/{target}."""

    def test_deletes_note(self, client, mock_notes_service):
        """Deletes note successfully."""
        mock_notes_service.delete.return_value = True

        response = client.delete("/api/notes/file/src/main.py")

        assert response.status_code == 204

    def test_returns_404_when_not_found(self, client, mock_notes_service):
        """Returns 404 when note doesn't exist."""
        mock_notes_service.delete.return_value = False

        response = client.delete("/api/notes/file/nonexistent.py")

        assert response.status_code == 404
