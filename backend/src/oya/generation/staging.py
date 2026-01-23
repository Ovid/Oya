"""Staging directory management for wiki generation.

Wiki generation builds in .oyawiki-building and only promotes to .oyawiki
on successful completion. This ensures that:
1. Interrupted builds don't corrupt the existing wiki
2. Failed builds are preserved for debugging
3. The wiki is always in a consistent state
"""

import shutil
from pathlib import Path

from oya.config import ConfigError, load_settings


def prepare_staging_directory(staging_path: Path, production_path: Path) -> None:
    """Prepare the staging directory for a new build.

    If a production directory exists (from a successful previous build),
    copies it to staging for incremental regeneration. Otherwise creates
    an empty staging directory.

    Always removes any existing staging directory first to avoid corruption
    from a previous incomplete build.

    Args:
        staging_path: Path to the staging directory (.oyawiki-building).
        production_path: Path to the production directory (.oyawiki).
    """
    # Always wipe staging first to avoid corruption from incomplete builds
    if staging_path.exists():
        shutil.rmtree(staging_path)

    # Copy production to staging for incremental regeneration, or create empty
    if production_path.exists():
        shutil.copytree(production_path, staging_path)
    else:
        staging_path.mkdir(parents=True, exist_ok=True)


def promote_staging_to_production(staging_path: Path, production_path: Path) -> None:
    """Promote staging directory to production.

    Replaces the production directory with the staging directory contents.
    This is an atomic-ish operation that ensures the wiki is always consistent.

    Args:
        staging_path: Path to the staging directory (.oyawiki-building).
        production_path: Path to the production directory (.oyawiki).
    """
    # Remove existing production if it exists
    if production_path.exists():
        shutil.rmtree(production_path)

    # Move staging to production
    shutil.move(str(staging_path), str(production_path))


def has_incomplete_build(workspace_path: Path) -> bool:
    """Check if there's an incomplete build in the staging directory.

    Args:
        workspace_path: Path to the workspace root.

    Returns:
        True if .oyawiki-building exists, indicating an incomplete build.
    """
    # Get staging directory name from settings, fallback to default
    staging_dir = ".oyawiki-building"  # Default
    try:
        settings = load_settings()
        staging_dir = settings.paths.staging_dir
    except (ValueError, OSError, ConfigError):
        # Settings not available, use default
        pass

    # Always compute path relative to workspace_path parameter
    staging_path = workspace_path / staging_dir
    return staging_path.exists()
