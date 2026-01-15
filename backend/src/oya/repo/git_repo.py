"""Git repository wrapper using GitPython."""

from pathlib import Path

from git import Repo


class GitRepo:
    """Wrapper for git repository operations."""

    def __init__(self, path: Path):
        """Initialize git repository wrapper.

        Args:
            path: Path to git repository root.
        """
        self.path = path
        self._repo = Repo(path)

    def get_head_commit(self) -> str:
        """Get current HEAD commit hash.

        Returns:
            Full commit SHA.
        """
        return self._repo.head.commit.hexsha

    def get_current_branch(self) -> str:
        """Get current branch name.

        Returns:
            Branch name or 'HEAD' if detached.
        """
        if self._repo.head.is_detached:
            return "HEAD"
        return self._repo.active_branch.name

    def is_dirty(self) -> bool:
        """Check if working directory has uncommitted changes.

        Returns:
            True if there are uncommitted changes.
        """
        return self._repo.is_dirty(untracked_files=True)

    def get_file_at_commit(self, file_path: str, commit_hash: str) -> str:
        """Get file content at specific commit.

        Args:
            file_path: Relative path to file.
            commit_hash: Commit SHA.

        Returns:
            File content as string.
        """
        commit = self._repo.commit(commit_hash)
        blob = commit.tree / file_path
        return str(blob.data_stream.read().decode("utf-8"))

    def list_files(self) -> list[str]:
        """List all tracked files in repository.

        Returns:
            List of relative file paths.
        """
        return [
            str(item.path)
            for item in self._repo.head.commit.tree.traverse()
            if not isinstance(item, tuple) and hasattr(item, "type") and item.type == "blob"
        ]

    def get_user_name(self) -> str:
        """Get configured git user name.

        Returns:
            User name or 'Unknown' if not configured.
        """
        try:
            return str(self._repo.config_reader().get_value("user", "name"))
        except Exception:
            return "Unknown"

    def get_user_email(self) -> str:
        """Get configured git user email.

        Returns:
            User email or empty string if not configured.
        """
        try:
            return str(self._repo.config_reader().get_value("user", "email"))
        except Exception:
            return ""
