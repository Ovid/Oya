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
