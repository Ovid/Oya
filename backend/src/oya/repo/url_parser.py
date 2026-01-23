"""Parse repository URLs and detect source type."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ParsedRepoUrl:
    """Result of parsing a repository URL."""

    source_type: str  # github, gitlab, bitbucket, git, local
    host: Optional[str]
    owner: Optional[str]
    repo: str
    local_path: str  # Path within wikis/ directory
    original_url: str


# Known hosts mapped to source types
KNOWN_HOSTS = {
    "github.com": "github",
    "gitlab.com": "gitlab",
    "bitbucket.org": "bitbucket",
}

# SSH URL pattern: git@host:owner/repo.git
SSH_PATTERN = re.compile(r"^git@([^:]+):([^/]+)/(.+?)(?:\.git)?$")

# HTTPS URL pattern for git repos
HTTPS_PATTERN = re.compile(r"^https?://([^/]+)/([^/]+)/(.+?)(?:\.git)?/?$")


def parse_repo_url(url: str) -> ParsedRepoUrl:
    """
    Parse a repository URL or local path.

    Supports:
    - GitHub/GitLab/Bitbucket HTTPS URLs
    - SSH URLs (git@host:owner/repo.git)
    - Local absolute paths (/path/to/repo)
    - Local paths with tilde (~/projects/repo)

    Returns ParsedRepoUrl with source_type and local_path for storage.
    Raises ValueError for invalid input.
    """
    url = url.strip()

    # Check for local path
    if url.startswith("/") or url.startswith("~"):
        return _parse_local_path(url)

    # Check for SSH URL
    ssh_match = SSH_PATTERN.match(url)
    if ssh_match:
        return _parse_ssh_url(url, ssh_match)

    # Check for HTTPS URL
    https_match = HTTPS_PATTERN.match(url)
    if https_match:
        return _parse_https_url(url, https_match)

    raise ValueError(f"Invalid repository URL or path: {url}")


def _parse_local_path(path: str) -> ParsedRepoUrl:
    """Parse a local filesystem path."""
    expanded = Path(path).expanduser().resolve()

    # Strip leading slash for local_path
    path_str = str(expanded).lstrip("/")

    return ParsedRepoUrl(
        source_type="local",
        host=None,
        owner=None,
        repo=expanded.name,
        local_path=f"local/{path_str}",
        original_url=path,
    )


def _parse_ssh_url(url: str, match: re.Match) -> ParsedRepoUrl:
    """Parse an SSH git URL."""
    host, owner, repo = match.groups()
    source_type = KNOWN_HOSTS.get(host, "git")

    if source_type == "git":
        local_path = f"git/{host}/{owner}/{repo}"
    else:
        local_path = f"{host}/{owner}/{repo}"

    return ParsedRepoUrl(
        source_type=source_type,
        host=host,
        owner=owner,
        repo=repo,
        local_path=local_path,
        original_url=url,
    )


def _parse_https_url(url: str, match: re.Match) -> ParsedRepoUrl:
    """Parse an HTTPS git URL."""
    host, owner, repo = match.groups()
    source_type = KNOWN_HOSTS.get(host, "git")

    if source_type == "git":
        local_path = f"git/{host}/{owner}/{repo}"
    else:
        local_path = f"{host}/{owner}/{repo}"

    return ParsedRepoUrl(
        source_type=source_type,
        host=host,
        owner=owner,
        repo=repo,
        local_path=local_path,
        original_url=url,
    )
