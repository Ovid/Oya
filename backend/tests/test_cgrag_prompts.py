"""Tests for CGRAG prompt templates."""


def test_cgrag_prompt_has_answer_section():
    """CGRAG prompt template includes <answer> section marker."""
    from oya.generation.prompts import CGRAG_QA_TEMPLATE

    assert "<answer>" in CGRAG_QA_TEMPLATE
    assert "</answer>" in CGRAG_QA_TEMPLATE


def test_cgrag_prompt_has_missing_section():
    """CGRAG prompt template includes <missing> section marker."""
    from oya.generation.prompts import CGRAG_QA_TEMPLATE

    assert "<missing>" in CGRAG_QA_TEMPLATE
    assert "</missing>" in CGRAG_QA_TEMPLATE


def test_cgrag_prompt_has_placeholders():
    """CGRAG prompt template has required placeholders."""
    from oya.generation.prompts import CGRAG_QA_TEMPLATE

    assert "{question}" in CGRAG_QA_TEMPLATE
    assert "{context}" in CGRAG_QA_TEMPLATE


def test_format_cgrag_prompt():
    """Format function produces valid prompt string."""
    from oya.generation.prompts import format_cgrag_prompt

    result = format_cgrag_prompt(
        question="How does auth work?",
        context="Some context here",
    )

    assert "How does auth work?" in result
    assert "Some context here" in result
    assert "<answer>" in result
    assert "<missing>" in result
