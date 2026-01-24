"""Unit tests for startup initialization.

Tests that the FastAPI lifespan handler properly initializes the data directory
on application startup.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class TestStartupInitialization:
    """Tests for startup initialization via lifespan handler."""

    def test_app_has_lifespan_handler(self):
        """Verify that the app has a lifespan handler configured."""
        from oya.main import app

        # Check if app has a lifespan handler
        assert app.router.lifespan_context is not None, "App should have a lifespan handler"

    def test_lifespan_creates_data_directory(self):
        """Verify that the lifespan handler creates the data directory on startup."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / ".oya"

            # Set OYA_DATA_DIR
            with patch.dict(os.environ, {"OYA_DATA_DIR": str(data_dir)}, clear=False):
                # Force reimport to pick up new env
                if "oya.main" in sys.modules:
                    del sys.modules["oya.main"]

                from oya.main import app

                # Create test client - this triggers the lifespan
                with TestClient(app) as client:
                    # App should be healthy
                    response = client.get("/health")
                    assert response.status_code == 200

                    # Data dir should have been created
                    assert data_dir.exists()
                    assert (data_dir / "wikis").exists()

    def test_lifespan_checks_git_available(self):
        """Verify that the lifespan handler checks for git availability."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / ".oya"

            with patch.dict(os.environ, {"OYA_DATA_DIR": str(data_dir)}, clear=False):
                # Force reimport
                if "oya.main" in sys.modules:
                    del sys.modules["oya.main"]

                with patch("oya.main._check_git_available", return_value=True) as mock_git:
                    from oya.main import app

                    with TestClient(app) as client:
                        response = client.get("/health")
                        assert response.status_code == 200

                        # Git check should have been called
                        mock_git.assert_called_once()

    def test_app_starts_without_git(self):
        """Verify that app starts even if git is not available (graceful degradation)."""
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / ".oya"

            with patch.dict(os.environ, {"OYA_DATA_DIR": str(data_dir)}, clear=False):
                # Force reimport
                if "oya.main" in sys.modules:
                    del sys.modules["oya.main"]

                with patch("oya.main._check_git_available", return_value=False):
                    from oya.main import app

                    # App should still start and be healthy (graceful degradation)
                    with TestClient(app) as client:
                        response = client.get("/health")
                        assert response.status_code == 200

    def test_lifespan_uses_default_data_dir(self):
        """Verify that app uses default data directory when OYA_DATA_DIR not set."""
        import os

        # Remove OYA_DATA_DIR if set
        env_without_data_dir = {k: v for k, v in os.environ.items() if k != "OYA_DATA_DIR"}

        with patch.dict(os.environ, env_without_data_dir, clear=True):
            # Force reimport
            if "oya.main" in sys.modules:
                del sys.modules["oya.main"]

            # Mock _ensure_data_dir to avoid actually creating ~/.oya
            with patch("oya.main._ensure_data_dir") as mock_ensure:
                mock_ensure.return_value = Path.home() / ".oya"

                from oya.main import app

                with TestClient(app) as client:
                    response = client.get("/health")
                    assert response.status_code == 200

                    # _ensure_data_dir should have been called
                    mock_ensure.assert_called_once()


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
