"""Tests for IssuesStore."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def issues_store():
    """Create a temporary IssuesStore for testing."""
    from oya.vectorstore.issues import IssuesStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = IssuesStore(Path(tmpdir))
        yield store
        store.close()


class TestIssuesStore:
    """Tests for IssuesStore."""

    def test_add_issues_for_file(self, issues_store):
        """Can add issues for a file."""
        from oya.generation.summaries import FileIssue

        issues = [
            FileIssue(
                file_path="src/api.py",
                category="security",
                severity="problem",
                title="SQL injection",
                description="Use parameterized queries",
                line_range=(10, 12),
            ),
            FileIssue(
                file_path="src/api.py",
                category="reliability",
                severity="suggestion",
                title="Missing error handling",
                description="Add try/except",
            ),
        ]

        issues_store.add_issues("src/api.py", issues)

        # Verify issues were added
        results = issues_store.query_issues()
        assert len(results) == 2

    def test_delete_issues_for_file(self, issues_store):
        """Can delete issues for a specific file."""
        from oya.generation.summaries import FileIssue

        # Add issues for two files
        issues_store.add_issues("file1.py", [
            FileIssue(
                file_path="file1.py",
                category="security",
                severity="problem",
                title="Issue 1",
                description="Desc",
            ),
        ])
        issues_store.add_issues("file2.py", [
            FileIssue(
                file_path="file2.py",
                category="reliability",
                severity="suggestion",
                title="Issue 2",
                description="Desc",
            ),
        ])

        # Delete issues for file1
        issues_store.delete_issues_for_file("file1.py")

        # Only file2 issues remain
        results = issues_store.query_issues()
        assert len(results) == 1
        assert results[0]["file_path"] == "file2.py"

    def test_query_issues_by_category(self, issues_store):
        """Can filter issues by category."""
        from oya.generation.summaries import FileIssue

        issues_store.add_issues("test.py", [
            FileIssue(
                file_path="test.py",
                category="security",
                severity="problem",
                title="Security issue",
                description="Desc",
            ),
            FileIssue(
                file_path="test.py",
                category="reliability",
                severity="problem",
                title="Reliability issue",
                description="Desc",
            ),
        ])

        security_issues = issues_store.query_issues(category="security")
        assert len(security_issues) == 1
        assert security_issues[0]["category"] == "security"

    def test_query_issues_by_severity(self, issues_store):
        """Can filter issues by severity."""
        from oya.generation.summaries import FileIssue

        issues_store.add_issues("test.py", [
            FileIssue(
                file_path="test.py",
                category="security",
                severity="problem",
                title="Critical",
                description="Desc",
            ),
            FileIssue(
                file_path="test.py",
                category="security",
                severity="suggestion",
                title="Nice to have",
                description="Desc",
            ),
        ])

        problems = issues_store.query_issues(severity="problem")
        assert len(problems) == 1
        assert problems[0]["severity"] == "problem"

    def test_query_issues_semantic_search(self, issues_store):
        """Can search issues semantically."""
        from oya.generation.summaries import FileIssue

        issues_store.add_issues("auth.py", [
            FileIssue(
                file_path="auth.py",
                category="security",
                severity="problem",
                title="SQL injection vulnerability",
                description="Query built with string concatenation allows injection attacks",
            ),
        ])
        issues_store.add_issues("utils.py", [
            FileIssue(
                file_path="utils.py",
                category="maintainability",
                severity="suggestion",
                title="Function too long",
                description="Consider breaking into smaller functions",
            ),
        ])

        # Search for injection-related issues
        results = issues_store.query_issues(query="injection attack")
        assert len(results) >= 1
        assert results[0]["title"] == "SQL injection vulnerability"

    def test_clear(self, issues_store):
        """Can clear all issues."""
        from oya.generation.summaries import FileIssue

        issues_store.add_issues("test.py", [
            FileIssue(
                file_path="test.py",
                category="security",
                severity="problem",
                title="Issue",
                description="Desc",
            ),
        ])

        issues_store.clear()

        results = issues_store.query_issues()
        assert len(results) == 0
