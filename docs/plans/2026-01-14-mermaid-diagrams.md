# Mermaid Diagram Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace LLM-generated Mermaid diagrams with Python-generated ones, plus syntax validation.

**Architecture:** Create a `mermaid.py` module with generators for layer, dependency, and class diagrams. Add a `mermaid_validator.py` for syntax validation. Integrate into `architecture.py` to inject validated diagrams after LLM generates prose content.

**Tech Stack:** Python dataclasses, regex for validation, existing SynthesisMap/ParsedSymbol models

---

## Task 1: Create MermaidValidator Module

**Files:**
- Create: `backend/src/oya/generation/mermaid_validator.py`
- Test: `backend/tests/test_mermaid_validator.py`

**Step 1: Write the failing test**

Create `backend/tests/test_mermaid_validator.py`:

```python
"""Tests for Mermaid diagram validation."""

import pytest

from oya.generation.mermaid_validator import ValidationResult, validate_mermaid


class TestValidateMermaid:
    """Tests for validate_mermaid function."""

    def test_valid_flowchart_returns_valid(self):
        """Valid flowchart diagram passes validation."""
        diagram = """flowchart TB
    A[Start] --> B[Process]
    B --> C[End]
"""
        result = validate_mermaid(diagram)
        assert result.valid is True
        assert result.errors == []

    def test_missing_diagram_type_returns_invalid(self):
        """Diagram without type declaration is invalid."""
        diagram = """A --> B
    B --> C
"""
        result = validate_mermaid(diagram)
        assert result.valid is False
        assert any("diagram type" in e.lower() for e in result.errors)

    def test_unbalanced_brackets_returns_invalid(self):
        """Unbalanced brackets are detected."""
        diagram = """flowchart TB
    A[Start --> B[Process]
"""
        result = validate_mermaid(diagram)
        assert result.valid is False
        assert any("bracket" in e.lower() for e in result.errors)

    def test_unmatched_subgraph_returns_invalid(self):
        """Subgraph without end is detected."""
        diagram = """flowchart TB
    subgraph Layer1
        A --> B
"""
        result = validate_mermaid(diagram)
        assert result.valid is False
        assert any("subgraph" in e.lower() for e in result.errors)

    def test_valid_subgraph_returns_valid(self):
        """Properly closed subgraph passes validation."""
        diagram = """flowchart TB
    subgraph Layer1
        A --> B
    end
"""
        result = validate_mermaid(diagram)
        assert result.valid is True

    def test_valid_class_diagram_returns_valid(self):
        """Valid classDiagram passes validation."""
        diagram = """classDiagram
    class Animal {
        +name: string
        +speak()
    }
"""
        result = validate_mermaid(diagram)
        assert result.valid is True
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_validator.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'oya.generation.mermaid_validator'"

**Step 3: Write minimal implementation**

Create `backend/src/oya/generation/mermaid_validator.py`:

```python
"""Mermaid diagram syntax validation."""

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of Mermaid diagram validation.

    Attributes:
        valid: True if the diagram syntax is valid.
        errors: List of human-readable error messages.
        line_numbers: Lines where errors were found.
    """

    valid: bool
    errors: list[str] = field(default_factory=list)
    line_numbers: list[int] = field(default_factory=list)


# Valid Mermaid diagram types
VALID_DIAGRAM_TYPES = frozenset([
    "flowchart",
    "graph",
    "sequenceDiagram",
    "classDiagram",
    "stateDiagram",
    "stateDiagram-v2",
    "erDiagram",
    "journey",
    "gantt",
    "pie",
    "quadrantChart",
    "requirementDiagram",
    "gitGraph",
    "mindmap",
    "timeline",
    "zenuml",
])


def validate_mermaid(content: str) -> ValidationResult:
    """Validate Mermaid diagram syntax.

    Performs structural validation including:
    - Diagram type declaration present
    - Balanced brackets [], (), {}
    - Subgraph/end pairing

    Args:
        content: Mermaid diagram content to validate.

    Returns:
        ValidationResult with validity status and any errors.
    """
    errors: list[str] = []
    line_numbers: list[int] = []

    lines = content.strip().split("\n")
    if not lines:
        return ValidationResult(valid=False, errors=["Empty diagram"], line_numbers=[0])

    # Check diagram type declaration
    first_line = lines[0].strip().lower()
    has_valid_type = any(first_line.startswith(dt) for dt in VALID_DIAGRAM_TYPES)
    if not has_valid_type:
        errors.append(f"Missing or invalid diagram type. Must start with one of: flowchart, classDiagram, etc.")
        line_numbers.append(1)

    # Check balanced brackets
    bracket_pairs = [("[", "]"), ("(", ")"), ("{", "}")]
    for open_char, close_char in bracket_pairs:
        open_count = content.count(open_char)
        close_count = content.count(close_char)
        if open_count != close_count:
            errors.append(f"Unbalanced brackets: {open_count} '{open_char}' vs {close_count} '{close_char}'")

    # Check subgraph/end pairing
    subgraph_count = len(re.findall(r"^\s*subgraph\b", content, re.MULTILINE | re.IGNORECASE))
    end_count = len(re.findall(r"^\s*end\b", content, re.MULTILINE | re.IGNORECASE))
    if subgraph_count != end_count:
        errors.append(f"Unmatched subgraph/end: {subgraph_count} subgraphs vs {end_count} ends")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        line_numbers=line_numbers,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_validator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams
git add backend/src/oya/generation/mermaid_validator.py backend/tests/test_mermaid_validator.py
git commit -m "feat(mermaid): add Mermaid syntax validator"
```

---

## Task 2: Create Label Sanitization Utility

**Files:**
- Modify: `backend/src/oya/generation/mermaid_validator.py`
- Modify: `backend/tests/test_mermaid_validator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_mermaid_validator.py`:

```python
from oya.generation.mermaid_validator import sanitize_label, sanitize_node_id


class TestSanitizeLabel:
    """Tests for label sanitization."""

    def test_removes_newlines(self):
        """Newlines are replaced with spaces."""
        result = sanitize_label("Hello\nWorld")
        assert "\n" not in result
        assert "Hello" in result and "World" in result

    def test_escapes_brackets(self):
        """Brackets are escaped or removed."""
        result = sanitize_label("foo(bar)[baz]")
        # Should not contain raw brackets that break Mermaid
        assert "(" not in result or result.count("(") == result.count(")")

    def test_truncates_long_labels(self):
        """Labels over max_length are truncated with ellipsis."""
        long_text = "a" * 100
        result = sanitize_label(long_text, max_length=40)
        assert len(result) <= 43  # 40 + "..."

    def test_preserves_short_labels(self):
        """Short labels are not truncated."""
        result = sanitize_label("short", max_length=40)
        assert result == "short"

    def test_handles_quotes(self):
        """Quotes are escaped or removed."""
        result = sanitize_label('He said "hello"')
        # Result should be safe for Mermaid
        assert result.count('"') % 2 == 0 or '"' not in result


class TestSanitizeNodeId:
    """Tests for node ID sanitization."""

    def test_replaces_dots_with_underscores(self):
        """Dots are replaced for valid IDs."""
        result = sanitize_node_id("oya.config.Settings")
        assert "." not in result

    def test_removes_special_chars(self):
        """Special characters are removed."""
        result = sanitize_node_id("my-class@v2!")
        assert "@" not in result
        assert "!" not in result

    def test_handles_slashes(self):
        """Slashes from paths are handled."""
        result = sanitize_node_id("src/oya/config.py")
        assert "/" not in result
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_validator.py::TestSanitizeLabel -v`
Expected: FAIL with "cannot import name 'sanitize_label'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/mermaid_validator.py`:

```python
def sanitize_label(text: str, max_length: int = 40) -> str:
    """Make text safe for Mermaid node labels.

    Handles problematic characters and truncates long labels.

    Args:
        text: Raw text to sanitize.
        max_length: Maximum length before truncation.

    Returns:
        Sanitized label safe for Mermaid diagrams.
    """
    # Replace newlines with spaces
    result = text.replace("\n", " ").replace("\r", "")

    # Remove or escape problematic characters
    # Brackets in labels need special handling
    result = result.replace("[", "(").replace("]", ")")
    result = result.replace("{", "(").replace("}", ")")
    result = result.replace('"', "'")
    result = result.replace("<", "").replace(">", "")

    # Collapse multiple spaces
    result = " ".join(result.split())

    # Truncate if too long
    if len(result) > max_length:
        result = result[: max_length - 3] + "..."

    return result


def sanitize_node_id(text: str) -> str:
    """Make text safe for Mermaid node IDs.

    Node IDs should only contain alphanumeric, underscore, and hyphen.

    Args:
        text: Raw text to convert to node ID.

    Returns:
        Valid Mermaid node ID.
    """
    # Replace common separators with underscores
    result = text.replace(".", "_").replace("/", "_").replace("-", "_")

    # Remove any remaining special characters
    result = re.sub(r"[^a-zA-Z0-9_]", "", result)

    # Collapse multiple underscores
    result = re.sub(r"_+", "_", result)

    # Ensure it doesn't start with a number
    if result and result[0].isdigit():
        result = "n" + result

    return result.strip("_")
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_validator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams
git add backend/src/oya/generation/mermaid_validator.py backend/tests/test_mermaid_validator.py
git commit -m "feat(mermaid): add label and node ID sanitization"
```

---

## Task 3: Create LayerDiagramGenerator

**Files:**
- Create: `backend/src/oya/generation/mermaid.py`
- Create: `backend/tests/test_mermaid_generator.py`

**Step 1: Write the failing test**

Create `backend/tests/test_mermaid_generator.py`:

```python
"""Tests for Mermaid diagram generators."""

import pytest

from oya.generation.mermaid import LayerDiagramGenerator
from oya.generation.mermaid_validator import validate_mermaid
from oya.generation.summaries import ComponentInfo, LayerInfo, SynthesisMap


class TestLayerDiagramGenerator:
    """Tests for LayerDiagramGenerator."""

    @pytest.fixture
    def sample_synthesis_map(self) -> SynthesisMap:
        """Create a sample SynthesisMap for testing."""
        return SynthesisMap(
            layers={
                "api": LayerInfo(
                    name="api",
                    purpose="HTTP endpoints",
                    directories=["src/api"],
                    files=["src/api/routes.py", "src/api/schemas.py"],
                ),
                "domain": LayerInfo(
                    name="domain",
                    purpose="Business logic",
                    directories=["src/domain"],
                    files=["src/domain/service.py"],
                ),
            },
            key_components=[
                ComponentInfo(name="Router", file="src/api/routes.py", role="HTTP routing", layer="api"),
                ComponentInfo(name="Service", file="src/domain/service.py", role="Core logic", layer="domain"),
            ],
            dependency_graph={"api": ["domain"]},
        )

    def test_generates_valid_mermaid(self, sample_synthesis_map):
        """Generated diagram passes Mermaid validation."""
        generator = LayerDiagramGenerator()
        diagram = generator.generate(sample_synthesis_map)

        result = validate_mermaid(diagram)
        assert result.valid, f"Invalid diagram: {result.errors}"

    def test_includes_all_layers(self, sample_synthesis_map):
        """All layers appear as subgraphs."""
        generator = LayerDiagramGenerator()
        diagram = generator.generate(sample_synthesis_map)

        assert "subgraph" in diagram.lower()
        assert "api" in diagram.lower()
        assert "domain" in diagram.lower()

    def test_includes_key_components(self, sample_synthesis_map):
        """Key components appear in the diagram."""
        generator = LayerDiagramGenerator()
        diagram = generator.generate(sample_synthesis_map)

        assert "Router" in diagram
        assert "Service" in diagram

    def test_includes_dependencies(self, sample_synthesis_map):
        """Layer dependencies are shown as arrows."""
        generator = LayerDiagramGenerator()
        diagram = generator.generate(sample_synthesis_map)

        # Should have an arrow showing api depends on domain
        assert "-->" in diagram

    def test_empty_synthesis_map_returns_minimal_diagram(self):
        """Empty input produces valid minimal diagram."""
        generator = LayerDiagramGenerator()
        diagram = generator.generate(SynthesisMap())

        result = validate_mermaid(diagram)
        assert result.valid
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_generator.py::TestLayerDiagramGenerator -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'oya.generation.mermaid'"

**Step 3: Write minimal implementation**

Create `backend/src/oya/generation/mermaid.py`:

```python
"""Mermaid diagram generators for architecture documentation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from oya.generation.mermaid_validator import sanitize_label, sanitize_node_id

if TYPE_CHECKING:
    from oya.generation.summaries import SynthesisMap
    from oya.parsing.models import ParsedSymbol


class LayerDiagramGenerator:
    """Generates layer architecture diagrams from SynthesisMap.

    Creates a flowchart showing architectural layers as subgraphs
    with key components inside and dependency arrows between layers.
    """

    def generate(self, synthesis_map: SynthesisMap) -> str:
        """Generate a layer diagram from SynthesisMap.

        Args:
            synthesis_map: SynthesisMap with layers, components, and dependencies.

        Returns:
            Mermaid flowchart diagram string.
        """
        lines = ["flowchart TB"]

        if not synthesis_map.layers:
            lines.append("    NoLayers[No layers detected]")
            return "\n".join(lines)

        # Create subgraph for each layer
        for layer_name, layer_info in synthesis_map.layers.items():
            layer_id = sanitize_node_id(layer_name)
            layer_label = sanitize_label(f"{layer_name}: {layer_info.purpose}", max_length=50)

            lines.append(f'    subgraph {layer_id}["{layer_label}"]')

            # Add components belonging to this layer
            layer_components = [
                c for c in synthesis_map.key_components if c.layer == layer_name
            ]

            if layer_components:
                for comp in layer_components[:5]:  # Limit to 5 per layer
                    comp_id = sanitize_node_id(f"{layer_name}_{comp.name}")
                    comp_label = sanitize_label(comp.name)
                    lines.append(f'        {comp_id}["{comp_label}"]')
            else:
                # Add placeholder if no components
                placeholder_id = sanitize_node_id(f"{layer_name}_placeholder")
                lines.append(f"        {placeholder_id}[...]")

            lines.append("    end")

        # Add dependency arrows between layers
        for source, targets in synthesis_map.dependency_graph.items():
            source_id = sanitize_node_id(source)
            if isinstance(targets, list):
                for target in targets:
                    target_id = sanitize_node_id(target)
                    if source_id != target_id:
                        lines.append(f"    {source_id} --> {target_id}")

        return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_generator.py::TestLayerDiagramGenerator -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams
git add backend/src/oya/generation/mermaid.py backend/tests/test_mermaid_generator.py
git commit -m "feat(mermaid): add LayerDiagramGenerator"
```

---

## Task 4: Create DependencyGraphGenerator

**Files:**
- Modify: `backend/src/oya/generation/mermaid.py`
- Modify: `backend/tests/test_mermaid_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_mermaid_generator.py`:

```python
from oya.generation.mermaid import DependencyGraphGenerator


class TestDependencyGraphGenerator:
    """Tests for DependencyGraphGenerator."""

    @pytest.fixture
    def sample_file_imports(self) -> dict[str, list[str]]:
        """Sample file_imports dict from analysis."""
        return {
            "src/api/routes.py": ["src/domain/service.py", "src/config.py"],
            "src/domain/service.py": ["src/db/connection.py"],
            "src/config.py": [],
            "src/db/connection.py": [],
        }

    def test_generates_valid_mermaid(self, sample_file_imports):
        """Generated diagram passes Mermaid validation."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate(sample_file_imports)

        result = validate_mermaid(diagram)
        assert result.valid, f"Invalid diagram: {result.errors}"

    def test_shows_import_relationships(self, sample_file_imports):
        """Import relationships appear as arrows."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate(sample_file_imports)

        assert "-->" in diagram

    def test_includes_all_files(self, sample_file_imports):
        """All files appear in the diagram."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate(sample_file_imports)

        assert "routes" in diagram.lower()
        assert "service" in diagram.lower()

    def test_empty_imports_returns_minimal_diagram(self):
        """Empty input produces valid minimal diagram."""
        generator = DependencyGraphGenerator()
        diagram = generator.generate({})

        result = validate_mermaid(diagram)
        assert result.valid

    def test_limits_nodes_for_large_graphs(self):
        """Large graphs are limited to prevent overwhelming diagrams."""
        large_imports = {f"file{i}.py": [f"file{i+1}.py"] for i in range(100)}
        generator = DependencyGraphGenerator(max_nodes=20)
        diagram = generator.generate(large_imports)

        # Should still be valid
        result = validate_mermaid(diagram)
        assert result.valid
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_generator.py::TestDependencyGraphGenerator -v`
Expected: FAIL with "cannot import name 'DependencyGraphGenerator'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/mermaid.py`:

```python
class DependencyGraphGenerator:
    """Generates file dependency graphs from import analysis.

    Creates a flowchart showing which files import from which other files.
    """

    def __init__(self, max_nodes: int = 30):
        """Initialize the generator.

        Args:
            max_nodes: Maximum number of nodes to include (prevents huge diagrams).
        """
        self.max_nodes = max_nodes

    def generate(self, file_imports: dict[str, list[str]]) -> str:
        """Generate a dependency graph from file imports.

        Args:
            file_imports: Dict mapping file paths to list of imported file paths.

        Returns:
            Mermaid flowchart diagram string.
        """
        lines = ["flowchart LR"]

        if not file_imports:
            lines.append("    NoFiles[No files analyzed]")
            return "\n".join(lines)

        # Collect all unique files and limit
        all_files = set(file_imports.keys())
        for imports in file_imports.values():
            all_files.update(imports)

        # Sort by number of connections (most connected first)
        file_connections = {}
        for f in all_files:
            incoming = sum(1 for imports in file_imports.values() if f in imports)
            outgoing = len(file_imports.get(f, []))
            file_connections[f] = incoming + outgoing

        sorted_files = sorted(all_files, key=lambda f: file_connections[f], reverse=True)
        included_files = set(sorted_files[: self.max_nodes])

        # Create nodes for included files
        for file_path in sorted(included_files):
            node_id = sanitize_node_id(file_path)
            # Use just the filename for label
            filename = file_path.split("/")[-1]
            label = sanitize_label(filename, max_length=30)
            lines.append(f'    {node_id}["{label}"]')

        # Add edges for imports between included files
        for source, imports in file_imports.items():
            if source not in included_files:
                continue
            source_id = sanitize_node_id(source)
            for target in imports:
                if target in included_files:
                    target_id = sanitize_node_id(target)
                    lines.append(f"    {source_id} --> {target_id}")

        return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_generator.py::TestDependencyGraphGenerator -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams
git add backend/src/oya/generation/mermaid.py backend/tests/test_mermaid_generator.py
git commit -m "feat(mermaid): add DependencyGraphGenerator"
```

---

## Task 5: Create ClassDiagramGenerator

**Files:**
- Modify: `backend/src/oya/generation/mermaid.py`
- Modify: `backend/tests/test_mermaid_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_mermaid_generator.py`:

```python
from oya.generation.mermaid import ClassDiagramGenerator
from oya.parsing.models import ParsedSymbol, SymbolType


class TestClassDiagramGenerator:
    """Tests for ClassDiagramGenerator."""

    @pytest.fixture
    def sample_symbols(self) -> list[ParsedSymbol]:
        """Sample ParsedSymbol list with classes and methods."""
        return [
            ParsedSymbol(
                name="UserService",
                symbol_type=SymbolType.CLASS,
                start_line=1,
                end_line=20,
                metadata={"file": "src/service.py"},
            ),
            ParsedSymbol(
                name="get_user",
                symbol_type=SymbolType.METHOD,
                start_line=5,
                end_line=10,
                parent="UserService",
                signature="def get_user(self, user_id: int) -> User",
                metadata={"file": "src/service.py"},
            ),
            ParsedSymbol(
                name="create_user",
                symbol_type=SymbolType.METHOD,
                start_line=12,
                end_line=18,
                parent="UserService",
                signature="def create_user(self, name: str) -> User",
                metadata={"file": "src/service.py"},
            ),
            ParsedSymbol(
                name="Database",
                symbol_type=SymbolType.CLASS,
                start_line=1,
                end_line=15,
                metadata={"file": "src/db.py"},
            ),
        ]

    def test_generates_valid_mermaid(self, sample_symbols):
        """Generated diagram passes Mermaid validation."""
        generator = ClassDiagramGenerator()
        diagram = generator.generate(sample_symbols)

        result = validate_mermaid(diagram)
        assert result.valid, f"Invalid diagram: {result.errors}"

    def test_includes_classes(self, sample_symbols):
        """Classes appear in the diagram."""
        generator = ClassDiagramGenerator()
        diagram = generator.generate(sample_symbols)

        assert "UserService" in diagram
        assert "Database" in diagram

    def test_includes_methods(self, sample_symbols):
        """Methods appear under their parent class."""
        generator = ClassDiagramGenerator()
        diagram = generator.generate(sample_symbols)

        assert "get_user" in diagram
        assert "create_user" in diagram

    def test_empty_symbols_returns_minimal_diagram(self):
        """Empty input produces valid minimal diagram."""
        generator = ClassDiagramGenerator()
        diagram = generator.generate([])

        result = validate_mermaid(diagram)
        assert result.valid

    def test_limits_classes_for_large_codebases(self):
        """Large symbol lists are limited."""
        many_classes = [
            ParsedSymbol(
                name=f"Class{i}",
                symbol_type=SymbolType.CLASS,
                start_line=1,
                end_line=10,
                metadata={"file": f"file{i}.py"},
            )
            for i in range(50)
        ]
        generator = ClassDiagramGenerator(max_classes=10)
        diagram = generator.generate(many_classes)

        result = validate_mermaid(diagram)
        assert result.valid
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_generator.py::TestClassDiagramGenerator -v`
Expected: FAIL with "cannot import name 'ClassDiagramGenerator'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/mermaid.py`:

```python
from oya.parsing.models import ParsedSymbol, SymbolType


class ClassDiagramGenerator:
    """Generates class diagrams from parsed symbols.

    Creates a classDiagram showing classes and their methods.
    """

    def __init__(self, max_classes: int = 15, max_methods_per_class: int = 5):
        """Initialize the generator.

        Args:
            max_classes: Maximum number of classes to include.
            max_methods_per_class: Maximum methods to show per class.
        """
        self.max_classes = max_classes
        self.max_methods_per_class = max_methods_per_class

    def generate(self, symbols: list[ParsedSymbol]) -> str:
        """Generate a class diagram from parsed symbols.

        Args:
            symbols: List of ParsedSymbol objects from parsing.

        Returns:
            Mermaid classDiagram string.
        """
        lines = ["classDiagram"]

        # Extract classes and their methods
        classes = [s for s in symbols if s.symbol_type == SymbolType.CLASS]
        methods = [s for s in symbols if s.symbol_type == SymbolType.METHOD]

        if not classes:
            lines.append("    class NoClasses {")
            lines.append("        No classes found")
            lines.append("    }")
            return "\n".join(lines)

        # Group methods by parent class
        methods_by_class: dict[str, list[ParsedSymbol]] = {}
        for method in methods:
            if method.parent:
                methods_by_class.setdefault(method.parent, []).append(method)

        # Generate class definitions (limited)
        for cls in classes[: self.max_classes]:
            class_name = sanitize_node_id(cls.name)
            lines.append(f"    class {class_name} {{")

            # Add methods for this class
            cls_methods = methods_by_class.get(cls.name, [])
            for method in cls_methods[: self.max_methods_per_class]:
                method_name = sanitize_label(method.name, max_length=30)
                # Extract simple signature if available
                if method.signature:
                    # Simplify signature for display
                    sig = method.signature.replace("def ", "").replace("self, ", "")
                    sig = sanitize_label(sig, max_length=40)
                    lines.append(f"        +{sig}")
                else:
                    lines.append(f"        +{method_name}()")

            if not cls_methods:
                lines.append("        ...")

            lines.append("    }")

        return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_generator.py::TestClassDiagramGenerator -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams
git add backend/src/oya/generation/mermaid.py backend/tests/test_mermaid_generator.py
git commit -m "feat(mermaid): add ClassDiagramGenerator"
```

---

## Task 6: Create DiagramGenerator Facade

**Files:**
- Modify: `backend/src/oya/generation/mermaid.py`
- Modify: `backend/tests/test_mermaid_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_mermaid_generator.py`:

```python
from oya.generation.mermaid import DiagramGenerator


class TestDiagramGenerator:
    """Tests for DiagramGenerator facade."""

    @pytest.fixture
    def sample_data(self, sample_synthesis_map, sample_file_imports, sample_symbols):
        """Combine all sample data."""
        return {
            "synthesis_map": sample_synthesis_map,
            "file_imports": sample_file_imports,
            "symbols": sample_symbols,
        }

    def test_generate_all_returns_dict_of_diagrams(self, sample_data):
        """generate_all returns dict with all diagram types."""
        generator = DiagramGenerator()
        diagrams = generator.generate_all(
            synthesis_map=sample_data["synthesis_map"],
            file_imports=sample_data["file_imports"],
            symbols=sample_data["symbols"],
        )

        assert "layer" in diagrams
        assert "dependency" in diagrams
        assert "class" in diagrams

    def test_all_generated_diagrams_are_valid(self, sample_data):
        """All generated diagrams pass validation."""
        generator = DiagramGenerator()
        diagrams = generator.generate_all(
            synthesis_map=sample_data["synthesis_map"],
            file_imports=sample_data["file_imports"],
            symbols=sample_data["symbols"],
        )

        for name, diagram in diagrams.items():
            result = validate_mermaid(diagram)
            assert result.valid, f"{name} diagram invalid: {result.errors}"

    def test_handles_missing_data_gracefully(self):
        """Missing data produces valid minimal diagrams."""
        generator = DiagramGenerator()
        diagrams = generator.generate_all(
            synthesis_map=None,
            file_imports={},
            symbols=[],
        )

        for name, diagram in diagrams.items():
            result = validate_mermaid(diagram)
            assert result.valid, f"{name} diagram invalid: {result.errors}"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_generator.py::TestDiagramGenerator -v`
Expected: FAIL with "cannot import name 'DiagramGenerator'"

**Step 3: Write minimal implementation**

Add to `backend/src/oya/generation/mermaid.py`:

```python
class DiagramGenerator:
    """Facade for generating all diagram types.

    Provides a single interface to generate layer, dependency,
    and class diagrams from analysis data.
    """

    def __init__(self):
        """Initialize with default sub-generators."""
        self.layer_generator = LayerDiagramGenerator()
        self.dependency_generator = DependencyGraphGenerator()
        self.class_generator = ClassDiagramGenerator()

    def generate_all(
        self,
        synthesis_map: SynthesisMap | None = None,
        file_imports: dict[str, list[str]] | None = None,
        symbols: list[ParsedSymbol] | None = None,
    ) -> dict[str, str]:
        """Generate all diagram types from available data.

        Args:
            synthesis_map: SynthesisMap for layer diagram (optional).
            file_imports: File import dict for dependency diagram (optional).
            symbols: ParsedSymbol list for class diagram (optional).

        Returns:
            Dict mapping diagram name to Mermaid content.
        """
        from oya.generation.summaries import SynthesisMap as SynthesisMapClass

        diagrams = {}

        # Layer diagram
        if synthesis_map is not None:
            diagrams["layer"] = self.layer_generator.generate(synthesis_map)
        else:
            diagrams["layer"] = self.layer_generator.generate(SynthesisMapClass())

        # Dependency diagram
        diagrams["dependency"] = self.dependency_generator.generate(file_imports or {})

        # Class diagram
        diagrams["class"] = self.class_generator.generate(symbols or [])

        return diagrams
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_mermaid_generator.py::TestDiagramGenerator -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams
git add backend/src/oya/generation/mermaid.py backend/tests/test_mermaid_generator.py
git commit -m "feat(mermaid): add DiagramGenerator facade"
```

---

## Task 7: Update Architecture Prompt

**Files:**
- Modify: `backend/src/oya/generation/prompts.py`
- Test: `backend/tests/test_architecture_generator.py`

**Step 1: Locate and update the prompt**

Find the architecture prompt in `backend/src/oya/generation/prompts.py` around line 220-230 where it says:

```
3. **Component Diagram**: Create a Mermaid diagram showing the main components...
```

**Step 2: Update the prompt text**

In `backend/src/oya/generation/prompts.py`, change the architecture prompt to remove diagram generation:

Find the ARCHITECTURE_PROMPT_SYNTHESIS template (around line 210-250) and replace the "Component Diagram" instruction with:

```python
# In the template string, change:
# 3. **Component Diagram**: Create a Mermaid diagram showing the main components and their relationships based on the layer dependencies

# To:
# 3. **Component Relationships**: Describe the main components and how they interact. Focus on the relationships and data flow between layers. (Diagrams will be generated automatically from code analysis.)
```

**Step 3: Run existing architecture tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_architecture_generator.py -v`
Expected: PASS (tests should still pass as they test generation, not specific prompt content)

**Step 4: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams
git add backend/src/oya/generation/prompts.py
git commit -m "refactor(prompts): remove Mermaid diagram generation from architecture prompt"
```

---

## Task 8: Integrate Diagrams into Architecture Generator

**Files:**
- Modify: `backend/src/oya/generation/architecture.py`
- Modify: `backend/tests/test_architecture_generator.py`

**Step 1: Write the failing test**

Add to `backend/tests/test_architecture_generator.py`:

```python
@pytest.mark.asyncio
async def test_architecture_includes_generated_diagrams(mock_llm_client, tmp_path):
    """Architecture page includes Python-generated diagrams."""
    from oya.repo import Repository
    from oya.generation.architecture import ArchitectureGenerator
    from oya.generation.summaries import SynthesisMap, LayerInfo, ComponentInfo

    repo = Repository(tmp_path)
    generator = ArchitectureGenerator(mock_llm_client, repo)

    synthesis_map = SynthesisMap(
        layers={
            "api": LayerInfo(name="api", purpose="HTTP endpoints", directories=[], files=[]),
        },
        key_components=[
            ComponentInfo(name="Router", file="routes.py", role="Routing", layer="api"),
        ],
        dependency_graph={},
    )

    # Mock LLM to return prose content
    mock_llm_client.generate.return_value = "# Architecture\n\nThis is the architecture."

    page = await generator.generate(
        file_tree="src/\n  api/",
        synthesis_map=synthesis_map,
        file_imports={"routes.py": []},
        symbols=[],
    )

    # Should include mermaid code blocks
    assert "```mermaid" in page.content
    assert "flowchart" in page.content.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_architecture_generator.py -k "generated_diagrams" -v`
Expected: FAIL (architecture generator doesn't accept file_imports/symbols yet)

**Step 3: Update architecture.py**

Modify `backend/src/oya/generation/architecture.py`:

```python
# backend/src/oya/generation/architecture.py
"""Architecture page generator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from oya.generation.mermaid import DiagramGenerator
from oya.generation.mermaid_validator import validate_mermaid
from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_architecture_prompt

if TYPE_CHECKING:
    from oya.generation.summaries import SynthesisMap
    from oya.parsing.models import ParsedSymbol


class ArchitectureGenerator:
    """Generates the repository architecture page.

    The architecture page provides system design documentation
    including component relationships, data flow, and diagrams.

    Supports two modes:
    1. Legacy mode: Uses key_symbols for architecture context
    2. Synthesis mode: Uses SynthesisMap for richer architecture context (preferred)
    """

    def __init__(self, llm_client, repo):
        """Initialize the architecture generator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper for context.
        """
        self.llm_client = llm_client
        self.repo = repo
        self.diagram_generator = DiagramGenerator()

    async def generate(
        self,
        file_tree: str,
        key_symbols: list[dict[str, Any]] | None = None,
        dependencies: list[str] | None = None,
        synthesis_map: SynthesisMap | None = None,
        file_imports: dict[str, list[str]] | None = None,
        symbols: list[ParsedSymbol] | None = None,
    ) -> GeneratedPage:
        """Generate the architecture page.

        Supports two modes:
        1. Legacy mode: Uses key_symbols for architecture context
        2. Synthesis mode: Uses SynthesisMap for richer architecture context

        Args:
            file_tree: String representation of file structure.
            key_symbols: Important symbols across the codebase (legacy mode).
            dependencies: List of project dependencies.
            synthesis_map: SynthesisMap with layer and component info (preferred).
            file_imports: Dict of file paths to their imports (for diagrams).
            symbols: List of ParsedSymbol objects (for class diagrams).

        Returns:
            GeneratedPage with architecture content.
        """
        repo_name = self.repo.path.name

        prompt = get_architecture_prompt(
            repo_name=repo_name,
            file_tree=file_tree,
            key_symbols=key_symbols,
            dependencies=dependencies or [],
            synthesis_map=synthesis_map,
        )

        # Get prose content from LLM
        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Generate and validate diagrams
        diagrams = self.diagram_generator.generate_all(
            synthesis_map=synthesis_map,
            file_imports=file_imports or {},
            symbols=symbols or [],
        )

        validated_diagrams = []
        for name, diagram in diagrams.items():
            result = validate_mermaid(diagram)
            if result.valid:
                validated_diagrams.append((name, diagram))

        # Inject diagrams into content
        content = self._inject_diagrams(content, validated_diagrams)

        word_count = len(content.split())

        return GeneratedPage(
            content=content,
            page_type="architecture",
            path="architecture.md",
            word_count=word_count,
        )

    def _inject_diagrams(
        self, content: str, diagrams: list[tuple[str, str]]
    ) -> str:
        """Inject validated diagrams into the architecture content.

        Adds diagrams at the end of the content in a Diagrams section.

        Args:
            content: Original markdown content.
            diagrams: List of (name, diagram) tuples.

        Returns:
            Content with diagrams appended.
        """
        if not diagrams:
            return content

        diagram_section = "\n\n---\n\n## Generated Diagrams\n\n"

        diagram_titles = {
            "layer": "### Layer Architecture Diagram",
            "dependency": "### File Dependency Graph",
            "class": "### Class Diagram",
        }

        for name, diagram in diagrams:
            title = diagram_titles.get(name, f"### {name.title()} Diagram")
            diagram_section += f"{title}\n\n```mermaid\n{diagram}\n```\n\n"

        return content + diagram_section
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/test_architecture_generator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams
git add backend/src/oya/generation/architecture.py backend/tests/test_architecture_generator.py
git commit -m "feat(architecture): integrate Python-generated Mermaid diagrams"
```

---

## Task 9: Update Orchestrator to Pass Data to Architecture Generator

**Files:**
- Modify: `backend/src/oya/generation/orchestrator.py`

**Step 1: Find and update _run_architecture method**

In `backend/src/oya/generation/orchestrator.py`, find the `_run_architecture` method (around line 700-725) and update to pass `file_imports` and `symbols`:

```python
async def _run_architecture(
    self,
    analysis: dict,
    synthesis_map: SynthesisMap | None,
    progress_callback: ProgressCallback | None = None,
) -> GeneratedPage:
    """Generate the architecture page.

    Args:
        analysis: Analysis results with file_tree, symbols, file_imports.
        synthesis_map: Optional SynthesisMap for richer context.
        progress_callback: Optional progress callback.

    Returns:
        Generated architecture page.
    """
    # Extract dependencies from pyproject.toml or package.json if available
    dependencies = self._extract_dependencies()

    # If we have a synthesis map, use it as primary context
    if synthesis_map is not None:
        return await self.architecture_generator.generate(
            file_tree=analysis["file_tree"],
            dependencies=dependencies,
            synthesis_map=synthesis_map,
            file_imports=analysis.get("file_imports", {}),
            symbols=analysis.get("symbols", []),
        )

    # Legacy mode: use key symbols (convert ParsedSymbol to dict)
    key_symbols = [
        self._symbol_to_dict(s) for s in analysis["symbols"]
        if s.symbol_type.value in ("class", "function", "method")
    ][:50]  # Limit to top 50

    return await self.architecture_generator.generate(
        file_tree=analysis["file_tree"],
        key_symbols=key_symbols,
        dependencies=dependencies,
        file_imports=analysis.get("file_imports", {}),
        symbols=analysis.get("symbols", []),
    )
```

**Step 2: Run full test suite**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/ -q`
Expected: All tests pass

**Step 3: Commit**

```bash
cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams
git add backend/src/oya/generation/orchestrator.py
git commit -m "feat(orchestrator): pass analysis data to architecture generator for diagrams"
```

---

## Task 10: Final Verification

**Step 1: Run full backend test suite**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/backend && source .venv/bin/activate && pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Run frontend tests**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams/frontend && npm run test`
Expected: All tests pass

**Step 3: Review git log**

Run: `cd /Users/poecurt/projects/oya/.worktrees/mermaid-diagrams && git log --oneline -12`
Expected: See all commits from this implementation

**Step 4: Final commit if any uncommitted changes**

```bash
git status
# If any changes: git add . && git commit -m "chore: final cleanup"
```
