"""Git clone and pull operations with friendly error handling."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class GitCloneError(Exception):
    """Error during git clone operation."""

    def __init__(self, message: str, original_error: Optional[str] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)


class GitPullError(Exception):
    """Error during git pull operation."""

    def __init__(self, message: str, original_error: Optional[str] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)


class GitSyncError(Exception):
    """Error during git sync operation."""

    def __init__(self, message: str, original_error: Optional[str] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)


def check_working_directory_clean(repo_path: Path) -> None:
    """
    Verify no uncommitted changes exist.

    Args:
        repo_path: Path to the git repository

    Raises:
        GitSyncError: If working directory has uncommitted changes or not a git repo
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise GitSyncError(
            f"Could not check repository status at `{repo_path}`. "
            "Ensure this is a valid git repository.",
            original_error=result.stderr,
        )

    if result.stdout.strip():
        raise GitSyncError(
            f"Repository has uncommitted changes at `{repo_path}`. "
            "Oya manages this repository automatically—please don't modify files directly. "
            "To reset, delete that folder and regenerate."
        )


def get_default_branch(repo_path: Path, timeout: int = 30) -> str:
    """
    Detect the repository's default branch.

    Queries remote first, falls back to local refs.

    Args:
        repo_path: Path to the git repository
        timeout: Timeout in seconds for remote query

    Returns:
        Name of the default branch (e.g., 'main' or 'master')

    Raises:
        GitSyncError: If default branch cannot be determined
    """
    # Try querying remote first (authoritative)
    try:
        result = subprocess.run(
            ["git", "remote", "show", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "HEAD branch:" in line:
                    return line.split(":")[-1].strip()
    except subprocess.TimeoutExpired:
        pass  # Fall through to local refs

    # Fallback: check local symbolic ref
    result = subprocess.run(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        # Output is like "refs/remotes/origin/main"
        return result.stdout.strip().split("/")[-1]

    raise GitSyncError(
        f"Could not determine the default branch for `{repo_path}`. "
        "Ensure the repository has an origin remote configured."
    )


def get_current_branch(repo_path: Path) -> str:
    """
    Get the name of the currently checked out branch.

    Args:
        repo_path: Path to the git repository

    Returns:
        Name of the current branch

    Raises:
        GitSyncError: If unable to determine current branch
    """
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise GitSyncError(
            f"Could not determine current branch in `{repo_path}`. "
            "Ensure this is a valid git repository.",
            original_error=result.stderr,
        )

    return result.stdout.strip()


def checkout_branch(repo_path: Path, branch: str) -> None:
    """
    Checkout a specific branch.

    Args:
        repo_path: Path to the git repository
        branch: Name of the branch to checkout

    Raises:
        GitSyncError: If checkout fails
    """
    result = subprocess.run(
        ["git", "checkout", branch],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise GitSyncError(
            f"Could not switch to branch '{branch}' in `{repo_path}`. "
            "The repository may be in an unexpected state.",
            original_error=result.stderr,
        )


def sync_to_default_branch(repo_path: Path, timeout: int = 120) -> str:
    """
    Sync repository to latest default branch.

    Checks for clean working directory, detects default branch,
    checks it out if needed, and pulls latest changes.

    Args:
        repo_path: Path to the git repository
        timeout: Timeout in seconds for network operations

    Returns:
        Name of the default branch

    Raises:
        GitSyncError: If any step fails, with user-friendly message
    """
    # Step 1: Ensure working directory is clean
    check_working_directory_clean(repo_path)

    # Step 2: Detect default branch
    default_branch = get_default_branch(repo_path, timeout=timeout)

    # Step 3: Checkout default branch if not already on it
    current = get_current_branch(repo_path)
    if current != default_branch:
        checkout_branch(repo_path, default_branch)

    # Step 4: Pull latest changes
    try:
        pull_repo(repo_path, timeout=timeout)
    except GitPullError as e:
        # Convert to GitSyncError with path included
        if "conflict" in e.message.lower():
            raise GitSyncError(
                f"Pull failed due to conflicts in `{repo_path}`. "
                "Oya manages this repository automatically—please don't modify files directly. "
                "Delete that folder and regenerate to fix this.",
                original_error=e.original_error,
            )
        raise GitSyncError(
            f"Could not pull latest changes for `{repo_path}`: {e.message}. "
            "Check your network connection and repository access.",
            original_error=e.original_error,
        )

    return default_branch


def clone_repo(url: str, dest: Path, timeout: int = 300) -> None:
    """
    Clone a git repository.

    Args:
        url: Git URL or local path to clone from
        dest: Destination directory (will be created)
        timeout: Timeout in seconds (default 5 minutes)

    Raises:
        GitCloneError: If clone fails, with user-friendly message
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ["git", "clone", url, str(dest)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise GitCloneError(
                _parse_clone_error(result.stderr),
                original_error=result.stderr,
            )

    except subprocess.TimeoutExpired:
        raise GitCloneError(
            "Clone operation timed out. The repository may be very large "
            "or your connection may be slow."
        )
    except FileNotFoundError:
        raise GitCloneError("Git is not installed. Please install git and try again.")


def pull_repo(repo_path: Path, timeout: int = 120) -> None:
    """
    Pull latest changes from origin.

    Args:
        repo_path: Path to the git repository
        timeout: Timeout in seconds (default 2 minutes)

    Raises:
        GitPullError: If pull fails, with user-friendly message
    """
    try:
        result = subprocess.run(
            ["git", "pull"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise GitPullError(
                _parse_pull_error(result.stderr),
                original_error=result.stderr,
            )

    except subprocess.TimeoutExpired:
        raise GitPullError("Pull operation timed out. Check your network connection.")
    except FileNotFoundError:
        raise GitPullError("Git is not installed. Please install git and try again.")


def get_remote_url(repo_path: Path) -> str:
    """
    Get the origin remote URL of a repository.

    Args:
        repo_path: Path to the git repository

    Returns:
        The origin remote URL

    Raises:
        ValueError: If no origin remote is configured
    """
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise ValueError(f"No origin remote configured: {result.stderr}")

    return result.stdout.strip()


def _parse_clone_error(stderr: str) -> str:
    """Convert git clone error to user-friendly message."""
    stderr_lower = stderr.lower()

    if "repository not found" in stderr_lower or "does not exist" in stderr_lower:
        return "Repository not found. Check the URL or ensure you have access."

    if "authentication" in stderr_lower or "permission denied" in stderr_lower:
        return (
            "Authentication failed. For private repos, ensure your SSH keys "
            "are configured or try an HTTPS URL with credentials."
        )

    if "could not resolve host" in stderr_lower or "network" in stderr_lower:
        return "Network error. Check your internet connection and try again."

    if "already exists" in stderr_lower:
        return "Destination directory already exists."

    return f"Clone failed: {stderr.strip()}"


def _parse_pull_error(stderr: str) -> str:
    """Convert git pull error to user-friendly message."""
    stderr_lower = stderr.lower()

    if "does not appear to be a git repository" in stderr_lower:
        return (
            "Original repository no longer exists at the configured location. "
            "You may need to delete this repo and re-add from the new location."
        )

    if "authentication" in stderr_lower or "permission denied" in stderr_lower:
        return "Authentication failed. Check your credentials and try again."

    if "could not resolve host" in stderr_lower or "network" in stderr_lower:
        return "Network error. Try again later."

    if "merge conflict" in stderr_lower:
        return "Merge conflict detected. This shouldn't happen - please report this bug."

    return f"Pull failed: {stderr.strip()}"
