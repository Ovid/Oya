"""Tests for graph-augmented Q&A prompt."""


def test_graph_qa_prompt_includes_mermaid():
    """Prompt template includes mermaid diagram placeholder."""
    from oya.generation.prompts import GRAPH_QA_CONTEXT_TEMPLATE

    assert "{mermaid_diagram}" in GRAPH_QA_CONTEXT_TEMPLATE


def test_graph_qa_prompt_includes_code():
    """Prompt template includes code snippets placeholder."""
    from oya.generation.prompts import GRAPH_QA_CONTEXT_TEMPLATE

    assert "{code_snippets}" in GRAPH_QA_CONTEXT_TEMPLATE


def test_format_graph_qa_context():
    """Format function produces valid context string."""
    from oya.generation.prompts import format_graph_qa_context

    mermaid = "flowchart TD\n    A --> B"
    code = "### a.py::func (lines 1-10)\n> Does something"

    result = format_graph_qa_context(mermaid, code)

    assert "flowchart TD" in result
    assert "a.py::func" in result
    assert "Code Relationships" in result
