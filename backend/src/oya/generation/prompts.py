# backend/src/oya/generation/prompts.py
"""Prompt templates for wiki generation."""

from dataclasses import dataclass
from typing import Any

from oya.generation.summaries import path_to_slug


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

IMPORTANT: If human correction notes are provided, they represent ground truth from
the developer. You MUST integrate these corrections naturally into your documentation.
Human notes override any inference you might make from the code.

Output your documentation in clean Markdown format."""


# =============================================================================
# Synthesis Template
# =============================================================================

SYNTHESIS_TEMPLATE = PromptTemplate(
    """Synthesize the following file and directory summaries into a coherent understanding of the codebase.

## File Summaries
{file_summaries}

## Directory Summaries
{directory_summaries}

---

Analyze the summaries above and produce a JSON response with the following structure:

```json
{{
  "key_components": [
    {{
      "name": "ComponentName",
      "file": "path/to/file.py",
      "role": "Description of what this component does and why it's important",
      "layer": "api|domain|infrastructure|utility|config|test"
    }}
  ],
  "dependency_graph": {{
    "layer_name": ["dependent_layer1", "dependent_layer2"]
  }},
  "project_summary": "A comprehensive 2-3 sentence summary of what this project does, its main purpose, and key technologies used."
}}
```

Guidelines:
1. **key_components**: Identify the 5-15 most important classes, functions, or modules that form the backbone of the system. Focus on:
   - Entry points and main orchestrators
   - Core domain models and services
   - Key infrastructure components
   - Important utilities used throughout

2. **dependency_graph**: Map which layers depend on which other layers. For example, "api" typically depends on "domain", and "domain" may depend on "infrastructure".

3. **project_summary**: Write a clear, informative summary that would help a new developer understand what this codebase does at a glance.

Respond with valid JSON only, no additional text."""
)


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


OVERVIEW_SYNTHESIS_TEMPLATE = PromptTemplate(
    """Generate a comprehensive overview page for the repository "{repo_name}".

## Project Summary (from code analysis)
{project_summary}

## System Layers
{layers}

## Key Components
{key_components}

## README Content (supplementary)
{readme_content}

## Project Structure
```
{file_tree}
```

## Package Information
{package_info}

---

Create a documentation overview that includes:
1. **Project Summary**: Use the project summary from code analysis as the primary source. If README content is available, incorporate any additional context it provides.
2. **Key Features**: Main capabilities and features based on the key components and layer structure
3. **Getting Started**: How to install and run the project (use README if available, otherwise infer from package info)
4. **Project Structure**: Overview of the directory organization based on the system layers
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
2. **Component Relationships**: Describe the main components and how they interact. Focus on the relationships and data flow between layers. (Diagrams will be generated automatically from code analysis.)
3. **Key Classes and Functions**: Document the most important code elements
4. **Data Flow**: How data moves through the system
5. **Design Patterns**: Notable patterns used in the codebase
6. **External Dependencies**: Key libraries and their purposes

Format the output as clean Markdown suitable for a wiki page."""
)


ARCHITECTURE_SYNTHESIS_TEMPLATE = PromptTemplate(
    """Generate an architecture documentation page for "{repo_name}".

## Project Structure
```
{file_tree}
```

## System Layers
{layers}

## Key Components
{key_components}

## Layer Dependencies
{dependency_graph}

## Project Summary
{project_summary}

## External Dependencies
{dependencies}

---

Create architecture documentation that includes:
1. **System Overview**: High-level description of the system architecture based on the project summary and layer structure
2. **Layer Architecture**: Describe each layer's purpose and responsibilities
3. **Component Relationships**: Describe the main components and how they interact. Focus on the relationships and data flow between layers. (Diagrams will be generated automatically from code analysis.)
4. **Key Components**: Document the most important classes and functions identified above
5. **Data Flow**: How data moves through the layers
6. **Design Patterns**: Notable patterns used in the codebase
7. **External Dependencies**: Key libraries and their purposes

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


WORKFLOW_SYNTHESIS_TEMPLATE = PromptTemplate(
    """Generate a workflow documentation page for the "{workflow_name}" workflow in "{repo_name}".

## Entry Points
{entry_points}

## Related Files
{related_files}

## System Layers
{layers}

## Key Components
{key_components}

## Layer Dependencies
{dependency_graph}

## Code Context
{code_context}

---

Create workflow documentation that includes:
1. **Workflow Overview**: What this workflow accomplishes and its role in the system
2. **Trigger/Entry Point**: How the workflow is initiated
3. **Step-by-Step Flow**: Walkthrough showing how data moves through layers
4. **Key Components Involved**: Which key components participate and their roles
5. **Error Handling**: How errors are handled at each layer
6. **Related Workflows**: Connections to other workflows

Format the output as clean Markdown suitable for a wiki page."""
)


# =============================================================================
# Directory Template
# =============================================================================

DIRECTORY_TEMPLATE = PromptTemplate(
    """Generate a directory documentation page for "{directory_path}" in "{repo_name}".

## Breadcrumb
{breadcrumb}

## Direct Files
{file_list}

## File Summaries
{file_summaries}

## Subdirectories
{subdirectory_summaries}

## Symbols Defined
{symbols}

---

IMPORTANT: You MUST start your response with a YAML summary block in the following format:

```
---
directory_summary:
  purpose: "One-sentence description of what this directory/module is responsible for"
  contains:
    - "file1.py"
    - "file2.py"
  role_in_system: "Description of how this directory fits into the overall architecture"
---
```

After the YAML block, create directory documentation with these sections IN ORDER:

1. **Overview**: One paragraph describing the directory's purpose (do NOT include a heading, start directly with the paragraph)

2. **Subdirectories** (if any exist): Use this exact table format:
| Directory | Purpose |
|-----------|---------|
| [name](./slug.md) | One-line description |

3. **Files**: Use this exact table format:
| File | Purpose |
|------|---------|
| [name.py](../files/slug.md) | One-line description |

4. **Key Components**: Bullet list of important classes/functions

5. **Dependencies**:
   - **Internal**: Other directories/modules this depends on
   - **External**: Third-party libraries used

Use the breadcrumb, file summaries, and subdirectory summaries provided to generate accurate content.
Do NOT invent files or subdirectories that aren't listed above.
Format all file and directory names as markdown links using the link formats shown in the tables."""
)


# =============================================================================
# File Template
# =============================================================================

FILE_TEMPLATE = PromptTemplate(
    """Generate documentation for the file "{file_path}".

AUDIENCE: You are writing for developers who will maintain, debug, and extend this code - NOT for end users of an API. Even files marked as "internal" or "no user-serviceable parts" need thorough documentation for the development team.

REQUIREMENT: You MUST always produce documentation. Every file has value to developers - explain what it does, why it exists, and how it works. Never skip documentation because a file seems "internal" or "trivial".

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

IMPORTANT: You MUST start your response with a YAML summary block in the following format:

```
---
file_summary:
  purpose: "One-sentence description of what this file does"
  layer: <one of: api, domain, infrastructure, utility, config, test>
  key_abstractions:
    - "ClassName or function_name"
  internal_deps:
    - "path/to/other/file.py"
  external_deps:
    - "library_name"
---
```

Layer classification guide:
- api: REST endpoints, request handlers, API routes
- domain: Core business logic, services, use cases
- infrastructure: Database, external services, I/O operations
- utility: Helper functions, shared utilities, common tools
- config: Configuration, settings, environment handling
- test: Test files, test utilities, fixtures

Your documentation MUST include these sections in order:
1. **Purpose** - What this file does and why it exists
2. **Public API** - Exported classes, functions, constants (if any)
3. **Internal Details** - Implementation specifics developers need to know
4. **Dependencies** - What this file imports and why
5. **Usage Examples** - How to use the components in this file

You MAY add additional sections after these if there's important information that doesn't fit (e.g., "Concurrency Notes", "Migration History", "Known Limitations").

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


def _format_synthesis_layers(synthesis_map: Any) -> str:
    """Format layer information from a SynthesisMap for inclusion in a prompt.

    Args:
        synthesis_map: A SynthesisMap object containing layer information.

    Returns:
        Formatted string representation of layers.
    """
    if not synthesis_map or not synthesis_map.layers:
        return "No layer information available."

    lines = []
    for layer_name, layer_info in synthesis_map.layers.items():
        lines.append(f"### {layer_name.upper()} Layer")
        lines.append(f"**Purpose**: {layer_info.purpose}")
        if layer_info.directories:
            dirs = ", ".join(layer_info.directories[:5])
            if len(layer_info.directories) > 5:
                dirs += f" (and {len(layer_info.directories) - 5} more)"
            lines.append(f"**Directories**: {dirs}")
        if layer_info.files:
            files = ", ".join(layer_info.files[:10])
            if len(layer_info.files) > 10:
                files += f" (and {len(layer_info.files) - 10} more)"
            lines.append(f"**Files**: {files}")
        lines.append("")

    return "\n".join(lines)


def _format_synthesis_key_components(synthesis_map: Any) -> str:
    """Format key components from a SynthesisMap for inclusion in a prompt.

    Args:
        synthesis_map: A SynthesisMap object containing key components.

    Returns:
        Formatted string representation of key components.
    """
    if not synthesis_map or not synthesis_map.key_components:
        return "No key components identified."

    lines = []
    for comp in synthesis_map.key_components:
        lines.append(f"### {comp.name}")
        lines.append(f"- **File**: {comp.file}")
        lines.append(f"- **Role**: {comp.role}")
        lines.append(f"- **Layer**: {comp.layer}")
        lines.append("")

    return "\n".join(lines)


def _format_synthesis_dependency_graph(synthesis_map: Any) -> str:
    """Format dependency graph from a SynthesisMap for inclusion in a prompt.

    Args:
        synthesis_map: A SynthesisMap object containing dependency graph.

    Returns:
        Formatted string representation of dependency graph.
    """
    if not synthesis_map or not synthesis_map.dependency_graph:
        return "No dependency graph available."

    lines = []
    for source, targets in synthesis_map.dependency_graph.items():
        if targets:
            deps = ", ".join(targets)
            lines.append(f"- **{source}** depends on: {deps}")
        else:
            lines.append(f"- **{source}**: no dependencies")

    return "\n".join(lines)


def _format_file_summaries(file_summaries: list[Any]) -> str:
    """Format a list of FileSummaries for inclusion in a prompt.

    Args:
        file_summaries: List of FileSummary objects.

    Returns:
        Formatted string representation of file summaries.
    """
    if not file_summaries:
        return "No file summaries available."

    lines = []
    for summary in file_summaries:
        lines.append(f"### {summary.file_path}")
        lines.append(f"- **Purpose**: {summary.purpose}")
        lines.append(f"- **Layer**: {summary.layer}")
        if summary.key_abstractions:
            abstractions = ", ".join(summary.key_abstractions)
            lines.append(f"- **Key Abstractions**: {abstractions}")
        if summary.internal_deps:
            deps = ", ".join(summary.internal_deps)
            lines.append(f"- **Internal Dependencies**: {deps}")
        if summary.external_deps:
            ext_deps = ", ".join(summary.external_deps)
            lines.append(f"- **External Dependencies**: {ext_deps}")
        lines.append("")

    return "\n".join(lines)


def _format_directory_summaries(directory_summaries: list[Any]) -> str:
    """Format a list of DirectorySummaries for inclusion in a prompt.

    Args:
        directory_summaries: List of DirectorySummary objects.

    Returns:
        Formatted string representation of directory summaries.
    """
    if not directory_summaries:
        return "No directory summaries available."

    lines = []
    for summary in directory_summaries:
        lines.append(f"### {summary.directory_path}")
        lines.append(f"- **Purpose**: {summary.purpose}")
        if summary.contains:
            files = ", ".join(summary.contains[:10])  # Limit to first 10
            if len(summary.contains) > 10:
                files += f" (and {len(summary.contains) - 10} more)"
            lines.append(f"- **Contains**: {files}")
        if summary.role_in_system:
            lines.append(f"- **Role in System**: {summary.role_in_system}")
        lines.append("")

    return "\n".join(lines)


def format_subdirectory_summaries(
    summaries: list[Any],
    parent_directory: str
) -> str:
    """Format subdirectory summaries as a markdown table with links.

    Only includes direct child directories of the parent.

    Args:
        summaries: List of DirectorySummary objects.
        parent_directory: Path of the parent directory.

    Returns:
        Markdown table string with directory links and purposes.
    """
    if not summaries:
        return "No subdirectories."

    # Filter to direct children only
    prefix = f"{parent_directory}/" if parent_directory else ""
    direct_children = []
    for summary in summaries:
        path = summary.directory_path
        # Must start with parent path
        if not path.startswith(prefix):
            continue
        # Remaining path after prefix should have no slashes (direct child)
        remaining = path[len(prefix):]
        if "/" not in remaining and remaining:
            direct_children.append(summary)

    if not direct_children:
        return "No subdirectories."

    lines = ["| Directory | Purpose |", "|-----------|---------|"]
    for summary in sorted(direct_children, key=lambda s: s.directory_path):
        name = summary.directory_path.split("/")[-1]
        slug = path_to_slug(summary.directory_path, include_extension=False)
        link = f"[{name}](./{slug}.md)"
        purpose = summary.purpose or "No description"
        lines.append(f"| {link} | {purpose} |")

    return "\n".join(lines)


def format_file_links(file_summaries: list[Any]) -> str:
    """Format file summaries as a markdown table with links.

    Args:
        file_summaries: List of FileSummary objects.

    Returns:
        Markdown table string with file links and purposes.
    """
    if not file_summaries:
        return "No files in this directory."

    lines = ["| File | Purpose |", "|------|---------|"]
    for summary in sorted(file_summaries, key=lambda s: s.file_path):
        filename = summary.file_path.split("/")[-1]
        slug = path_to_slug(summary.file_path)
        link = f"[{filename}](../files/{slug}.md)"
        purpose = summary.purpose or "No description"
        lines.append(f"| {link} | {purpose} |")

    return "\n".join(lines)


def generate_breadcrumb(directory_path: str, project_name: str) -> str:
    """Generate a breadcrumb trail for directory navigation.

    For shallow directories (depth <= 4), shows full path.
    For deep directories (depth > 4), truncates middle: root / ... / parent / current.

    Args:
        directory_path: Path to the directory (empty string for root).
        project_name: Name of the project for the root link.

    Returns:
        Markdown string with clickable breadcrumb links.
    """
    # Root directory - just show project name
    if not directory_path:
        return project_name

    parts = directory_path.split("/")
    depth = len(parts)

    # Root link
    root_link = f"[{project_name}](./root.md)"

    if depth <= 4:
        # Show full path
        links = [root_link]
        for i in range(len(parts) - 1):
            ancestor_path = "/".join(parts[: i + 1])
            slug = path_to_slug(ancestor_path, include_extension=False)
            links.append(f"[{parts[i]}](./{slug}.md)")
        links.append(parts[-1])  # Current directory (no link)
        return " / ".join(links)
    else:
        # Truncate middle: root / ... / parent / current
        parent_path = "/".join(parts[:-1])
        parent_slug = path_to_slug(parent_path, include_extension=False)
        parent_link = f"[{parts[-2]}](./{parent_slug}.md)"
        return f"{root_link} / ... / {parent_link} / {parts[-1]}"


def get_overview_prompt(
    repo_name: str,
    readme_content: str,
    file_tree: str,
    package_info: dict[str, Any],
    synthesis_map: Any = None,
) -> str:
    """Generate a prompt for creating an overview page.

    Supports two modes:
    1. Legacy mode: Uses README as primary context
    2. Synthesis mode: Uses SynthesisMap as primary context with README as supplementary

    Args:
        repo_name: Name of the repository.
        readme_content: Content of the README file.
        file_tree: String representation of the file tree.
        package_info: Dictionary of package metadata.
        synthesis_map: SynthesisMap object with layer and component info (preferred).

    Returns:
        The rendered prompt string.
    """
    # Use synthesis-based template if synthesis_map is provided
    if synthesis_map is not None:
        return OVERVIEW_SYNTHESIS_TEMPLATE.render(
            repo_name=repo_name,
            project_summary=synthesis_map.project_summary or "No project summary available.",
            layers=_format_synthesis_layers(synthesis_map),
            key_components=_format_synthesis_key_components(synthesis_map),
            readme_content=readme_content or "No README found.",
            file_tree=file_tree,
            package_info=_format_package_info(package_info),
        )

    # Fall back to legacy template without synthesis_map
    return OVERVIEW_TEMPLATE.render(
        repo_name=repo_name,
        readme_content=readme_content or "No README found.",
        file_tree=file_tree,
        package_info=_format_package_info(package_info),
    )


def get_architecture_prompt(
    repo_name: str,
    file_tree: str,
    key_symbols: list[dict[str, Any]] | None = None,
    dependencies: list[str] | None = None,
    synthesis_map: Any = None,
) -> str:
    """Generate a prompt for creating an architecture page.

    Supports two modes:
    1. Legacy mode: Uses key_symbols for architecture context
    2. Synthesis mode: Uses SynthesisMap for richer architecture context

    Args:
        repo_name: Name of the repository.
        file_tree: String representation of the file tree.
        key_symbols: List of key symbol dictionaries (legacy mode).
        dependencies: List of dependency names.
        synthesis_map: SynthesisMap object with layer and component info (preferred).

    Returns:
        The rendered prompt string.
    """
    deps = dependencies or []

    # Use synthesis-based template if synthesis_map is provided
    if synthesis_map is not None:
        return ARCHITECTURE_SYNTHESIS_TEMPLATE.render(
            repo_name=repo_name,
            file_tree=file_tree,
            layers=_format_synthesis_layers(synthesis_map),
            key_components=_format_synthesis_key_components(synthesis_map),
            dependency_graph=_format_synthesis_dependency_graph(synthesis_map),
            project_summary=synthesis_map.project_summary or "No project summary available.",
            dependencies=_format_dependencies(deps),
        )

    # Fall back to legacy template with key_symbols
    return ARCHITECTURE_TEMPLATE.render(
        repo_name=repo_name,
        file_tree=file_tree,
        key_symbols=_format_symbols(key_symbols or []),
        dependencies=_format_dependencies(deps),
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
    entry_points_str = (
        "\n".join(f"- {ep}" for ep in entry_points) if entry_points else "No entry points defined."
    )
    related_files_str = (
        "\n".join(f"- {f}" for f in related_files) if related_files else "No related files."
    )

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
    file_summaries: list[Any] | None = None,
    subdirectory_summaries: list[Any] | None = None,
    project_name: str | None = None,
) -> str:
    """Generate a prompt for creating a directory page.

    Args:
        repo_name: Name of the repository.
        directory_path: Path to the directory (empty string for root).
        file_list: List of files in the directory.
        symbols: List of symbol dictionaries defined in the directory.
        architecture_context: Summary of how this directory fits in the architecture.
        file_summaries: Optional list of FileSummary objects for files in the directory.
        subdirectory_summaries: Optional list of DirectorySummary objects for child directories.
        project_name: Project name for breadcrumb (defaults to repo_name).

    Returns:
        The rendered prompt string.
    """
    file_list_str = (
        "\n".join(f"- {f}" for f in file_list) if file_list else "No files in directory."
    )

    proj_name = project_name or repo_name
    breadcrumb = generate_breadcrumb(directory_path, proj_name)

    # Format display path - use project name for root
    display_path = directory_path if directory_path else proj_name

    return DIRECTORY_TEMPLATE.render(
        repo_name=repo_name,
        directory_path=display_path,
        breadcrumb=breadcrumb,
        file_list=file_list_str,
        file_summaries=format_file_links(file_summaries or []),
        subdirectory_summaries=format_subdirectory_summaries(
            subdirectory_summaries or [], directory_path
        ),
        symbols=_format_symbols(symbols),
    )


def get_file_prompt(
    file_path: str,
    content: str,
    symbols: list[dict[str, Any]],
    imports: list[str],
    architecture_summary: str,
    language: str = "",
    notes: list[dict[str, Any]] | None = None,
) -> str:
    """Generate a prompt for creating a file documentation page.

    Args:
        file_path: Path to the file.
        content: Content of the file.
        symbols: List of symbol dictionaries defined in the file.
        imports: List of import statements.
        architecture_summary: Summary of how this file fits in the architecture.
        language: Programming language for syntax highlighting.
        notes: Optional list of correction notes affecting this file.

    Returns:
        The rendered prompt string.
    """
    prompt = FILE_TEMPLATE.render(
        file_path=file_path,
        content=content,
        symbols=_format_symbols(symbols),
        imports=_format_imports(imports),
        architecture_summary=architecture_summary or "No architecture context provided.",
        language=language,
    )

    if notes:
        prompt = _add_notes_to_prompt(prompt, notes)

    return prompt


def _format_notes(notes: list[dict[str, Any]]) -> str:
    """Format notes for inclusion in a prompt.

    Args:
        notes: List of note dictionaries with content, author, created_at.

    Returns:
        Formatted string representation of notes.
    """
    if not notes:
        return ""

    lines = ["## Developer Corrections (Ground Truth)", ""]
    lines.append(
        "The following corrections have been provided by developers and MUST be incorporated:"
    )
    lines.append("")

    for i, note in enumerate(notes, 1):
        content = note.get("content", "")
        author = note.get("author", "Unknown")
        created_at = note.get("created_at", "")

        lines.append(f"### Correction {i}")
        if author:
            lines.append(f"*From: {author}*")
        if created_at:
            lines.append(f"*Date: {created_at}*")
        lines.append("")
        lines.append(content)
        lines.append("")

    return "\n".join(lines)


def _add_notes_to_prompt(prompt: str, notes: list[dict[str, Any]]) -> str:
    """Add notes section to a prompt.

    Args:
        prompt: Original prompt.
        notes: List of correction notes.

    Returns:
        Prompt with notes section added.
    """
    notes_section = _format_notes(notes)
    if notes_section:
        # Insert notes before the "---" separator
        if "---" in prompt:
            parts = prompt.split("---", 1)
            return parts[0] + notes_section + "\n---" + parts[1]
        else:
            return prompt + "\n\n" + notes_section

    return prompt


def get_notes_for_target(
    db: Any,
    scope: str,
    target: str,
) -> list[dict[str, Any]]:
    """Load notes that affect a specific target.

    Args:
        db: Database connection.
        scope: Note scope ('file', 'directory', 'workflow', 'general').
        target: Target path.

    Returns:
        List of note dictionaries.
    """
    # Query notes by scope and target
    sql = """
        SELECT content, author, created_at
        FROM notes
        WHERE (scope = ? AND target = ?)
           OR scope = 'general'
        ORDER BY created_at DESC
    """

    try:
        cursor = db.execute(sql, (scope, target))
        notes = []
        for row in cursor.fetchall():
            notes.append(
                {
                    "content": row["content"],
                    "author": row["author"],
                    "created_at": row["created_at"],
                }
            )
        return notes
    except Exception:
        return []


def get_synthesis_prompt(
    file_summaries: list[Any],
    directory_summaries: list[Any],
) -> str:
    """Generate a prompt for synthesizing summaries into a codebase understanding.

    Args:
        file_summaries: List of FileSummary objects.
        directory_summaries: List of DirectorySummary objects.

    Returns:
        The rendered prompt string.
    """
    return SYNTHESIS_TEMPLATE.render(
        file_summaries=_format_file_summaries(file_summaries),
        directory_summaries=_format_directory_summaries(directory_summaries),
    )
