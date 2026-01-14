# backend/tests/test_prompts.py
"""Prompt template tests."""

import pytest

from oya.generation.prompts import (
    PromptTemplate,
    get_overview_prompt,
    get_architecture_prompt,
    get_workflow_prompt,
    get_directory_prompt,
    get_file_prompt,
)


def test_prompt_template_renders_variables():
    """PromptTemplate substitutes variables correctly."""
    template = PromptTemplate(
        "Hello {name}, welcome to {project}!"
    )
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
    assert "must" in template_text and "always" in template_text and "documentation" in template_text


def test_file_template_rejects_skip_documentation():
    """File template must explicitly prohibit skipping documentation."""
    from oya.generation.prompts import FILE_TEMPLATE

    template_text = FILE_TEMPLATE.template.lower()

    # Must address internal/trivial files explicitly
    assert "internal" in template_text or "trivial" in template_text
    assert "never skip" in template_text or "must always" in template_text
