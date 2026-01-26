"""Tests for frontmatter utilities."""

from datetime import datetime, timezone


from oya.generation.frontmatter import build_frontmatter, parse_frontmatter


class TestBuildFrontmatter:
    """Tests for build_frontmatter function."""

    def test_build_file_frontmatter_with_layer(self):
        """Build frontmatter for a file page with layer included."""
        generated = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = build_frontmatter(
            source="src/utils/helpers.py",
            page_type="file",
            commit="abc123def456",
            generated=generated,
            layer="application",
        )

        assert result.startswith("---\n")
        assert result.endswith("---\n\n")
        assert "source: src/utils/helpers.py" in result
        assert "type: file" in result
        assert "commit: abc123def456" in result
        assert "generated: 2024-01-15T10:30:00+00:00" in result
        assert "layer: application" in result

    def test_build_directory_frontmatter_without_layer(self):
        """Build frontmatter for a directory page without layer."""
        generated = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = build_frontmatter(
            source="src/utils/",
            page_type="directory",
            commit="abc123def456",
            generated=generated,
        )

        assert result.startswith("---\n")
        assert result.endswith("---\n\n")
        assert "source: src/utils/" in result
        assert "type: directory" in result
        assert "commit: abc123def456" in result
        assert "generated: 2024-01-15T10:30:00+00:00" in result
        assert "layer:" not in result

    def test_build_overview_frontmatter_without_source(self):
        """Build frontmatter for overview page without source."""
        generated = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = build_frontmatter(
            source=None,
            page_type="overview",
            commit="abc123def456",
            generated=generated,
        )

        assert result.startswith("---\n")
        assert result.endswith("---\n\n")
        assert "source:" not in result
        assert "type: overview" in result
        assert "commit: abc123def456" in result
        assert "generated: 2024-01-15T10:30:00+00:00" in result


class TestParseFrontmatter:
    """Tests for parse_frontmatter function."""

    def test_parse_valid_frontmatter(self):
        """Parse content with valid frontmatter."""
        content = """---
source: src/utils/helpers.py
type: file
commit: abc123def456
generated: 2024-01-15T10:30:00+00:00
layer: application
---

# File Documentation

This is the content.
"""
        metadata, remaining = parse_frontmatter(content)

        assert metadata is not None
        assert metadata["source"] == "src/utils/helpers.py"
        assert metadata["type"] == "file"
        assert metadata["commit"] == "abc123def456"
        # YAML parses ISO timestamps into datetime objects
        assert metadata["generated"] == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        assert metadata["layer"] == "application"
        assert remaining == "# File Documentation\n\nThis is the content.\n"

    def test_parse_content_without_frontmatter(self):
        """Return None metadata for content without frontmatter."""
        content = """# Just a Heading

Some content without frontmatter.
"""
        metadata, remaining = parse_frontmatter(content)

        assert metadata is None
        assert remaining == content

    def test_parse_frontmatter_without_source_field(self):
        """Parse frontmatter that has no source field."""
        content = """---
type: overview
commit: abc123def456
generated: 2024-01-15T10:30:00+00:00
---

# Overview

Overview content.
"""
        metadata, remaining = parse_frontmatter(content)

        assert metadata is not None
        assert "source" not in metadata
        assert metadata["type"] == "overview"
        assert metadata["commit"] == "abc123def456"
        assert remaining == "# Overview\n\nOverview content.\n"

    def test_parse_invalid_yaml_returns_none(self):
        """Return None for invalid YAML in frontmatter."""
        content = """---
invalid: [unclosed bracket
type: file
---

Content
"""
        metadata, remaining = parse_frontmatter(content)

        assert metadata is None
        assert remaining == content

    def test_parse_unclosed_frontmatter_returns_none(self):
        """Return None for frontmatter without closing delimiter."""
        content = """---
source: test.py
type: file

Content without closing delimiter
"""
        metadata, remaining = parse_frontmatter(content)

        assert metadata is None
        assert remaining == content

    def test_parse_frontmatter_without_blank_line_after(self):
        """Parse frontmatter that has no blank line after closing delimiter."""
        content = """---
type: file
commit: abc123
generated: 2024-01-15T10:30:00+00:00
---
# Heading immediately after
"""
        metadata, remaining = parse_frontmatter(content)

        assert metadata is not None
        assert metadata["type"] == "file"
        assert remaining == "# Heading immediately after\n"
