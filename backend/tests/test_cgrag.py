"""Tests for CGRAG core functionality."""


class TestParseGaps:
    """Tests for parse_gaps function."""

    def test_parse_gaps_none(self):
        """NONE in response returns empty list."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by...

MISSING (or "NONE" if nothing needed):
NONE"""

        gaps = parse_gaps(response)

        assert gaps == []

    def test_parse_gaps_single(self):
        """Single gap is parsed correctly."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by...

MISSING (or "NONE" if nothing needed):
- verify_token in auth/verify.py"""

        gaps = parse_gaps(response)

        assert len(gaps) == 1
        assert "verify_token" in gaps[0]

    def test_parse_gaps_multiple(self):
        """Multiple gaps are parsed correctly."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by...

MISSING (or "NONE" if nothing needed):
- verify_token in auth/verify.py
- UserModel in models/user.py
- the database connection handler"""

        gaps = parse_gaps(response)

        assert len(gaps) == 3
        assert "verify_token" in gaps[0]
        assert "UserModel" in gaps[1]
        assert "database connection" in gaps[2]

    def test_parse_gaps_no_section(self):
        """Missing MISSING section returns empty list."""
        from oya.qa.cgrag import parse_gaps

        response = """ANSWER:
The auth system works by calling various functions."""

        gaps = parse_gaps(response)

        assert gaps == []

    def test_parse_answer(self):
        """Answer is extracted correctly."""
        from oya.qa.cgrag import parse_answer

        response = """ANSWER:
The auth system works by verifying tokens
and checking user permissions.

MISSING (or "NONE" if nothing needed):
NONE"""

        answer = parse_answer(response)

        assert "auth system works" in answer
        assert "verifying tokens" in answer
        assert "MISSING" not in answer
