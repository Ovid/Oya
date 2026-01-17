"""Tests for graph-aware architecture generation."""

import networkx as nx
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def sample_graph():
    """Create a sample code graph."""
    G = nx.DiGraph()
    G.add_node("api/routes.py::handle", name="handle", type="function",
               file_path="api/routes.py", line_start=10, line_end=30,
               docstring="Handle incoming requests")
    G.add_node("db/queries.py::get_user", name="get_user", type="function",
               file_path="db/queries.py", line_start=5, line_end=20,
               docstring="Fetch user from database")
    G.add_node("llm/client.py::generate", name="generate", type="function",
               file_path="llm/client.py", line_start=1, line_end=50,
               docstring="Generate LLM response")
    G.add_edge("api/routes.py::handle", "db/queries.py::get_user",
               type="calls", confidence=0.9, line=15)
    G.add_edge("api/routes.py::handle", "llm/client.py::generate",
               type="calls", confidence=0.85, line=20)
    return G


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client."""
    client = AsyncMock()
    client.generate.return_value = """# Architecture

## Overview

This system has three main components...

## Components

The **api** component handles HTTP requests...
"""
    return client


@pytest.mark.asyncio
async def test_graph_architecture_generator_produces_page(sample_graph, mock_llm_client):
    """GraphArchitectureGenerator produces a valid architecture page."""
    from oya.generation.graph_architecture import GraphArchitectureGenerator

    generator = GraphArchitectureGenerator(mock_llm_client)

    page = await generator.generate(
        repo_name="my-project",
        graph=sample_graph,
        component_summaries={"api": "HTTP endpoints", "db": "Database", "llm": "LLM client"},
    )

    assert page.page_type == "architecture"
    assert page.path == "architecture.md"
    assert "Architecture" in page.content
    # Should contain graph-derived Mermaid diagrams
    assert "```mermaid" in page.content
    mock_llm_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_graph_architecture_generator_filters_test_code(mock_llm_client):
    """GraphArchitectureGenerator excludes test files from diagrams."""
    from oya.generation.graph_architecture import GraphArchitectureGenerator

    G = nx.DiGraph()
    G.add_node("api/routes.py::handle", file_path="api/routes.py")
    G.add_node("tests/test_routes.py::test_handle", file_path="tests/test_routes.py")
    G.add_edge("tests/test_routes.py::test_handle", "api/routes.py::handle",
               type="calls", confidence=0.9, line=5)

    generator = GraphArchitectureGenerator(mock_llm_client)

    page = await generator.generate(
        repo_name="my-project",
        graph=G,
        component_summaries={},
    )

    # Should not include test files in diagrams
    assert "test_routes" not in page.content
    assert "test_handle" not in page.content
