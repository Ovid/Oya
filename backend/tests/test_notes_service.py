"""Notes service tests."""

import pytest
from unittest.mock import MagicMock

from oya.notes.service import NotesService, _slugify_path, _get_filepath
from oya.notes.schemas import NoteScope


class TestSlugifyPath:
    """Tests for path slugification."""

    def test_replaces_slashes_with_double_dash(self):
        assert _slugify_path("src/main.py") == "src--main.py"

    def test_handles_nested_paths(self):
        assert _slugify_path("src/api/routers/notes.py") == "src--api--routers--notes.py"

    def test_empty_path_returns_empty(self):
        assert _slugify_path("") == ""

    def test_removes_special_characters(self):
        assert _slugify_path("src/[test]/file.py") == "src--test--file.py"


class TestGetFilepath:
    """Tests for filepath generation."""

    def test_general_scope_returns_general_md(self):
        assert _get_filepath(NoteScope.GENERAL, "") == "general.md"

    def test_file_scope_uses_files_subdirectory(self):
        assert _get_filepath(NoteScope.FILE, "src/main.py") == "files/src--main.py.md"

    def test_directory_scope_uses_directories_subdirectory(self):
        assert _get_filepath(NoteScope.DIRECTORY, "src/api") == "directorys/src--api.md"

    def test_workflow_scope_uses_workflows_subdirectory(self):
        assert _get_filepath(NoteScope.WORKFLOW, "auth") == "workflows/auth.md"


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create temporary workspace with notes directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    notes_path = workspace / ".oyawiki" / "notes"
    notes_path.mkdir(parents=True)
    return workspace


@pytest.fixture
def mock_db():
    """Mock database for testing."""
    db = MagicMock()
    # Setup for upsert returning the note
    db.execute.return_value.fetchone.return_value = {
        "id": 1,
        "scope": "file",
        "target": "src/main.py",
        "filepath": "files/src--main.py.md",
        "content": "Test content",
        "author": None,
        "updated_at": "2024-01-01T00:00:00+00:00",
    }
    return db


@pytest.fixture
def notes_service(tmp_workspace, mock_db):
    """Create notes service for testing."""
    notes_path = tmp_workspace / ".oyawiki" / "notes"
    return NotesService(notes_path, mock_db)


class TestNotesServiceUpsert:
    """Tests for note upsert."""

    def test_creates_note_file(self, notes_service, tmp_workspace):
        """Upserting a note creates file on disk."""
        notes_service.upsert(
            scope=NoteScope.FILE,
            target="src/main.py",
            content="This function should use async/await pattern.",
        )

        # Check file exists in correct location
        notes_path = tmp_workspace / ".oyawiki" / "notes"
        note_file = notes_path / "files" / "src--main.py.md"
        assert note_file.exists()

        # Check content
        content = note_file.read_text()
        assert "scope: file" in content
        assert "target: src/main.py" in content
        assert "async/await pattern" in content

    def test_includes_frontmatter_metadata(self, notes_service, tmp_workspace):
        """Note file includes YAML frontmatter with metadata."""
        notes_service.upsert(
            scope=NoteScope.WORKFLOW,
            target="authentication",
            content="Auth flow needs two-factor support.",
            author="test@example.com",
        )

        notes_path = tmp_workspace / ".oyawiki" / "notes"
        note_file = notes_path / "workflows" / "authentication.md"
        content = note_file.read_text()

        assert content.startswith("---")
        assert "scope: workflow" in content
        assert "target: authentication" in content
        assert "author: test@example.com" in content
        assert "updated_at:" in content

    def test_upserts_to_database(self, notes_service, mock_db):
        """Upserting inserts or updates database record."""
        notes_service.upsert(
            scope=NoteScope.FILE,
            target="src/api.py",
            content="API needs rate limiting.",
        )

        mock_db.execute.assert_called()
        # Should use INSERT...ON CONFLICT
        call_sql = mock_db.execute.call_args_list[0][0][0].lower()
        assert "insert" in call_sql
        assert "on conflict" in call_sql

    def test_returns_note_object(self, notes_service):
        """Upsert returns Note with all fields."""
        note = notes_service.upsert(
            scope=NoteScope.GENERAL,
            target="",
            content="General project guidelines.",
        )

        assert note.id is not None
        assert note.scope == NoteScope.FILE  # From mock
        assert note.content == "Test content"  # From mock


class TestNotesServiceGet:
    """Tests for getting notes."""

    def test_gets_note_by_scope_and_target(self, notes_service, mock_db):
        """Gets note by scope and target."""
        note = notes_service.get(NoteScope.FILE, "src/main.py")

        assert note is not None
        assert note.id == 1
        assert note.content == "Test content"

    def test_returns_none_when_not_found(self, notes_service, mock_db):
        """Returns None when note doesn't exist."""
        mock_db.execute.return_value.fetchone.return_value = None

        note = notes_service.get(NoteScope.FILE, "nonexistent.py")

        assert note is None


class TestNotesServiceDelete:
    """Tests for deleting notes."""

    def test_deletes_note_file(self, notes_service, tmp_workspace, mock_db):
        """Deleting a note removes the file."""
        # Create a note file
        notes_path = tmp_workspace / ".oyawiki" / "notes"
        files_dir = notes_path / "files"
        files_dir.mkdir(exist_ok=True)
        note_file = files_dir / "src--main.py.md"
        note_file.write_text("Test content")

        mock_db.execute.return_value.fetchone.return_value = {
            "id": 1,
            "scope": "file",
            "target": "src/main.py",
            "filepath": "files/src--main.py.md",
            "content": "Test",
            "author": None,
            "updated_at": "2024-01-01T00:00:00",
        }

        result = notes_service.delete(NoteScope.FILE, "src/main.py")

        assert result is True
        assert not note_file.exists()

    def test_returns_false_when_not_found(self, notes_service, mock_db):
        """Returns False when note doesn't exist."""
        mock_db.execute.return_value.fetchone.return_value = None

        result = notes_service.delete(NoteScope.FILE, "nonexistent.py")

        assert result is False


class TestNotesServiceList:
    """Tests for listing notes."""

    def test_lists_all_notes(self, notes_service, mock_db):
        """Lists all notes when no scope filter."""
        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "scope": "file",
                "target": "src/a.py",
                "filepath": "files/src--a.py.md",
                "content": "A",
                "author": None,
                "updated_at": "2024-01-01T00:00:00",
            },
            {
                "id": 2,
                "scope": "directory",
                "target": "src/utils",
                "filepath": "directories/src--utils.md",
                "content": "B",
                "author": None,
                "updated_at": "2024-01-02T00:00:00",
            },
        ]

        notes = notes_service.list()

        assert len(notes) == 2

    def test_filters_by_scope(self, notes_service, mock_db):
        """Lists notes filtered by scope."""
        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "scope": "file",
                "target": "src/a.py",
                "filepath": "files/src--a.py.md",
                "content": "A",
                "author": None,
                "updated_at": "2024-01-01T00:00:00",
            },
        ]

        notes_service.list(NoteScope.FILE)

        # Verify scope was passed to query
        call_args = mock_db.execute.call_args[0]
        assert "file" in call_args[1]
