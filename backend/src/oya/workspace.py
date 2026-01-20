"""Workspace initialization module.

This module handles initialization of the .oyawiki directory structure
that contains all Oya-generated artifacts.
"""

import logging
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

# Required subdirectories within .oyawiki/
# These directories store different types of artifacts:
# - wiki: Generated wiki content (committable)
# - notes: Human corrections (committable)
# - meta: Generation metadata (committable)
# - index: Search indexes (ephemeral)
# - cache: Temporary data (ephemeral)
# - config: Settings files
OYAWIKI_SUBDIRS: Final[list[str]] = ["wiki", "notes", "meta", "index", "cache", "config"]


def initialize_workspace(workspace_path: Path) -> bool:
    """Initialize the .oyawiki directory structure.

    Creates the following structure if it doesn't exist:
    .oyawiki/
    ├── wiki/      - Generated wiki content
    ├── notes/     - Human corrections
    ├── meta/      - Generation metadata
    ├── index/     - Search indexes
    ├── cache/     - Temporary data
    └── config/    - Settings

    Args:
        workspace_path: Root path of the workspace/repository.

    Returns:
        True if initialization succeeded, False otherwise.
    """
    # Get wiki directory name from settings, fallback to default
    wiki_dir = ".oyawiki"  # Default
    try:
        from oya.config import load_settings
        settings = load_settings()
        wiki_dir = settings.paths.wiki_dir
    except (ValueError, OSError):
        # Settings not available, use default
        pass

    # Always compute path relative to workspace_path parameter
    oyawiki_path = workspace_path / wiki_dir

    try:
        for subdir in OYAWIKI_SUBDIRS:
            (oyawiki_path / subdir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized workspace at {workspace_path}")
        return True
    except OSError as e:
        logger.error(f"Failed to initialize workspace at {workspace_path}: {e}")
        return False
