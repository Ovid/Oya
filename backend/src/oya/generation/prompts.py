# backend/src/oya/generation/prompts.py
"""Prompt templates for wiki generation."""

from dataclasses import dataclass
from typing import Any


@dataclass
class PromptTemplate:
    """A template for generating prompts with variable substitution."""

    template: str

    def render(self, **kwargs: Any) -> str:
        """Render the template with the given variables.

        Args:
            **kwargs: Variables to substitute into the template.

        Returns:
            The rendered template string.

        Raises:
            KeyError: If a required variable is missing.
        """
        return self.template.format(**kwargs)


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are a technical documentation expert. Your task is to generate
clear, accurate, and helpful documentation for codebases. Follow these guidelines:

1. Be precise and factual - only document what exists in the code
2. Use clear, concise language appropriate for developers
3. Include relevant code examples when helpful
4. Organize information logically with proper headings
5. Highlight important patterns, dependencies, and relationships
6. Note any potential issues, TODOs, or areas for improvement

Output your documentation in clean Markdown format."""


# =============================================================================
# Overview Template
# =============================================================================

OVERVIEW_TEMPLATE = PromptTemplate(
    """Generate a comprehensive overview page for the repository "{repo_name}".

## README Content
{readme_content}

## Project Structure
```
{file_tree}
```

## Package Information
{package_info}

---

Create a documentation overview that includes:
1. **Project Summary**: A brief description of what this project does
2. **Key Features**: Main capabilities and features
3. **Getting Started**: How to install and run the project
4. **Project Structure**: Overview of the directory organization
5. **Technology Stack**: Languages, frameworks, and key dependencies

Format the output as clean Markdown suitable for a wiki page."""
)


# =============================================================================
# Architecture Template
# =============================================================================

ARCHITECTURE_TEMPLATE = PromptTemplate(
    """Generate an architecture documentation page for "{repo_name}".

## Project Structure
```
{file_tree}
```

## Key Symbols
{key_symbols}

## Dependencies
{dependencies}

---

Create architecture documentation that includes:
1. **System Overview**: High-level description of the system architecture
2. **Component Diagram**: Describe the main components and their relationships
3. **Key Classes and Functions**: Document the most important code elements
4. **Data Flow**: How data moves through the system
5. **Design Patterns**: Notable patterns used in the codebase
6. **External Dependencies**: Key libraries and their purposes

Format the output as clean Markdown suitable for a wiki page."""
)


# =============================================================================
# Workflow Template
# =============================================================================

WORKFLOW_TEMPLATE = PromptTemplate(
    """Generate a workflow documentation page for the "{workflow_name}" workflow in "{repo_name}".

## Entry Points
{entry_points}

## Related Files
{related_files}

## Code Context
{code_context}

---

Create workflow documentation that includes:
1. **Workflow Overview**: What this workflow accomplishes
2. **Trigger/Entry Point**: How the workflow is initiated
3. **Step-by-Step Flow**: Detailed walkthrough of the process
4. **Key Functions**: Important functions involved
5. **Error Handling**: How errors are handled
6. **Related Workflows**: Connections to other workflows

Format the output as clean Markdown suitable for a wiki page."""
)


# =============================================================================
# Directory Template
# =============================================================================

DIRECTORY_TEMPLATE = PromptTemplate(
    """Generate a directory documentation page for "{directory_path}" in "{repo_name}".

## Files in Directory
{file_list}

## Symbols Defined
{symbols}

## Architecture Context
{architecture_context}

---

Create directory documentation that includes:
1. **Directory Purpose**: What this directory contains and why
2. **File Overview**: Brief description of each file
3. **Key Components**: Important classes, functions, or modules
4. **Dependencies**: What this directory depends on and what depends on it
5. **Usage Examples**: How to use the components in this directory

Format the output as clean Markdown suitable for a wiki page."""
)


# =============================================================================
# File Template
# =============================================================================

FILE_TEMPLATE = PromptTemplate(
    """Generate documentation for the file "{file_path}".

## File Content
```{language}
{content}
```

## Symbols
{symbols}

## Imports
{imports}

## Architecture Context
{architecture_summary}

---

Create file documentation that includes:
1. **File Purpose**: What this file does and its role in the project
2. **Classes**: Document each class with its purpose and methods
3. **Functions**: Document each function with parameters and return values
4. **Constants/Variables**: Document important module-level definitions
5. **Dependencies**: What this file imports and why
6. **Usage Examples**: How to use the components defined in this file

Format the output as clean Markdown suitable for a wiki page."""
)


# =============================================================================
# Helper Functions
# =============================================================================


def _format_symbols(symbols: list[dict[str, Any]]) -> str:
    """Format a list of symbols for inclusion in a prompt.

    Args:
        symbols: List of symbol dictionaries with name, type, and optionally file/line.

    Returns:
        Formatted string representation of symbols.
    """
    if not symbols:
        return "No symbols defined."

    lines = []
    for sym in symbols:
        name = sym.get("name", "unknown")
        sym_type = sym.get("type", "unknown")
        file_path = sym.get("file", "")
        line = sym.get("line", "")

        if file_path:
            lines.append(f"- {name} ({sym_type}) in {file_path}")
        elif line:
            lines.append(f"- {name} ({sym_type}) at line {line}")
        else:
            lines.append(f"- {name} ({sym_type})")

    return "\n".join(lines)


def _format_dependencies(dependencies: list[str]) -> str:
    """Format a list of dependencies for inclusion in a prompt.

    Args:
        dependencies: List of dependency names.

    Returns:
        Formatted string representation of dependencies.
    """
    if not dependencies:
        return "No external dependencies."

    return "\n".join(f"- {dep}" for dep in dependencies)


def _format_imports(imports: list[str]) -> str:
    """Format a list of imports for inclusion in a prompt.

    Args:
        imports: List of import statements.

    Returns:
        Formatted string representation of imports.
    """
    if not imports:
        return "No imports."

    return "\n".join(imports)


def _format_package_info(package_info: dict[str, Any]) -> str:
    """Format package information for inclusion in a prompt.

    Args:
        package_info: Dictionary of package metadata.

    Returns:
        Formatted string representation of package info.
    """
    if not package_info:
        return "No package information available."

    lines = []
    for key, value in package_info.items():
        lines.append(f"- {key}: {value}")

    return "\n".join(lines)


def get_overview_prompt(
    repo_name: str,
    readme_content: str,
    file_tree: str,
    package_info: dict[str, Any],
) -> str:
    """Generate a prompt for creating an overview page.

    Args:
        repo_name: Name of the repository.
        readme_content: Content of the README file.
        file_tree: String representation of the file tree.
        package_info: Dictionary of package metadata.

    Returns:
        The rendered prompt string.
    """
    return OVERVIEW_TEMPLATE.render(
        repo_name=repo_name,
        readme_content=readme_content or "No README found.",
        file_tree=file_tree,
        package_info=_format_package_info(package_info),
    )


def get_architecture_prompt(
    repo_name: str,
    file_tree: str,
    key_symbols: list[dict[str, Any]],
    dependencies: list[str],
) -> str:
    """Generate a prompt for creating an architecture page.

    Args:
        repo_name: Name of the repository.
        file_tree: String representation of the file tree.
        key_symbols: List of key symbol dictionaries.
        dependencies: List of dependency names.

    Returns:
        The rendered prompt string.
    """
    return ARCHITECTURE_TEMPLATE.render(
        repo_name=repo_name,
        file_tree=file_tree,
        key_symbols=_format_symbols(key_symbols),
        dependencies=_format_dependencies(dependencies),
    )


def get_workflow_prompt(
    repo_name: str,
    workflow_name: str,
    entry_points: list[str],
    related_files: list[str],
    code_context: str,
) -> str:
    """Generate a prompt for creating a workflow page.

    Args:
        repo_name: Name of the repository.
        workflow_name: Name of the workflow being documented.
        entry_points: List of entry point descriptions.
        related_files: List of related file paths.
        code_context: Relevant code snippets or context.

    Returns:
        The rendered prompt string.
    """
    entry_points_str = "\n".join(f"- {ep}" for ep in entry_points) if entry_points else "No entry points defined."
    related_files_str = "\n".join(f"- {f}" for f in related_files) if related_files else "No related files."

    return WORKFLOW_TEMPLATE.render(
        repo_name=repo_name,
        workflow_name=workflow_name,
        entry_points=entry_points_str,
        related_files=related_files_str,
        code_context=code_context or "No code context provided.",
    )


def get_directory_prompt(
    repo_name: str,
    directory_path: str,
    file_list: list[str],
    symbols: list[dict[str, Any]],
    architecture_context: str,
) -> str:
    """Generate a prompt for creating a directory page.

    Args:
        repo_name: Name of the repository.
        directory_path: Path to the directory.
        file_list: List of files in the directory.
        symbols: List of symbol dictionaries defined in the directory.
        architecture_context: Summary of how this directory fits in the architecture.

    Returns:
        The rendered prompt string.
    """
    file_list_str = "\n".join(f"- {f}" for f in file_list) if file_list else "No files in directory."

    return DIRECTORY_TEMPLATE.render(
        repo_name=repo_name,
        directory_path=directory_path,
        file_list=file_list_str,
        symbols=_format_symbols(symbols),
        architecture_context=architecture_context or "No architecture context provided.",
    )


def get_file_prompt(
    file_path: str,
    content: str,
    symbols: list[dict[str, Any]],
    imports: list[str],
    architecture_summary: str,
    language: str = "",
) -> str:
    """Generate a prompt for creating a file documentation page.

    Args:
        file_path: Path to the file.
        content: Content of the file.
        symbols: List of symbol dictionaries defined in the file.
        imports: List of import statements.
        architecture_summary: Summary of how this file fits in the architecture.
        language: Programming language for syntax highlighting.

    Returns:
        The rendered prompt string.
    """
    return FILE_TEMPLATE.render(
        file_path=file_path,
        content=content,
        symbols=_format_symbols(symbols),
        imports=_format_imports(imports),
        architecture_summary=architecture_summary or "No architecture context provided.",
        language=language,
    )
