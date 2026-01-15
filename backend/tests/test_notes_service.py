"""Notes service tests."""

import pytest
from unittest.mock import MagicMock

from oya.notes.service import NotesService
from oya.notes.schemas import (
    NoteCreate,
    NoteScope,
)


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
    db.execute.return_value.lastrowid = 1
    return db


@pytest.fixture
def notes_service(tmp_workspace, mock_db):
    """Create notes service for testing."""
    notes_path = tmp_workspace / ".oyawiki" / "notes"
    return NotesService(notes_path, mock_db)


class TestNotesServiceCreate:
    """Tests for note creation."""

    def test_creates_note_file(self, notes_service, tmp_workspace):
        """Creating a note saves file to disk."""
        note_data = NoteCreate(
            scope=NoteScope.FILE,
            target="src/main.py",
            content="This function should use async/await pattern.",
        )

        notes_service.create(note_data)

        # Check file exists
        notes_path = tmp_workspace / ".oyawiki" / "notes"
        files = list(notes_path.glob("*.md"))
        assert len(files) == 1

        # Check content
        content = files[0].read_text()
        assert "scope: file" in content
        assert "target: src/main.py" in content
        assert "async/await pattern" in content

    def test_generates_correct_filename(self, notes_service, tmp_workspace):
        """Note filename follows format: {timestamp}-{scope}-{slug}.md"""
        note_data = NoteCreate(
            scope=NoteScope.DIRECTORY,
            target="src/utils",
            content="All utilities should be pure functions.",
        )

        notes_service.create(note_data)

        notes_path = tmp_workspace / ".oyawiki" / "notes"
        files = list(notes_path.glob("*.md"))
        filename = files[0].name

        # Should contain timestamp, scope, and slug
        assert "-directory-" in filename
        assert filename.endswith(".md")

    def test_includes_frontmatter_metadata(self, notes_service, tmp_workspace):
        """Note file includes YAML frontmatter with metadata."""
        note_data = NoteCreate(
            scope=NoteScope.WORKFLOW,
            target="authentication",
            content="Auth flow needs two-factor support.",
            author="test@example.com",
        )

        notes_service.create(note_data)

        notes_path = tmp_workspace / ".oyawiki" / "notes"
        files = list(notes_path.glob("*.md"))
        content = files[0].read_text()

        # Check frontmatter exists
        assert content.startswith("---")
        assert "scope: workflow" in content
        assert "target: authentication" in content
        assert "author: test@example.com" in content
        assert "created_at:" in content

    def test_stores_note_in_database(self, notes_service, mock_db):
        """Creating a note inserts record in database."""
        note_data = NoteCreate(
            scope=NoteScope.FILE,
            target="src/api.py",
            content="API needs rate limiting.",
        )

        notes_service.create(note_data)

        mock_db.execute.assert_called()
        # Should insert into notes table
        call_sql = mock_db.execute.call_args[0][0].lower()
        assert "insert" in call_sql
        assert "notes" in call_sql

    def test_returns_note_with_id(self, notes_service):
        """Created note has ID and all fields populated."""
        note_data = NoteCreate(
            scope=NoteScope.GENERAL,
            target="",
            content="General project guidelines.",
        )

        note = notes_service.create(note_data)

        assert note.id is not None
        assert note.scope == NoteScope.GENERAL
        assert note.content == "General project guidelines."
        assert note.created_at is not None


class TestNotesServiceList:
    """Tests for listing notes."""

    def test_lists_notes_by_target(self, notes_service, mock_db):
        """Lists notes filtered by target path."""
        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "filepath": "2024-01-01-file-src-main-py.md",
                "scope": "file",
                "target": "src/main.py",
                "content": "Note 1",
                "author": "test@example.com",
                "created_at": "2024-01-01T00:00:00",
            },
            {
                "id": 2,
                "filepath": "2024-01-02-file-src-main-py.md",
                "scope": "file",
                "target": "src/main.py",
                "content": "Note 2",
                "author": None,
                "created_at": "2024-01-02T00:00:00",
            },
        ]

        notes = notes_service.list_by_target("src/main.py")

        assert len(notes) == 2
        assert all(n.target == "src/main.py" for n in notes)

    def test_lists_all_notes_when_no_target(self, notes_service, mock_db):
        """Lists all notes when target is None."""
        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "filepath": "note1.md",
                "scope": "file",
                "target": "src/a.py",
                "content": "A",
                "author": None,
                "created_at": "2024-01-01T00:00:00",
            },
            {
                "id": 2,
                "filepath": "note2.md",
                "scope": "directory",
                "target": "src/utils",
                "content": "B",
                "author": None,
                "created_at": "2024-01-02T00:00:00",
            },
        ]

        notes = notes_service.list_by_target(None)

        assert len(notes) == 2

    def test_returns_empty_list_when_no_notes(self, notes_service, mock_db):
        """Returns empty list when no notes match."""
        mock_db.execute.return_value.fetchall.return_value = []

        notes = notes_service.list_by_target("nonexistent/path.py")

        assert notes == []


class TestNotesServiceGet:
    """Tests for getting individual notes."""

    def test_gets_note_by_id(self, notes_service, mock_db, tmp_workspace):
        """Gets note by ID returns full content."""
        # Create a note file
        notes_path = tmp_workspace / ".oyawiki" / "notes"
        (notes_path / "test-note.md").write_text("""---
scope: file
target: src/main.py
author: test@example.com
created_at: 2024-01-01T00:00:00
---
Full note content here.
""")

        mock_db.execute.return_value.fetchone.return_value = {
            "id": 1,
            "filepath": "test-note.md",
            "scope": "file",
            "target": "src/main.py",
            "content": "Full note content here.",
            "author": "test@example.com",
            "created_at": "2024-01-01T00:00:00",
        }

        note = notes_service.get(1)

        assert note is not None
        assert note.id == 1
        assert note.content == "Full note content here."

    def test_returns_none_for_nonexistent_id(self, notes_service, mock_db):
        """Returns None when note ID doesn't exist."""
        mock_db.execute.return_value.fetchone.return_value = None

        note = notes_service.get(999)

        assert note is None


class TestNotesServiceDelete:
    """Tests for deleting notes."""

    def test_deletes_note_file(self, notes_service, tmp_workspace, mock_db):
        """Deleting a note removes the file."""
        # Create a note file
        notes_path = tmp_workspace / ".oyawiki" / "notes"
        note_file = notes_path / "test-note.md"
        note_file.write_text("Test content")

        mock_db.execute.return_value.fetchone.return_value = {
            "id": 1,
            "filepath": "test-note.md",
            "scope": "file",
            "target": "src/main.py",
            "content": "Test",
            "author": None,
            "created_at": "2024-01-01T00:00:00",
        }

        result = notes_service.delete(1)

        assert result is True
        assert not note_file.exists()

    def test_deletes_database_record(self, notes_service, mock_db, tmp_workspace):
        """Deleting a note removes database record."""
        notes_path = tmp_workspace / ".oyawiki" / "notes"
        (notes_path / "test.md").write_text("Test")

        mock_db.execute.return_value.fetchone.return_value = {
            "id": 1,
            "filepath": "test.md",
            "scope": "file",
            "target": "src/main.py",
            "content": "Test",
            "author": None,
            "created_at": "2024-01-01T00:00:00",
        }

        notes_service.delete(1)

        # Check DELETE was called
        calls = [str(c) for c in mock_db.execute.call_args_list]
        delete_called = any("delete" in c.lower() for c in calls)
        assert delete_called

    def test_returns_false_for_nonexistent(self, notes_service, mock_db):
        """Returns False when note doesn't exist."""
        mock_db.execute.return_value.fetchone.return_value = None

        result = notes_service.delete(999)

        assert result is False
