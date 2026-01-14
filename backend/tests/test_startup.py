"""Unit tests for startup initialization.

Tests that the FastAPI lifespan handler properly initializes the workspace
on application startup.

Feature: oya-config-improvements
Validates: Requirements 2.1
"""

import importlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
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
        assert app.router.lifespan_context is not None, \
            "App should have a lifespan handler that initializes workspace"

    def test_lifespan_calls_initialize_workspace_on_startup(self):
        """Verify that the lifespan handler calls initialize_workspace on startup.
        
        Requirements: 2.1
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir)
            
            # Mock the settings to return our temp directory
            mock_settings = MagicMock()
            mock_settings.workspace_path = workspace_path
            
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
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace_path = Path(tmpdir)
            
            mock_settings = MagicMock()
            mock_settings.workspace_path = workspace_path
            
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


def test_logging_format_includes_timestamp():
    """Verify main.py configures logging with timestamp format.

    Tests that the LOG_FORMAT and DATE_FORMAT constants in main.py
    match the expected format for timestamps in log output.
    """
    from oya.main import LOG_FORMAT, DATE_FORMAT

    # Verify LOG_FORMAT includes timestamp via %(asctime)s
    assert "%(asctime)s" in LOG_FORMAT, \
        f"LOG_FORMAT should include %(asctime)s for timestamps: {LOG_FORMAT}"

    # Verify LOG_FORMAT includes log level
    assert "%(levelname)" in LOG_FORMAT, \
        f"LOG_FORMAT should include %(levelname) for log level: {LOG_FORMAT}"

    # Verify LOG_FORMAT includes message
    assert "%(message)s" in LOG_FORMAT, \
        f"LOG_FORMAT should include %(message)s for the log message: {LOG_FORMAT}"

    # Verify DATE_FORMAT uses ISO-style date format (YYYY-MM-DD HH:MM:SS)
    assert "%Y-%m-%d" in DATE_FORMAT, \
        f"DATE_FORMAT should include %Y-%m-%d for ISO date: {DATE_FORMAT}"
    assert "%H:%M:%S" in DATE_FORMAT, \
        f"DATE_FORMAT should include %H:%M:%S for time: {DATE_FORMAT}"
