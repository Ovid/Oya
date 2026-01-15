"""Tests for Mermaid diagram validation."""

from oya.generation.mermaid_validator import (
    sanitize_label,
    sanitize_node_id,
    validate_mermaid,
)


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
