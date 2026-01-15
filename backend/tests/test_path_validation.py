"""Property-based tests for path validation.

Feature: oya-config-improvements

Tests for:
- Property 2: Invalid path rejection
- Property 3: Base path security enforcement
- Property 4: Path canonicalization security
"""

import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st


class TestInvalidPathRejection:
    """Property 2: Invalid Path Rejection

    For any path string that either does not exist on the filesystem OR exists
    but is not a directory, the workspace switch endpoint SHALL return a 400
    error response.

    Validates: Requirements 4.6, 4.7
    """

    @given(
        path_suffix=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=30
        ).filter(lambda x: x.strip() and not x.startswith("-"))
    )
    @settings(max_examples=100, deadline=None)
    def test_nonexistent_paths_are_rejected(self, path_suffix):
        """Feature: oya-config-improvements, Property 2: Invalid path rejection

        For any path that does not exist, validate_workspace_path() should
        return is_valid=False with appropriate error message.
        """
        from oya.api.deps import validate_workspace_path

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            # Create a path that doesn't exist
            nonexistent_path = str(base_path / "nonexistent" / path_suffix)

            is_valid, error_msg, resolved_path = validate_workspace_path(
                nonexistent_path, base_path
            )

            assert is_valid is False
            assert "does not exist" in error_msg.lower()
            assert resolved_path is None

    @given(
        filename=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-.", min_size=1, max_size=20
        ).filter(lambda x: x.strip() and not x.startswith("-") and not x.startswith("."))
    )
    @settings(max_examples=100, deadline=None)
    def test_file_paths_are_rejected(self, filename):
        """Feature: oya-config-improvements, Property 2: Invalid path rejection

        For any path that exists but is a file (not a directory),
        validate_workspace_path() should return is_valid=False.
        """
        from oya.api.deps import validate_workspace_path

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            # Create a file, not a directory
            file_path = base_path / filename
            file_path.write_text("test content")

            is_valid, error_msg, resolved_path = validate_workspace_path(str(file_path), base_path)

            assert is_valid is False
            assert "not a directory" in error_msg.lower()
            assert resolved_path is None


class TestBasePathSecurityEnforcement:
    """Property 3: Base Path Security Enforcement

    For any path string, after resolving to its canonical form, if the path is
    not under the configured `WORKSPACE_BASE_PATH` (or user home directory if
    unconfigured), the workspace switch endpoint SHALL return a 403 error response.

    Validates: Requirements 4.9, 4.11
    """

    @given(
        subdir=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20
        ).filter(lambda x: x.strip() and not x.startswith("-"))
    )
    @settings(max_examples=100, deadline=None)
    def test_paths_inside_base_are_accepted(self, subdir):
        """Feature: oya-config-improvements, Property 3: Base path security enforcement

        For any valid directory path that is under the base path,
        validate_workspace_path() should return is_valid=True.
        """
        from oya.api.deps import validate_workspace_path

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir).resolve()
            # Create a valid directory inside base path
            valid_dir = base_path / subdir
            valid_dir.mkdir(parents=True, exist_ok=True)

            is_valid, error_msg, resolved_path = validate_workspace_path(str(valid_dir), base_path)

            assert is_valid is True
            assert error_msg == ""
            assert resolved_path == valid_dir.resolve()

    @given(
        subdir=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20
        ).filter(lambda x: x.strip() and not x.startswith("-"))
    )
    @settings(max_examples=100, deadline=None)
    def test_paths_outside_base_are_rejected(self, subdir):
        """Feature: oya-config-improvements, Property 3: Base path security enforcement

        For any path that is outside the base path,
        validate_workspace_path() should return is_valid=False with security error.
        """
        from oya.api.deps import validate_workspace_path

        with tempfile.TemporaryDirectory() as base_tmpdir:
            with tempfile.TemporaryDirectory() as outside_tmpdir:
                base_path = Path(base_tmpdir).resolve()
                # Create a directory outside the base path
                outside_dir = Path(outside_tmpdir) / subdir
                outside_dir.mkdir(parents=True, exist_ok=True)

                is_valid, error_msg, resolved_path = validate_workspace_path(
                    str(outside_dir), base_path
                )

                assert is_valid is False
                assert "outside" in error_msg.lower()
                assert resolved_path is None

    def test_get_workspace_base_path_uses_env_var(self, monkeypatch):
        """Feature: oya-config-improvements, Property 3: Base path security enforcement

        get_workspace_base_path() should return the WORKSPACE_BASE_PATH env var
        when configured.
        """
        from oya.api.deps import get_workspace_base_path

        with tempfile.TemporaryDirectory() as tmpdir:
            monkeypatch.setenv("WORKSPACE_BASE_PATH", tmpdir)

            result = get_workspace_base_path()

            assert result == Path(tmpdir).resolve()

    def test_get_workspace_base_path_defaults_to_home(self, monkeypatch):
        """Feature: oya-config-improvements, Property 3: Base path security enforcement

        get_workspace_base_path() should return user home directory when
        WORKSPACE_BASE_PATH is not configured.
        """
        from oya.api.deps import get_workspace_base_path

        monkeypatch.delenv("WORKSPACE_BASE_PATH", raising=False)

        result = get_workspace_base_path()

        assert result == Path.home()


class TestPathCanonicalizationSecurity:
    """Property 4: Path Canonicalization Security

    For any path string containing symlinks, `..` segments, or other path
    traversal patterns, the system SHALL resolve the path to its canonical form
    before validation. If the canonical path of a symlink target is outside the
    allowed base path, the system SHALL return a 403 error.

    Validates: Requirements 4.12, 4.13
    """

    @given(
        subdir=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20
        ).filter(lambda x: x.strip() and not x.startswith("-"))
    )
    @settings(max_examples=100, deadline=None)
    def test_dot_dot_traversal_is_resolved(self, subdir):
        """Feature: oya-config-improvements, Property 4: Path canonicalization security

        Paths with .. segments should be resolved to canonical form before
        validation against base path.
        """
        from oya.api.deps import validate_workspace_path

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir).resolve()
            # Create nested directory structure
            nested_dir = base_path / "level1" / "level2"
            nested_dir.mkdir(parents=True)

            # Path with .. that resolves to level1 (still inside base)
            target_dir = base_path / "level1" / subdir
            target_dir.mkdir(parents=True, exist_ok=True)
            traversal_path = str(nested_dir / ".." / subdir)

            is_valid, error_msg, resolved_path = validate_workspace_path(traversal_path, base_path)

            # Should be valid since resolved path is still inside base
            assert is_valid is True
            assert resolved_path == target_dir.resolve()

    @given(
        subdir=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20
        ).filter(lambda x: x.strip() and not x.startswith("-"))
    )
    @settings(max_examples=100, deadline=None)
    def test_dot_dot_traversal_outside_base_is_rejected(self, subdir):
        """Feature: oya-config-improvements, Property 4: Path canonicalization security

        Paths with .. segments that resolve outside base path should be rejected.
        """
        from oya.api.deps import validate_workspace_path

        with tempfile.TemporaryDirectory() as base_tmpdir:
            with tempfile.TemporaryDirectory() as outside_tmpdir:
                base_path = Path(base_tmpdir).resolve()
                outside_path = Path(outside_tmpdir).resolve()

                # Create a directory outside base
                outside_dir = outside_path / subdir
                outside_dir.mkdir(parents=True, exist_ok=True)

                # Try to access it via .. traversal from inside base
                # This constructs a path like /base/../outside/subdir
                # which resolves to /outside/subdir
                traversal_path = str(base_path / ".." / outside_path.name / subdir)

                is_valid, error_msg, resolved_path = validate_workspace_path(
                    traversal_path, base_path
                )

                assert is_valid is False
                assert "outside" in error_msg.lower()

    def test_symlink_inside_base_is_accepted(self):
        """Feature: oya-config-improvements, Property 4: Path canonicalization security

        Symlinks whose targets are inside the base path should be accepted.
        """
        from oya.api.deps import validate_workspace_path

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir).resolve()

            # Create target directory inside base
            target_dir = base_path / "target"
            target_dir.mkdir()

            # Create symlink to target
            symlink_path = base_path / "link"
            symlink_path.symlink_to(target_dir)

            is_valid, error_msg, resolved_path = validate_workspace_path(
                str(symlink_path), base_path
            )

            assert is_valid is True
            assert resolved_path == target_dir.resolve()

    def test_symlink_outside_base_is_rejected(self):
        """Feature: oya-config-improvements, Property 4: Path canonicalization security

        Symlinks whose targets are outside the base path should be rejected.
        """
        from oya.api.deps import validate_workspace_path

        with tempfile.TemporaryDirectory() as base_tmpdir:
            with tempfile.TemporaryDirectory() as outside_tmpdir:
                base_path = Path(base_tmpdir).resolve()
                outside_path = Path(outside_tmpdir).resolve()

                # Create target directory outside base
                target_dir = outside_path / "target"
                target_dir.mkdir()

                # Create symlink inside base pointing to outside target
                symlink_path = base_path / "malicious_link"
                symlink_path.symlink_to(target_dir)

                is_valid, error_msg, resolved_path = validate_workspace_path(
                    str(symlink_path), base_path
                )

                assert is_valid is False
                assert "outside" in error_msg.lower()
                assert resolved_path is None
