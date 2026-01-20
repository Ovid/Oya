"""Summary data models for bottom-up wiki generation.

These models capture structured information extracted from file and directory
documentation to enable synthesis into higher-level architecture understanding.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

import logging

logger = logging.getLogger(__name__)

# Issue categories for validation. These are code logic constants, not configuration.
ISSUE_CATEGORIES: frozenset[str] = frozenset(["security", "reliability", "maintainability"])

# Issue severities for validation. These are code logic constants, not configuration.
ISSUE_SEVERITIES: frozenset[str] = frozenset(["problem", "suggestion"])


# Valid layer classifications for code files
VALID_LAYERS: frozenset[str] = frozenset(
    ["api", "domain", "infrastructure", "utility", "config", "test"]
)


def path_to_slug(path: str, include_extension: bool = True) -> str:
    """Convert a file or directory path to a URL-safe slug.

    Args:
        path: File or directory path to convert.
        include_extension: If True, replace dots with dashes (for file paths).
                          If False, preserve dots (for directory paths).

    Returns:
        URL-safe slug string.
    """
    slug = path.replace("/", "-").replace("\\", "-")
    if include_extension:
        slug = slug.replace(".", "-")
    slug = re.sub(r"[^a-zA-Z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


@dataclass
class FileIssue:
    """A potential issue identified in a source file.

    Represents bugs, security concerns, or design flaws detected during
    file analysis. Issues are stored both in FileSummary (for display)
    and in a dedicated ChromaDB collection (for Q&A queries).

    Attributes:
        file_path: Path to the source file containing the issue.
        category: Type of issue (security, reliability, maintainability).
        severity: Urgency level (problem, suggestion).
        title: Brief description of the issue.
        description: Detailed explanation of why this matters.
        line_range: Optional (start, end) line numbers where issue occurs.
    """

    file_path: str
    category: str
    severity: str
    title: str
    description: str
    line_range: tuple[int, int] | None = None

    def __post_init__(self):
        """Validate category and severity fields."""
        if self.category not in ISSUE_CATEGORIES:
            raise ValueError(
                f"Invalid category '{self.category}'. "
                f"Must be one of: {', '.join(sorted(ISSUE_CATEGORIES))}"
            )
        if self.severity not in ISSUE_SEVERITIES:
            raise ValueError(
                f"Invalid severity '{self.severity}'. "
                f"Must be one of: {', '.join(sorted(ISSUE_SEVERITIES))}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        result: dict[str, Any] = {
            "file_path": self.file_path,
            "category": self.category,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
        }
        if self.line_range:
            result["line_start"] = self.line_range[0]
            result["line_end"] = self.line_range[1]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileIssue":
        """Deserialize from dictionary."""
        line_range = None
        if "line_start" in data and "line_end" in data:
            line_range = (data["line_start"], data["line_end"])
        elif "lines" in data and isinstance(data["lines"], list) and len(data["lines"]) >= 2:
            line_range = (data["lines"][0], data["lines"][1])

        # Validate category and severity, using defaults if invalid
        category = data.get("category", "maintainability")
        if category not in ISSUE_CATEGORIES:
            category = "maintainability"

        severity = data.get("severity", "suggestion")
        if severity not in ISSUE_SEVERITIES:
            severity = "suggestion"

        return cls(
            file_path=data.get("file_path", ""),
            category=category,
            severity=severity,
            title=data.get("title", ""),
            description=data.get("description", ""),
            line_range=line_range,
        )


@dataclass
class FileSummary:
    """Structured summary extracted from file documentation.

    Captures the essential information about a source file including its purpose,
    architectural layer, key abstractions, dependencies, and detected issues.

    Attributes:
        file_path: Path to the source file relative to repository root.
        purpose: One-sentence description of what the file does.
        layer: Classification of code responsibility (api, domain, infrastructure,
               utility, config, or test).
        key_abstractions: Primary classes, functions, or types defined in the file.
        internal_deps: Paths to other files in the repository that this file depends on.
        external_deps: External libraries or packages the file imports.
        issues: List of FileIssue objects representing detected code issues.
    """

    file_path: str
    purpose: str
    layer: str
    key_abstractions: list[str] = field(default_factory=list)
    internal_deps: list[str] = field(default_factory=list)
    external_deps: list[str] = field(default_factory=list)
    issues: list[FileIssue] = field(default_factory=list)

    def __post_init__(self):
        """Validate layer field after initialization."""
        if self.layer not in VALID_LAYERS:
            raise ValueError(
                f"Invalid layer '{self.layer}'. Must be one of: {', '.join(sorted(VALID_LAYERS))}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the FileSummary to a dictionary.

        Returns:
            Dictionary representation of the FileSummary for JSON storage.
        """
        return {
            "file_path": self.file_path,
            "purpose": self.purpose,
            "layer": self.layer,
            "key_abstractions": self.key_abstractions,
            "internal_deps": self.internal_deps,
            "external_deps": self.external_deps,
            "issues": [issue.to_dict() for issue in self.issues],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileSummary":
        """Deserialize a FileSummary from a dictionary.

        Args:
            data: Dictionary representation of a FileSummary.

        Returns:
            A new FileSummary instance.
        """
        issues_data = data.get("issues", [])
        issues = [FileIssue.from_dict(issue_data) for issue_data in issues_data]

        return cls(
            file_path=data.get("file_path", ""),
            purpose=data.get("purpose", "Unknown"),
            layer=data.get("layer", "utility"),
            key_abstractions=data.get("key_abstractions", []),
            internal_deps=data.get("internal_deps", []),
            external_deps=data.get("external_deps", []),
            issues=issues,
        )


@dataclass
class DirectorySummary:
    """Structured summary extracted from directory documentation.

    Captures the essential information about a directory/module including its purpose,
    contained files, and role in the overall system architecture.

    Attributes:
        directory_path: Path to the directory relative to repository root.
        purpose: One-sentence description of what the directory/module is responsible for.
        contains: List of files contained in the directory.
        role_in_system: Description of how this directory fits into the overall architecture.
    """

    directory_path: str
    purpose: str
    contains: list[str] = field(default_factory=list)
    role_in_system: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the DirectorySummary to a dictionary.

        Returns:
            Dictionary representation of the DirectorySummary for JSON storage.
        """
        return {
            "directory_path": self.directory_path,
            "purpose": self.purpose,
            "contains": self.contains,
            "role_in_system": self.role_in_system,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DirectorySummary":
        """Deserialize a DirectorySummary from a dictionary.

        Args:
            data: Dictionary representation of a DirectorySummary.

        Returns:
            A new DirectorySummary instance.
        """
        return cls(
            directory_path=data.get("directory_path", ""),
            purpose=data.get("purpose", "Unknown"),
            contains=data.get("contains", []),
            role_in_system=data.get("role_in_system", ""),
        )


@dataclass
class LayerInfo:
    """Information about a code layer in the system architecture.

    Represents a logical grouping of code by responsibility (e.g., api, domain,
    infrastructure) with associated directories and files.

    Attributes:
        name: The layer name (e.g., "api", "domain", "infrastructure").
        purpose: Description of what this layer is responsible for.
        directories: List of directory paths belonging to this layer.
        files: List of file paths belonging to this layer.
    """

    name: str
    purpose: str
    directories: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)


@dataclass
class ComponentInfo:
    """Information about a key component in the codebase.

    Represents an important abstraction (class, function, module) that plays
    a significant role in the system architecture.

    Attributes:
        name: The component name (e.g., class or function name).
        file: Path to the file containing this component.
        role: Description of what role this component plays in the system.
        layer: The architectural layer this component belongs to.
    """

    name: str
    file: str
    role: str
    layer: str


@dataclass
class EntryPointInfo:
    """Information about an entry point in the codebase.

    Represents a CLI command, API route, or main function that serves
    as a starting point for users interacting with the system.

    Attributes:
        name: The entry point name (e.g., function name).
        entry_type: Type of entry point (cli_command, api_route, main_function).
        file: Path to the file containing this entry point.
        description: Route path, CLI command name, or other descriptor.
    """

    name: str
    entry_type: str
    file: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "entry_type": self.entry_type,
            "file": self.file,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntryPointInfo":
        """Deserialize from dictionary."""
        return cls(
            name=data.get("name", ""),
            entry_type=data.get("entry_type", ""),
            file=data.get("file", ""),
            description=data.get("description", ""),
        )


@dataclass
class CodeMetrics:
    """Aggregated code metrics for the codebase.

    Provides quantitative information about project scale and distribution
    of code across architectural layers.

    Attributes:
        total_files: Total number of analyzed files.
        files_by_layer: Count of files per architectural layer.
        lines_by_layer: Lines of code per architectural layer.
        total_lines: Total lines of code across all files.
    """

    total_files: int
    files_by_layer: dict[str, int]
    lines_by_layer: dict[str, int]
    total_lines: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "total_files": self.total_files,
            "files_by_layer": self.files_by_layer,
            "lines_by_layer": self.lines_by_layer,
            "total_lines": self.total_lines,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CodeMetrics":
        """Deserialize from dictionary."""
        return cls(
            total_files=data.get("total_files", 0),
            files_by_layer=dict(data.get("files_by_layer", {})),
            lines_by_layer=dict(data.get("lines_by_layer", {})),
            total_lines=data.get("total_lines", 0),
        )


@dataclass
class SynthesisMap:
    """Aggregated codebase understanding synthesized from file and directory summaries.

    Combines all File_Summaries and Directory_Summaries into a coherent map of the
    codebase, including layer groupings, key components, and dependency relationships.
    This serves as the primary context for generating Architecture and Overview pages.

    Attributes:
        layers: Mapping of layer names to LayerInfo objects.
        key_components: List of important components identified across the codebase.
        dependency_graph: Mapping of component/layer names to their dependencies.
        project_summary: LLM-generated overall summary of the project.
        entry_points: List of discovered CLI commands, API routes, main functions.
        tech_stack: Nested dict of detected libraries by language and category.
        metrics: CodeMetrics object with file counts and LOC.
        layer_interactions: LLM-generated description of how layers communicate.
    """

    layers: dict[str, LayerInfo] = field(default_factory=dict)
    key_components: list[ComponentInfo] = field(default_factory=list)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    project_summary: str = ""
    entry_points: list[EntryPointInfo] = field(default_factory=list)
    tech_stack: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    metrics: CodeMetrics | None = None
    layer_interactions: str = ""

    def to_json(self) -> str:
        """Serialize the SynthesisMap to a JSON string.

        Returns:
            JSON string representation of the SynthesisMap.
        """
        data = {
            "layers": {
                name: {
                    "name": layer.name,
                    "purpose": layer.purpose,
                    "directories": layer.directories,
                    "files": layer.files,
                }
                for name, layer in self.layers.items()
            },
            "key_components": [
                {
                    "name": comp.name,
                    "file": comp.file,
                    "role": comp.role,
                    "layer": comp.layer,
                }
                for comp in self.key_components
            ],
            "dependency_graph": self.dependency_graph,
            "project_summary": self.project_summary,
            "entry_points": [ep.to_dict() for ep in self.entry_points],
            "tech_stack": self.tech_stack,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "layer_interactions": self.layer_interactions,
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "SynthesisMap":
        """Deserialize a SynthesisMap from a JSON string.

        Args:
            json_str: JSON string representation of a SynthesisMap.

        Returns:
            A new SynthesisMap instance.
        """
        data = json.loads(json_str)

        layers = {
            name: LayerInfo(
                name=layer_data["name"],
                purpose=layer_data["purpose"],
                directories=layer_data.get("directories", []),
                files=layer_data.get("files", []),
            )
            for name, layer_data in data.get("layers", {}).items()
        }

        key_components = [
            ComponentInfo(
                name=comp["name"],
                file=comp["file"],
                role=comp["role"],
                layer=comp["layer"],
            )
            for comp in data.get("key_components", [])
        ]

        entry_points = [EntryPointInfo.from_dict(ep) for ep in data.get("entry_points", [])]

        metrics_data = data.get("metrics")
        metrics = CodeMetrics.from_dict(metrics_data) if metrics_data else None

        return cls(
            layers=layers,
            key_components=key_components,
            dependency_graph=data.get("dependency_graph", {}),
            project_summary=data.get("project_summary", ""),
            entry_points=entry_points,
            tech_stack=data.get("tech_stack", {}),
            metrics=metrics,
            layer_interactions=data.get("layer_interactions", ""),
        )


class SummaryParser:
    """Parses structured summaries from LLM-generated markdown.

    Extracts YAML summary blocks from markdown content and converts them
    to FileSummary or DirectorySummary objects. The YAML block is stripped
    from the returned markdown content.
    """

    # Regex pattern to match YAML blocks delimited by ---
    YAML_BLOCK_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.MULTILINE | re.DOTALL)

    def _extract_yaml_block(self, markdown: str) -> tuple[str | None, str]:
        """Extract YAML content from markdown and return clean markdown.

        Args:
            markdown: The full markdown content potentially containing a YAML block.

        Returns:
            A tuple of (yaml_content, clean_markdown) where yaml_content is None
            if no valid YAML block was found.
        """
        match = self.YAML_BLOCK_PATTERN.search(markdown)

        if not match:
            return None, markdown

        yaml_content = match.group(1)
        clean_markdown = self.YAML_BLOCK_PATTERN.sub("", markdown).strip()

        return yaml_content, clean_markdown

    def _parse_yaml_safely(self, yaml_content: str) -> dict[str, Any] | None:
        """Safely parse YAML content, returning None on failure.

        Args:
            yaml_content: Raw YAML string to parse.

        Returns:
            Parsed dict or None if parsing fails.
        """
        try:
            data = yaml.safe_load(yaml_content)
            return data if isinstance(data, dict) else None
        except yaml.YAMLError:
            return None

    def _ensure_list(self, value: Any) -> list[str]:
        """Ensure a value is a list of strings.

        Args:
            value: Any value that should be a list.

        Returns:
            The value as a list, or empty list if not a list.
        """
        return value if isinstance(value, list) else []

    def _parse_issues(self, issues_data: Any, file_path: str) -> list[FileIssue]:
        """Parse issues from YAML data into FileIssue objects.

        Args:
            issues_data: Raw issues data from YAML (expected to be a list of dicts).
            file_path: Path to the file, added to each issue.

        Returns:
            List of successfully parsed FileIssue objects.
        """
        if not isinstance(issues_data, list):
            return []

        issues = []
        for item in issues_data:
            if not isinstance(item, dict):
                continue

            # Create a copy with file_path added to avoid mutating input data
            item_with_path = {**item, "file_path": file_path}

            try:
                issue = FileIssue.from_dict(item_with_path)
                issues.append(issue)
            except (ValueError, KeyError) as e:
                logger.warning(f"Failed to parse issue for {file_path}: {e}. Item: {item}")

        return issues

    def parse_file_summary(self, markdown: str, file_path: str) -> tuple[str, FileSummary]:
        """Parse File_Summary from markdown, return (clean_markdown, summary).

        Extracts the YAML block containing file_summary data from the markdown,
        parses it into a FileSummary object, and returns the markdown with the
        YAML block removed.

        Args:
            markdown: The full markdown content potentially containing a YAML block.
            file_path: The path to the file being summarized.

        Returns:
            A tuple of (clean_markdown, FileSummary) where clean_markdown has
            the YAML block removed.
        """
        yaml_content, clean_markdown = self._extract_yaml_block(markdown)

        if yaml_content is None:
            return markdown, self._fallback_file_summary(file_path)

        data = self._parse_yaml_safely(yaml_content)

        if data is None or "file_summary" not in data:
            return markdown, self._fallback_file_summary(file_path)

        summary_data = data["file_summary"]

        if not isinstance(summary_data, dict):
            return markdown, self._fallback_file_summary(file_path)

        # Extract and validate fields
        purpose = summary_data.get("purpose", "Unknown")
        layer = summary_data.get("layer", "utility")

        # Validate layer, default to utility if invalid
        if layer not in VALID_LAYERS:
            logger.warning(
                f"Invalid layer '{layer}' for {file_path}, defaulting to 'utility'. "
                f"Valid layers: {', '.join(sorted(VALID_LAYERS))}"
            )
            layer = "utility"

        # Parse issues from YAML
        issues = self._parse_issues(summary_data.get("issues", []), file_path)

        summary = FileSummary(
            file_path=file_path,
            purpose=purpose,
            layer=layer,
            key_abstractions=self._ensure_list(summary_data.get("key_abstractions", [])),
            internal_deps=self._ensure_list(summary_data.get("internal_deps", [])),
            external_deps=self._ensure_list(summary_data.get("external_deps", [])),
            issues=issues,
        )

        return clean_markdown, summary

    def _fallback_file_summary(self, file_path: str) -> FileSummary:
        """Create a fallback FileSummary with default values.

        Used when YAML parsing fails or no YAML block is found.
        """
        logger.warning(
            f"YAML parsing failed for {file_path}, using fallback summary "
            "(purpose='Unknown', layer='utility')"
        )
        return FileSummary(
            file_path=file_path,
            purpose="Unknown",
            layer="utility",
            key_abstractions=[],
            internal_deps=[],
            external_deps=[],
        )

    def parse_directory_summary(
        self, markdown: str, directory_path: str
    ) -> tuple[str, DirectorySummary]:
        """Parse Directory_Summary from markdown, return (clean_markdown, summary).

        Extracts the YAML block containing directory_summary data from the markdown,
        parses it into a DirectorySummary object, and returns the markdown with the
        YAML block removed.

        Args:
            markdown: The full markdown content potentially containing a YAML block.
            directory_path: The path to the directory being summarized.

        Returns:
            A tuple of (clean_markdown, DirectorySummary) where clean_markdown has
            the YAML block removed.
        """
        yaml_content, clean_markdown = self._extract_yaml_block(markdown)

        if yaml_content is None:
            return markdown, self._fallback_directory_summary(directory_path)

        data = self._parse_yaml_safely(yaml_content)

        if data is None or "directory_summary" not in data:
            return markdown, self._fallback_directory_summary(directory_path)

        summary_data = data["directory_summary"]

        if not isinstance(summary_data, dict):
            return markdown, self._fallback_directory_summary(directory_path)

        summary = DirectorySummary(
            directory_path=directory_path,
            purpose=summary_data.get("purpose", "Unknown"),
            contains=self._ensure_list(summary_data.get("contains", [])),
            role_in_system=summary_data.get("role_in_system", ""),
        )

        return clean_markdown, summary

    def _fallback_directory_summary(self, directory_path: str) -> DirectorySummary:
        """Create a fallback DirectorySummary with default values.

        Used when YAML parsing fails or no YAML block is found.
        """
        logger.warning(
            f"YAML parsing failed for {directory_path}, using fallback summary (purpose='Unknown')"
        )
        return DirectorySummary(
            directory_path=directory_path,
            purpose="Unknown",
            contains=[],
            role_in_system="",
        )
