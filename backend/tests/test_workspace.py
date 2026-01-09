"""Property-based tests for workspace initialization.

Feature: oya-config-improvements
"""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st


# Required subdirectories that must be created in .oyawiki/
REQUIRED_SUBDIRS = ["wiki", "notes", "meta", "index", "cache", "config"]


class TestWorkspaceInitialization:
    """Property 1: Workspace Initialization Creates Directory Structure
    
    For any valid workspace path that does not contain a `.oyawiki/` directory,
    calling `initialize_workspace()` SHALL create the `.oyawiki/` directory with
    all required subdirectories (wiki, notes, meta, index, cache, config).
    
    Validates: Requirements 2.2
    """

    @given(subdir_name=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
        min_size=1,
        max_size=20
    ).filter(lambda x: x.strip() and not x.startswith("-")))
    @settings(max_examples=100)
    def test_workspace_initialization_creates_all_required_directories(self, subdir_name):
        """Feature: oya-config-improvements, Property 1: Workspace initialization creates directory structure
        
        For any valid workspace path, initialize_workspace() creates .oyawiki/ 
        with all required subdirectories.
        """
        from oya.workspace import initialize_workspace
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a workspace directory with a random subdirectory name
            workspace_path = Path(tmpdir) / subdir_name
            workspace_path.mkdir(parents=True, exist_ok=True)
            
            # Ensure .oyawiki doesn't exist yet
            oyawiki_path = workspace_path / ".oyawiki"
            assert not oyawiki_path.exists()
            
            # Initialize workspace
            result = initialize_workspace(workspace_path)
            
            # Should return True on success
            assert result is True
            
            # .oyawiki directory should exist
            assert oyawiki_path.exists()
            assert oyawiki_path.is_dir()
            
            # All required subdirectories should exist
            for subdir in REQUIRED_SUBDIRS:
                subdir_path = oyawiki_path / subdir
                assert subdir_path.exists(), f"Missing required subdirectory: {subdir}"
                assert subdir_path.is_dir(), f"{subdir} should be a directory"

    @given(st.data())
    @settings(max_examples=100)
    def test_workspace_initialization_is_idempotent(self, data):
        """Feature: oya-config-improvements, Property 1: Workspace initialization creates directory structure
        
        Calling initialize_workspace() multiple times should be safe and idempotent.
        """
        from oya.workspace import initialize_workspace
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir) / "workspace"
            workspace_path.mkdir()
            
            # Initialize multiple times
            num_calls = data.draw(st.integers(min_value=1, max_value=5))
            for _ in range(num_calls):
                result = initialize_workspace(workspace_path)
                assert result is True
            
            # All directories should still exist
            oyawiki_path = workspace_path / ".oyawiki"
            assert oyawiki_path.exists()
            
            for subdir in REQUIRED_SUBDIRS:
                subdir_path = oyawiki_path / subdir
                assert subdir_path.exists()
                assert subdir_path.is_dir()

    def test_workspace_initialization_returns_false_on_permission_error(self):
        """Feature: oya-config-improvements, Property 1: Workspace initialization creates directory structure
        
        If workspace initialization fails due to permissions, it should return False
        and not raise an exception.
        """
        from oya.workspace import initialize_workspace
        
        # Use a path that doesn't exist and can't be created
        # This tests the error handling path
        invalid_path = Path("/nonexistent/path/that/cannot/exist")
        
        # Should return False, not raise an exception
        result = initialize_workspace(invalid_path)
        assert result is False
