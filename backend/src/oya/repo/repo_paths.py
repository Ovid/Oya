"""Path utilities for multi-repo directory structure."""

from __future__ import annotations

import shutil
from pathlib import Path


class RepoPaths:
    """
    Computes paths for a repository's directory structure.

    Structure:
        {data_dir}/wikis/{local_path}/
            source/      # Git clone (untouched)
            meta/        # Oya artifacts
                .oyawiki/
                    wiki/
                    notes/
                    meta/
                        oya.db
                        chroma/
                        index/
                        cache/
                    config/
                .oyaignore
                .oya-logs/
    """

    def __init__(self, data_dir: Path, local_path: str) -> None:
        """
        Initialize repo paths.

        Args:
            data_dir: The OYA_DATA_DIR (e.g., ~/.oya)
            local_path: Path within wikis/ (e.g., "github.com/Ovid/Oya")
        """
        self.data_dir = data_dir
        self.local_path = local_path

        # Root of this repo's storage
        self.root = data_dir / "wikis" / local_path

        # Top-level directories
        self.source = self.root / "source"
        self.meta = self.root / "meta"

        # Artifacts in meta/
        self.oyawiki = self.meta / ".oyawiki"
        self.oyaignore = self.meta / ".oyaignore"
        self.oya_logs = self.meta / ".oya-logs"

        # .oyawiki subdirectories (mirrors current structure)
        self.wiki_dir = self.oyawiki / "wiki"
        self.notes_dir = self.oyawiki / "notes"
        self.meta_dir = self.oyawiki / "meta"
        self.config_dir = self.oyawiki / "config"

        # Database and search paths
        self.db_path = self.meta_dir / "oya.db"
        self.chroma_dir = self.meta_dir / "chroma"
        self.index_dir = self.meta_dir / "index"
        self.cache_dir = self.meta_dir / "cache"

    def create_structure(self) -> None:
        """Create the meta directory structure (source/ is created by git clone)."""
        self.meta.mkdir(parents=True, exist_ok=True)
        self.wiki_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.oya_logs.mkdir(parents=True, exist_ok=True)

    def delete_all(self) -> None:
        """Delete the entire repo directory (source + meta)."""
        if self.root.exists():
            shutil.rmtree(self.root)

    def exists(self) -> bool:
        """Check if the repo directory exists."""
        return self.root.exists()

    def has_source(self) -> bool:
        """Check if the source directory has been cloned."""
        return self.source.exists() and (self.source / ".git").exists()

    def has_wiki(self) -> bool:
        """Check if a wiki has been generated."""
        return self.wiki_dir.exists() and any(self.wiki_dir.iterdir())
