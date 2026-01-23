"""Tests for Q&A response parsing utilities."""

from oya.qa.cgrag import parse_answer


class TestParseAnswer:
    """Tests for parse_answer function."""

    def test_extracts_answer_from_tags(self):
        """Basic extraction of answer from XML tags."""
        response = "<answer>This is the answer.</answer><citations>[]</citations>"
        assert parse_answer(response) == "This is the answer."

    def test_handles_whitespace_in_tags(self):
        """Whitespace inside tags is preserved but outer whitespace trimmed."""
        response = "<answer>\n  Multiline\n  answer\n</answer>"
        assert parse_answer(response) == "Multiline\n  answer"

    def test_handles_missing_tags_returns_full_response(self):
        """When no tags present, returns the full response."""
        response = "Just plain text without tags"
        assert parse_answer(response) == "Just plain text without tags"

    def test_case_insensitive_tags(self):
        """Tag matching is case insensitive."""
        response = "<ANSWER>Works</ANSWER>"
        assert parse_answer(response) == "Works"

    def test_extracts_from_response_with_citations(self):
        """Extracts answer even when citations block follows."""
        response = """<answer>
The main function initializes the app.
</answer>

<citations>
[{"path": "main.py", "relevant_text": "def main()"}]
</citations>"""
        result = parse_answer(response)
        assert "main function initializes" in result
        assert "<citations>" not in result

    def test_extracts_from_response_with_missing_block(self):
        """Extracts answer when CGRAG missing block follows."""
        response = """<answer>
Authentication uses JWT tokens.
</answer>

<missing>
NONE
</missing>"""
        result = parse_answer(response)
        assert "JWT tokens" in result
        assert "<missing>" not in result
