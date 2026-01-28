# backend/tests/test_prompts.py
"""Prompt template tests."""

import pytest

from oya.generation.prompts import (
    PromptTemplate,
    get_overview_prompt,
    get_architecture_prompt,
    get_file_prompt,
)


def test_prompt_template_renders_variables():
    """PromptTemplate substitutes variables correctly."""
    template = PromptTemplate("Hello {name}, welcome to {project}!")
    result = template.render(name="Alice", project="Oya")

    assert result == "Hello Alice, welcome to Oya!"


def test_prompt_template_handles_missing_variable():
    """PromptTemplate raises error for missing variables."""
    template = PromptTemplate("Hello {name}!")

    with pytest.raises(KeyError):
        template.render()


def test_get_overview_prompt_includes_context():
    """Overview prompt includes readme and structure."""
    prompt = get_overview_prompt(
        repo_name="my-project",
        readme_content="# My Project\nA cool project.",
        file_tree="src/\n  main.py\ntests/",
        package_info={"name": "my-project", "version": "1.0.0"},
    )

    assert "my-project" in prompt
    assert "A cool project" in prompt
    assert "src/" in prompt


def test_get_architecture_prompt_includes_symbols():
    """Architecture prompt includes parsed symbols."""
    prompt = get_architecture_prompt(
        repo_name="my-project",
        file_tree="src/\n  main.py",
        key_symbols=[
            {"file": "src/main.py", "name": "main", "type": "function"},
            {"file": "src/api.py", "name": "Router", "type": "class"},
        ],
        dependencies=["fastapi", "sqlalchemy"],
    )

    assert "my-project" in prompt
    assert "main" in prompt
    assert "Router" in prompt
    assert "fastapi" in prompt


def test_get_file_prompt_includes_content():
    """File prompt includes file content and context."""
    prompt = get_file_prompt(
        file_path="src/auth/login.py",
        content="def login(user): pass",
        symbols=[{"name": "login", "type": "function", "line": 1}],
        imports=["from flask import request"],
        architecture_summary="Authentication system handles user login.",
    )

    assert "src/auth/login.py" in prompt
    assert "def login" in prompt
    assert "Authentication system" in prompt


def test_file_template_includes_developer_audience():
    """File template must specify developer audience."""
    from oya.generation.prompts import FILE_TEMPLATE

    template_text = FILE_TEMPLATE.template.lower()

    # Must mention developers as the audience
    assert "developer" in template_text
    assert "maintain" in template_text or "debug" in template_text or "extend" in template_text

    # Must NOT skip documentation for internal files
    assert (
        "must" in template_text and "always" in template_text and "documentation" in template_text
    )


def test_file_template_rejects_skip_documentation():
    """File template must explicitly prohibit skipping documentation."""
    from oya.generation.prompts import FILE_TEMPLATE

    template_text = FILE_TEMPLATE.template.lower()

    # Must address internal/trivial files explicitly
    assert "internal" in template_text or "trivial" in template_text
    assert "never skip" in template_text or "must always" in template_text


class TestBreadcrumbGeneration:
    """Tests for breadcrumb generation helper."""

    def test_generate_breadcrumb_shallow_directory(self):
        """Shallow directories show full path."""
        from oya.generation.prompts import generate_breadcrumb

        result = generate_breadcrumb("src/api/routes", "my-project")

        assert "[my-project](./root)" in result
        assert "[src](./src)" in result
        assert "[api](./src-api)" in result
        assert "routes" in result
        assert "..." not in result

    def test_generate_breadcrumb_deep_directory_truncates(self):
        """Deep directories (>4 levels) truncate middle."""
        from oya.generation.prompts import generate_breadcrumb

        result = generate_breadcrumb("src/components/ui/forms/inputs/validation", "my-project")

        assert "[my-project](./root)" in result
        assert "..." in result
        assert "[inputs](./src-components-ui-forms-inputs)" in result
        assert "validation" in result
        # Middle segments should be truncated
        assert "[ui]" not in result
        assert "[forms]" not in result

    def test_generate_breadcrumb_root_directory(self):
        """Root directory shows only project name."""
        from oya.generation.prompts import generate_breadcrumb

        result = generate_breadcrumb("", "my-project")

        assert result == "my-project"

    def test_generate_breadcrumb_single_level(self):
        """Single level directory shows root and current."""
        from oya.generation.prompts import generate_breadcrumb

        result = generate_breadcrumb("src", "my-project")

        assert "[my-project](./root)" in result
        assert "src" in result
        assert "..." not in result


class TestSubdirectorySummariesFormatter:
    """Tests for subdirectory summaries formatter."""

    def test_format_subdirectory_summaries_with_data(self):
        """Formats subdirectories as markdown table with links."""
        from oya.generation.prompts import format_subdirectory_summaries
        from oya.generation.summaries import DirectorySummary

        summaries = [
            DirectorySummary(
                directory_path="src/api/routes",
                purpose="HTTP route handlers for all endpoints",
                contains=["user.py", "auth.py"],
                role_in_system="API layer",
            ),
            DirectorySummary(
                directory_path="src/api/middleware",
                purpose="Request/response middleware",
                contains=["cors.py"],
                role_in_system="Cross-cutting concerns",
            ),
        ]

        result = format_subdirectory_summaries(summaries, "src/api")

        assert "| Directory | Purpose |" in result
        assert "[routes](./src-api-routes)" in result
        assert "HTTP route handlers" in result
        assert "[middleware](./src-api-middleware)" in result
        assert "Request/response middleware" in result

    def test_format_subdirectory_summaries_empty(self):
        """Returns message when no subdirectories."""
        from oya.generation.prompts import format_subdirectory_summaries

        result = format_subdirectory_summaries([], "src/api")

        assert "No subdirectories" in result

    def test_format_subdirectory_summaries_filters_to_direct_children(self):
        """Only includes direct child directories, not nested ones."""
        from oya.generation.prompts import format_subdirectory_summaries
        from oya.generation.summaries import DirectorySummary

        summaries = [
            DirectorySummary(
                directory_path="src/api/routes",
                purpose="Routes",
                contains=[],
                role_in_system="",
            ),
            DirectorySummary(
                directory_path="src/api/routes/v1",  # Nested - should be excluded
                purpose="V1 routes",
                contains=[],
                role_in_system="",
            ),
        ]

        result = format_subdirectory_summaries(summaries, "src/api")

        assert "routes" in result
        assert "v1" not in result.lower() or "[v1]" not in result


class TestFileLinksFormatter:
    """Tests for file links formatter."""

    def test_format_file_links_with_summaries(self):
        """Formats files as markdown table with links."""
        from oya.generation.prompts import format_file_links
        from oya.generation.summaries import FileSummary

        summaries = [
            FileSummary(
                file_path="src/api/app.py",
                purpose="FastAPI application setup",
                layer="api",
                key_abstractions=["create_app"],
                internal_deps=[],
                external_deps=["fastapi"],
            ),
            FileSummary(
                file_path="src/api/__init__.py",
                purpose="Package initialization",
                layer="config",
                key_abstractions=[],
                internal_deps=[],
                external_deps=[],
            ),
        ]

        result = format_file_links(summaries)

        assert "| File | Purpose |" in result
        assert "[app.py](../files/src-api-app-py)" in result
        assert "FastAPI application setup" in result
        # Canonical path_to_slug strips underscores: __init__.py -> init-py
        assert "[__init__.py](../files/src-api-init-py)" in result

    def test_format_file_links_empty(self):
        """Returns message when no files."""
        from oya.generation.prompts import format_file_links

        result = format_file_links([])

        assert "No files" in result


class TestSynthesisTemplate:
    """Tests for synthesis prompt template."""

    def test_synthesis_template_requests_layer_interactions(self):
        """Test that synthesis template asks for layer_interactions field."""
        from oya.generation.prompts import SYNTHESIS_TEMPLATE

        template_str = SYNTHESIS_TEMPLATE.template

        assert "layer_interactions" in template_str
        assert "how" in template_str.lower() and "layer" in template_str.lower()

    def test_synthesis_template_json_schema_includes_layer_interactions(self):
        """Test that JSON schema in synthesis template includes layer_interactions."""
        from oya.generation.prompts import SYNTHESIS_TEMPLATE

        template_str = SYNTHESIS_TEMPLATE.template

        # Should have layer_interactions in the JSON example
        assert '"layer_interactions"' in template_str


class TestFormatHelpers:
    """Tests for prompt formatting helper functions."""

    def test_format_entry_points(self):
        """Test formatting entry points for prompt."""
        from oya.generation.prompts import _format_entry_points
        from oya.generation.summaries import EntryPointInfo

        entry_points = [
            EntryPointInfo(name="main", entry_type="main_function", file="main.py", description=""),
            EntryPointInfo(
                name="get_users", entry_type="api_route", file="api/users.py", description="/users"
            ),
            EntryPointInfo(
                name="init", entry_type="cli_command", file="cli/main.py", description="init"
            ),
        ]

        result = _format_entry_points(entry_points)

        assert "main" in result
        assert "main_function" in result
        assert "main.py" in result
        assert "/users" in result
        assert "cli_command" in result

    def test_format_entry_points_empty(self):
        """Test formatting empty entry points list."""
        from oya.generation.prompts import _format_entry_points

        result = _format_entry_points([])

        assert "No entry points" in result or result == ""

    def test_format_tech_stack(self):
        """Test formatting tech stack for prompt."""
        from oya.generation.prompts import _format_tech_stack

        tech_stack = {
            "python": {
                "web_framework": ["FastAPI"],
                "database": ["SQLAlchemy"],
            },
            "javascript": {
                "frontend": ["React"],
            },
        }

        result = _format_tech_stack(tech_stack)

        assert "Python" in result or "python" in result
        assert "FastAPI" in result
        assert "SQLAlchemy" in result
        assert "React" in result

    def test_format_tech_stack_empty(self):
        """Test formatting empty tech stack."""
        from oya.generation.prompts import _format_tech_stack

        result = _format_tech_stack({})

        assert "no technology" in result.lower() or result == ""

    def test_format_metrics(self):
        """Test formatting code metrics for prompt."""
        from oya.generation.prompts import _format_metrics
        from oya.generation.summaries import CodeMetrics

        metrics = CodeMetrics(
            total_files=50,
            files_by_layer={"api": 10, "domain": 20, "test": 20},
            lines_by_layer={"api": 1000, "domain": 3000, "test": 2000},
            total_lines=6000,
        )

        result = _format_metrics(metrics)

        assert "50" in result  # total files
        assert "6000" in result or "6,000" in result  # total lines
        assert "api" in result.lower()
        assert "domain" in result.lower()

    def test_format_metrics_none(self):
        """Test formatting None metrics."""
        from oya.generation.prompts import _format_metrics

        result = _format_metrics(None)

        assert "No metrics" in result or result == ""


class TestOverviewSynthesisTemplate:
    """Tests for overview synthesis prompt template."""

    def test_template_includes_new_fields(self):
        """Test that template includes placeholders for new fields."""
        from oya.generation.prompts import OVERVIEW_SYNTHESIS_TEMPLATE

        template_str = OVERVIEW_SYNTHESIS_TEMPLATE.template

        assert "{entry_points}" in template_str
        assert "{tech_stack}" in template_str
        assert "{metrics}" in template_str
        assert "{layer_interactions}" in template_str
        assert "{architecture_diagram}" in template_str

    def test_template_deprioritizes_readme(self):
        """Test that template indicates README may be outdated."""
        from oya.generation.prompts import OVERVIEW_SYNTHESIS_TEMPLATE

        template_str = OVERVIEW_SYNTHESIS_TEMPLATE.template.lower()

        assert "outdated" in template_str or "supplementary" in template_str

    def test_template_has_structured_output(self):
        """Test that template specifies structured output format."""
        from oya.generation.prompts import OVERVIEW_SYNTHESIS_TEMPLATE

        template_str = OVERVIEW_SYNTHESIS_TEMPLATE.template

        # Should have main sections
        assert "## Overview" in template_str or "# {repo_name}" in template_str
        assert "Technology Stack" in template_str
        assert "Getting Started" in template_str
        assert "Architecture" in template_str


class TestGetOverviewPrompt:
    """Tests for get_overview_prompt function."""

    def test_includes_entry_points_in_prompt(self):
        """Test that entry points are included in generated prompt."""
        from oya.generation.prompts import get_overview_prompt
        from oya.generation.summaries import (
            SynthesisMap,
            EntryPointInfo,
            CodeMetrics,
            LayerInfo,
        )

        synthesis_map = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="HTTP", directories=[], files=[])},
            project_summary="Test project",
            entry_points=[
                EntryPointInfo(
                    name="main", entry_type="main_function", file="main.py", description=""
                )
            ],
            tech_stack={"python": {"web_framework": ["FastAPI"]}},
            metrics=CodeMetrics(
                total_files=10,
                files_by_layer={"api": 10},
                lines_by_layer={"api": 500},
                total_lines=500,
            ),
            layer_interactions="API calls domain directly.",
        )

        result = get_overview_prompt(
            repo_name="test-repo",
            readme_content="Test README",
            file_tree="test/\n  main.py",
            package_info={},
            synthesis_map=synthesis_map,
            architecture_diagram="```mermaid\ngraph TD\n```",
        )

        assert "main" in result
        assert "main_function" in result
        assert "FastAPI" in result
        assert "500" in result
        assert "API calls domain" in result
        assert "mermaid" in result

    def test_works_without_architecture_diagram(self):
        """Test that function works when no diagram is provided."""
        from oya.generation.prompts import get_overview_prompt
        from oya.generation.summaries import SynthesisMap

        synthesis_map = SynthesisMap(project_summary="Test")

        result = get_overview_prompt(
            repo_name="test-repo",
            readme_content="Test",
            file_tree="test/",
            package_info={},
            synthesis_map=synthesis_map,
        )

        assert "test-repo" in result


class TestFileTemplateIssues:
    """Tests for FILE_TEMPLATE issue detection instructions."""

    def test_file_template_includes_issues_instructions(self):
        """FILE_TEMPLATE includes issue detection instructions."""
        from oya.generation.prompts import FILE_TEMPLATE

        template = FILE_TEMPLATE.template

        # Check for issue detection section
        assert "Code Analysis" in template or "issues" in template.lower()
        assert "security" in template.lower()
        assert "reliability" in template.lower()
        assert "maintainability" in template.lower()

    def test_file_template_yaml_schema_includes_issues(self):
        """FILE_TEMPLATE YAML schema includes issues field."""
        from oya.generation.prompts import FILE_TEMPLATE

        template = FILE_TEMPLATE.template

        # YAML schema should show issues structure
        assert "issues:" in template
        assert "category:" in template
        assert "severity:" in template
        assert "title:" in template
        assert "description:" in template

    def test_get_file_prompt_renders_correctly(self):
        """get_file_prompt renders without errors."""
        from oya.generation.prompts import get_file_prompt

        prompt = get_file_prompt(
            file_path="test.py",
            content="def hello(): pass",
            symbols=[{"name": "hello", "type": "function", "line": 1}],
            imports=["import os"],
            architecture_summary="Utility module",
            language="python",
        )

        assert "test.py" in prompt
        assert "def hello()" in prompt
        assert "issues:" in prompt


def test_get_graph_architecture_prompt_includes_component_diagram():
    """get_graph_architecture_prompt includes the component diagram."""
    from oya.generation.prompts import get_graph_architecture_prompt

    prompt = get_graph_architecture_prompt(
        repo_name="my-project",
        component_diagram="flowchart LR\n    api --> db",
        entry_points=[
            {"id": "api/main.py::handle", "name": "handle", "file": "api/main.py", "fanout": 3},
        ],
        flow_diagrams=[
            {"entry_point": "handle", "diagram": "flowchart TD\n    handle --> query"},
        ],
        component_summaries={"api": "HTTP endpoints", "db": "Database access"},
    )

    assert "flowchart LR" in prompt
    assert "api --> db" in prompt
    assert "handle" in prompt
    assert "HTTP endpoints" in prompt


def test_get_graph_architecture_prompt_handles_empty_flows():
    """get_graph_architecture_prompt handles case with no flow diagrams."""
    from oya.generation.prompts import get_graph_architecture_prompt

    prompt = get_graph_architecture_prompt(
        repo_name="my-project",
        component_diagram="flowchart LR\n    api --> db",
        entry_points=[],
        flow_diagrams=[],
        component_summaries={},
    )

    assert "flowchart LR" in prompt
    assert "my-project" in prompt


def test_file_template_includes_synopsis_section():
    """FILE_TEMPLATE should mention Synopsis as section 2."""
    from oya.generation.prompts import FILE_TEMPLATE

    template_text = FILE_TEMPLATE.template

    # Should mention Synopsis section
    assert "Synopsis" in template_text or "synopsis" in template_text

    # Should mention it comes after Purpose (section 1)
    assert "1." in template_text and "Purpose" in template_text
    assert "2." in template_text and ("Synopsis" in template_text or "synopsis" in template_text)


def test_file_template_mentions_ai_generated_marker():
    """FILE_TEMPLATE should instruct LLM to mark AI-generated synopses."""
    from oya.generation.prompts import (
        FILE_TEMPLATE,
        SYNOPSIS_INSTRUCTIONS_WITHOUT_EXTRACTED,
    )

    template_text = FILE_TEMPLATE.template
    # The AI-Generated marker should appear in the synopsis instructions
    assert (
        "AI-Generated" in template_text
        or "ai-generated" in template_text.lower()
        or "AI-Generated" in SYNOPSIS_INSTRUCTIONS_WITHOUT_EXTRACTED
    )
