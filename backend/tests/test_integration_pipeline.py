"""Integration tests for directory pages redesign."""


from oya.generation.prompts import generate_breadcrumb, format_subdirectory_summaries, format_file_links
from oya.generation.summaries import DirectorySummary, FileSummary
from oya.repo.file_filter import extract_directories_from_files


class TestDirectoryPagesRedesign:
    """Integration tests for directory pages redesign."""

    def test_breadcrumb_generation_integrates_with_template(self):
        """Breadcrumb helper works with expected directory structures."""
        # Test typical project structure
        breadcrumb = generate_breadcrumb("src/api/routes", "my-project")

        assert "[my-project](./root.md)" in breadcrumb
        assert "[src](./src.md)" in breadcrumb
        assert "[api](./src-api.md)" in breadcrumb
        assert "routes" in breadcrumb  # Current dir not linked

    def test_root_directory_included_in_extraction(self):
        """Root directory is always included when extracting directories."""
        files = ["src/main.py", "README.md"]

        directories = extract_directories_from_files(files)

        assert "" in directories  # Root directory
        assert "src" in directories

    def test_subdirectory_summaries_format_as_table(self):
        """Subdirectory summaries format correctly as markdown table."""
        summaries = [
            DirectorySummary(
                directory_path="src/api",
                purpose="API endpoints",
                contains=["routes.py"],
                role_in_system="HTTP layer",
            )
        ]

        result = format_subdirectory_summaries(summaries, "src")

        assert "| Directory | Purpose |" in result
        assert "[api](./src-api.md)" in result
        assert "API endpoints" in result

    def test_depth_first_processing_order(self):
        """Directories are processed deepest-first."""
        from oya.generation.orchestrator import get_processing_order

        directories = ["", "src", "src/api", "src/api/routes", "tests"]

        order = get_processing_order(directories)

        # Deepest first
        assert order.index("src/api/routes") < order.index("src/api")
        assert order.index("src/api") < order.index("src")
        # Root last
        assert order[-1] == ""

    def test_signature_includes_child_purposes(self):
        """Directory signature changes when child purpose changes."""
        from oya.generation.orchestrator import compute_directory_signature_with_children

        file_hashes = [("main.py", "abc123")]
        child1 = [DirectorySummary(
            directory_path="src/api",
            purpose="Original purpose",
            contains=[],
            role_in_system="",
        )]
        child2 = [DirectorySummary(
            directory_path="src/api",
            purpose="Changed purpose",
            contains=[],
            role_in_system="",
        )]

        sig1 = compute_directory_signature_with_children(file_hashes, child1)
        sig2 = compute_directory_signature_with_children(file_hashes, child2)

        assert sig1 != sig2


class TestRootDirectoryPage:
    """Tests for root directory page generation."""

    def test_root_directory_uses_root_slug(self):
        """Root directory page uses 'root' as its slug."""
        from oya.generation.summaries import path_to_slug

        # Root directory should map to "root" slug
        # This is handled specially in DirectoryGenerator
        # For non-root, path_to_slug works normally
        slug = path_to_slug("src/api", include_extension=False)
        assert slug == "src-api"

    def test_breadcrumb_for_root_shows_project_name(self):
        """Root directory breadcrumb shows just the project name."""
        breadcrumb = generate_breadcrumb("", "my-project")

        assert breadcrumb == "my-project"


class TestFileLinkFormatting:
    """Tests for file link formatting in directory pages."""

    def test_file_links_format_as_table(self):
        """File summaries format correctly as markdown table with links."""
        summaries = [
            FileSummary(
                file_path="src/main.py",
                purpose="Application entry point",
                layer="api",
                key_abstractions=["main"],
                internal_deps=[],
                external_deps=["fastapi"],
            )
        ]

        result = format_file_links(summaries)

        assert "| File | Purpose |" in result
        assert "[main.py](../files/src-main-py.md)" in result
        assert "Application entry point" in result

    def test_empty_file_list_message(self):
        """Empty file list returns appropriate message."""
        result = format_file_links([])

        assert result == "No files in this directory."


class TestSubdirectoryFiltering:
    """Tests for subdirectory filtering logic."""

    def test_only_direct_children_included(self):
        """Only direct child directories are included in the table."""
        summaries = [
            DirectorySummary(
                directory_path="src/api",
                purpose="API layer",
                contains=[],
                role_in_system="",
            ),
            DirectorySummary(
                directory_path="src/api/routes",
                purpose="Route handlers",
                contains=[],
                role_in_system="",
            ),
            DirectorySummary(
                directory_path="src/models",
                purpose="Data models",
                contains=[],
                role_in_system="",
            ),
        ]

        result = format_subdirectory_summaries(summaries, "src")

        # Direct children should be included
        assert "[api](./src-api.md)" in result
        assert "[models](./src-models.md)" in result
        # Nested child should NOT be included
        assert "routes" not in result

    def test_empty_subdirectory_list(self):
        """Empty subdirectory list returns appropriate message."""
        result = format_subdirectory_summaries([], "src")

        assert result == "No subdirectories."

    def test_root_directory_children(self):
        """Root directory correctly lists top-level directories."""
        summaries = [
            DirectorySummary(
                directory_path="src",
                purpose="Source code",
                contains=[],
                role_in_system="",
            ),
            DirectorySummary(
                directory_path="tests",
                purpose="Test suite",
                contains=[],
                role_in_system="",
            ),
            DirectorySummary(
                directory_path="src/api",
                purpose="API layer",
                contains=[],
                role_in_system="",
            ),
        ]

        result = format_subdirectory_summaries(summaries, "")

        # Top-level directories should be included
        assert "[src](./src.md)" in result
        assert "[tests](./tests.md)" in result
        # Nested should NOT be included
        assert "api" not in result


class TestBreadcrumbTruncation:
    """Tests for breadcrumb truncation on deep directory paths."""

    def test_shallow_path_shows_full_breadcrumb(self):
        """Paths with depth <= 4 show full breadcrumb."""
        breadcrumb = generate_breadcrumb("a/b/c/d", "project")

        # Should show all parts
        assert "[project](./root.md)" in breadcrumb
        assert "[a](./a.md)" in breadcrumb
        assert "[b](./a-b.md)" in breadcrumb
        assert "[c](./a-b-c.md)" in breadcrumb
        assert "d" in breadcrumb

    def test_deep_path_truncates_middle(self):
        """Paths with depth > 4 truncate middle with ellipsis."""
        breadcrumb = generate_breadcrumb("a/b/c/d/e", "project")

        # Should show: project / ... / d / e
        assert "[project](./root.md)" in breadcrumb
        assert "..." in breadcrumb
        assert "[d](./a-b-c-d.md)" in breadcrumb
        assert "e" in breadcrumb
        # Middle parts should NOT appear
        assert "[b]" not in breadcrumb
        assert "[c]" not in breadcrumb
