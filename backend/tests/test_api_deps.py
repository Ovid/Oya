"""API dependency tests."""


from oya.api.deps import get_db, get_settings, get_repo


def test_get_settings_returns_settings(tmp_path, monkeypatch):
    """get_settings returns Settings instance."""
    # Setup workspace path
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    # Clear any cached settings
    from oya.config import load_settings
    load_settings.cache_clear()
    get_settings.cache_clear()

    settings = get_settings()
    assert hasattr(settings, "workspace_path")
    assert hasattr(settings, "active_provider")


def test_get_db_returns_database(tmp_path, monkeypatch):
    """get_db returns Database instance with migrations applied."""
    from oya.api.deps import _reset_db_instance
    from oya.db.connection import Database

    # Reset singleton for test isolation
    _reset_db_instance()

    # Configure workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    # Clear cached settings
    from oya.config import load_settings
    from oya.api.deps import get_settings
    load_settings.cache_clear()
    get_settings.cache_clear()

    db = get_db()
    assert isinstance(db, Database)

    # Verify migrations ran (schema_version table exists)
    result = db.execute("SELECT version FROM schema_version").fetchone()
    assert result is not None

    _reset_db_instance()


def test_get_repo_returns_repository(tmp_path, monkeypatch):
    """get_repo returns GitRepo wrapper for workspace."""
    import subprocess
    from oya.repo.git_repo import GitRepo

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(["git", "init"], cwd=workspace, capture_output=True)

    monkeypatch.setenv("WORKSPACE_PATH", str(workspace))

    from oya.config import load_settings
    from oya.api.deps import get_settings
    load_settings.cache_clear()
    get_settings.cache_clear()

    repo = get_repo()
    assert isinstance(repo, GitRepo)
