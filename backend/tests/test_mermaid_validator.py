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
