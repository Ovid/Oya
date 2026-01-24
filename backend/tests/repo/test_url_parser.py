"""Tests for URL parsing and source type detection."""

import pytest
from oya.repo.url_parser import parse_repo_url


class TestParseRepoUrl:
    """Tests for URL parsing and source type detection."""

    def test_github_https_url(self):
        result = parse_repo_url("https://github.com/Ovid/Oya")
        assert result.source_type == "github"
        assert result.host == "github.com"
        assert result.owner == "Ovid"
        assert result.repo == "Oya"
        assert result.local_path == "github.com/Ovid/Oya"

    def test_github_https_url_with_git_suffix(self):
        result = parse_repo_url("https://github.com/Ovid/Oya.git")
        assert result.source_type == "github"
        assert result.repo == "Oya"
        assert result.local_path == "github.com/Ovid/Oya"

    def test_github_ssh_url(self):
        result = parse_repo_url("git@github.com:Ovid/Oya.git")
        assert result.source_type == "github"
        assert result.owner == "Ovid"
        assert result.repo == "Oya"
        assert result.local_path == "github.com/Ovid/Oya"

    def test_gitlab_url(self):
        result = parse_repo_url("https://gitlab.com/someorg/project")
        assert result.source_type == "gitlab"
        assert result.local_path == "gitlab.com/someorg/project"

    def test_bitbucket_url(self):
        result = parse_repo_url("https://bitbucket.org/team/repo")
        assert result.source_type == "bitbucket"
        assert result.local_path == "bitbucket.org/team/repo"

    def test_enterprise_github_url(self):
        result = parse_repo_url("https://github.mycompany.com/org/repo")
        assert result.source_type == "git"
        assert result.local_path == "git/github.mycompany.com/org/repo"

    def test_local_absolute_path(self):
        result = parse_repo_url("/Users/alice/projects/myrepo")
        assert result.source_type == "local"
        assert result.local_path == "local/Users/alice/projects/myrepo"

    def test_local_home_path(self):
        result = parse_repo_url("~/projects/myrepo")
        assert result.source_type == "local"
        assert result.local_path.startswith("local/")
        assert "projects/myrepo" in result.local_path

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Invalid"):
            parse_repo_url("not-a-url-or-path")
