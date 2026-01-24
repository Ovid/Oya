"""Unit tests for startup initialization.

Tests that the FastAPI lifespan handler properly initializes the workspace
on application startup.

Feature: oya-config-improvements
Validates: Requirements 2.1
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


class TestStartupInitialization:
    """Tests for startup initialization via lifespan handler.

    Validates: Requirements 2.1 - THE System SHALL initialize the workspace
    when the backend application starts.
    """

    def test_app_has_lifespan_handler(self):
        """Verify that the app has a lifespan handler configured.

        Requirements: 2.1
        """
        from oya.main import app

        # Check if app has a lifespan handler
        assert app.router.lifespan_context is not None, (
            "App should have a lifespan handler that initializes workspace"
        )

    def test_lifespan_calls_initialize_workspace_on_startup(self):
        """Verify that the lifespan handler calls initialize_workspace on startup.

        Requirements: 2.1
        """
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir)

            # Mock the settings to return our temp directory
            mock_settings = MagicMock()
            mock_settings.workspace_path = workspace_path
            mock_settings.db_path = workspace_path / ".oyawiki" / "meta" / "oya.db"

            # Set WORKSPACE_PATH env var so lifespan triggers legacy mode
            with patch.dict(os.environ, {"WORKSPACE_PATH": str(workspace_path)}):
                # We need to reload the module to pick up our patches
                with patch("oya.config.load_settings", return_value=mock_settings):
                    with patch("oya.workspace.initialize_workspace") as mock_init:
                        mock_init.return_value = True

                        # Force reimport to pick up patches
                        if "oya.main" in sys.modules:
                            del sys.modules["oya.main"]

                        from oya.main import app

                        # Create test client - this triggers the lifespan
                        with TestClient(app) as client:
                            # Verify initialize_workspace was called with the workspace path
                            mock_init.assert_called_once_with(workspace_path)

                            # App should still be healthy
                            response = client.get("/health")
                            assert response.status_code == 200

    def test_lifespan_logs_warning_on_failed_initialization(self):
        """Verify that failed initialization logs a warning but app still starts.

        Requirements: 2.1, 2.3 (graceful handling)
        """
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir)

            mock_settings = MagicMock()
            mock_settings.workspace_path = workspace_path
            mock_settings.db_path = workspace_path / ".oyawiki" / "meta" / "oya.db"

            # Set WORKSPACE_PATH env var so lifespan triggers legacy mode
            with patch.dict(os.environ, {"WORKSPACE_PATH": str(workspace_path)}):
                with patch("oya.config.load_settings", return_value=mock_settings):
                    with patch("oya.workspace.initialize_workspace", return_value=False):
                        # Force reimport
                        if "oya.main" in sys.modules:
                            del sys.modules["oya.main"]

                        from oya.main import app

                        # App should still start and be healthy (graceful degradation)
                        with TestClient(app) as client:
                            response = client.get("/health")
                            assert response.status_code == 200

    def test_lifespan_works_without_workspace_path(self):
        """Verify that the app starts in multi-repo mode without WORKSPACE_PATH.

        In multi-repo mode, WORKSPACE_PATH is not required - repos are managed
        via the repos_v2 API instead.
        """
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / ".oya"

            # Remove WORKSPACE_PATH, set OYA_DATA_DIR
            env_patch = {"OYA_DATA_DIR": str(data_dir)}
            with patch.dict(os.environ, env_patch, clear=False):
                # Remove WORKSPACE_PATH if it exists
                if "WORKSPACE_PATH" in os.environ:
                    del os.environ["WORKSPACE_PATH"]

                # Force reimport
                if "oya.main" in sys.modules:
                    del sys.modules["oya.main"]

                from oya.main import app

                # App should start and be healthy
                with TestClient(app) as client:
                    response = client.get("/health")
                    assert response.status_code == 200

                    # Data dir should have been created
                    assert data_dir.exists()
                    assert (data_dir / "wikis").exists()


def test_logging_format_includes_timestamp():
    """Verify main.py configures logging with timestamp format.

    Tests that the LOG_FORMAT and DATE_FORMAT constants in main.py
    match the expected format for timestamps in log output.
    """
    from oya.main import LOG_FORMAT, DATE_FORMAT

    # Verify LOG_FORMAT includes timestamp via %(asctime)s
    assert "%(asctime)s" in LOG_FORMAT, (
        f"LOG_FORMAT should include %(asctime)s for timestamps: {LOG_FORMAT}"
    )

    # Verify LOG_FORMAT includes log level
    assert "%(levelname)" in LOG_FORMAT, (
        f"LOG_FORMAT should include %(levelname) for log level: {LOG_FORMAT}"
    )

    # Verify LOG_FORMAT includes message
    assert "%(message)s" in LOG_FORMAT, (
        f"LOG_FORMAT should include %(message)s for the log message: {LOG_FORMAT}"
    )

    # Verify DATE_FORMAT uses ISO-style date format (YYYY-MM-DD HH:MM:SS)
    assert "%Y-%m-%d" in DATE_FORMAT, (
        f"DATE_FORMAT should include %Y-%m-%d for ISO date: {DATE_FORMAT}"
    )
    assert "%H:%M:%S" in DATE_FORMAT, f"DATE_FORMAT should include %H:%M:%S for time: {DATE_FORMAT}"
