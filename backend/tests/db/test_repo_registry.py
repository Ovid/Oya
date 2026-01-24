"""Tests for the repository registry database."""

from oya.db.repo_registry import RepoRegistry


def test_create_repo_registry(tmp_path):
    """Registry can be created with a database path."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)
    assert db_path.exists()
    registry.close()


def test_add_repo(tmp_path):
    """Can add a repo to the registry."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    repo_id = registry.add(
        origin_url="https://github.com/Ovid/Oya",
        source_type="github",
        local_path="github.com/Ovid/Oya",
        display_name="Oya Wiki Generator",
    )

    assert repo_id == 1
    registry.close()


def test_get_repo_by_id(tmp_path):
    """Can retrieve a repo by ID."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    repo_id = registry.add(
        origin_url="https://github.com/Ovid/Oya",
        source_type="github",
        local_path="github.com/Ovid/Oya",
        display_name="Oya",
    )

    repo = registry.get(repo_id)
    assert repo is not None
    assert repo.origin_url == "https://github.com/Ovid/Oya"
    assert repo.display_name == "Oya"
    assert repo.status == "pending"
    registry.close()


def test_get_repo_not_found(tmp_path):
    """Returns None for non-existent repo."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    repo = registry.get(999)
    assert repo is None
    registry.close()


def test_list_repos(tmp_path):
    """Can list all repos."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    registry.add("https://github.com/a/b", "github", "github.com/a/b", "Repo A")
    registry.add("https://github.com/c/d", "github", "github.com/c/d", "Repo B")

    repos = registry.list_all()
    assert len(repos) == 2
    assert repos[0].display_name == "Repo A"
    assert repos[1].display_name == "Repo B"
    registry.close()


def test_update_repo(tmp_path):
    """Can update repo fields."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    repo_id = registry.add("https://github.com/a/b", "github", "github.com/a/b", "Repo")

    registry.update(repo_id, status="ready", head_commit="abc123")

    repo = registry.get(repo_id)
    assert repo.status == "ready"
    assert repo.head_commit == "abc123"
    registry.close()


def test_delete_repo(tmp_path):
    """Can delete a repo."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    repo_id = registry.add("https://github.com/a/b", "github", "github.com/a/b", "Repo")
    registry.delete(repo_id)

    repo = registry.get(repo_id)
    assert repo is None
    registry.close()


def test_find_by_origin_url(tmp_path):
    """Can find repo by origin URL."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)

    registry.add("https://github.com/a/b", "github", "github.com/a/b", "Repo")

    repo = registry.find_by_origin_url("https://github.com/a/b")
    assert repo is not None
    assert repo.display_name == "Repo"

    not_found = registry.find_by_origin_url("https://github.com/x/y")
    assert not_found is None
    registry.close()


# App settings tests


def test_get_setting_returns_none_for_missing_key(tmp_path):
    """get_setting returns None when key doesn't exist."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)
    try:
        result = registry.get_setting("nonexistent")
        assert result is None
    finally:
        registry.close()


def test_set_and_get_setting(tmp_path):
    """Can store and retrieve a setting."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)
    try:
        registry.set_setting("active_repo_id", "42")
        result = registry.get_setting("active_repo_id")
        assert result == "42"
    finally:
        registry.close()


def test_set_setting_overwrites_existing(tmp_path):
    """Setting a key twice overwrites the value."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)
    try:
        registry.set_setting("active_repo_id", "1")
        registry.set_setting("active_repo_id", "2")
        result = registry.get_setting("active_repo_id")
        assert result == "2"
    finally:
        registry.close()


def test_delete_setting(tmp_path):
    """Can delete a setting."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)
    try:
        registry.set_setting("active_repo_id", "42")
        registry.delete_setting("active_repo_id")
        result = registry.get_setting("active_repo_id")
        assert result is None
    finally:
        registry.close()


def test_delete_nonexistent_setting_is_noop(tmp_path):
    """Deleting a nonexistent setting doesn't raise."""
    db_path = tmp_path / "repos.db"
    registry = RepoRegistry(db_path)
    try:
        registry.delete_setting("nonexistent")  # Should not raise
    finally:
        registry.close()
