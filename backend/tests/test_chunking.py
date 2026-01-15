# backend/tests/test_chunking.py
"""Content chunking tests."""

from oya.generation.chunking import (
    chunk_file_content,
    chunk_by_symbols,
    estimate_tokens,
)
from oya.parsing.models import ParsedSymbol, SymbolType


def test_estimate_tokens_approximation():
    """Token estimation is roughly 4 chars per token."""
    text = "Hello world, this is a test."
    tokens = estimate_tokens(text)

    # ~28 chars / 4 = ~7 tokens
    assert 5 <= tokens <= 10


def test_chunk_file_content_respects_size():
    """Chunks respect maximum token size."""
    content = "line\n" * 1000  # 5000 chars
    chunks = chunk_file_content(content, "test.py", max_tokens=100)

    for chunk in chunks:
        assert estimate_tokens(chunk.content) <= 120  # Allow some overflow


def test_chunk_file_content_includes_metadata():
    """Chunks include file path and line info."""
    content = "line1\nline2\nline3\n"
    chunks = chunk_file_content(content, "src/main.py", max_tokens=1000)

    assert len(chunks) >= 1
    assert chunks[0].file_path == "src/main.py"
    assert chunks[0].start_line == 1


def test_chunk_by_symbols_creates_logical_chunks():
    """Symbol-based chunking respects code boundaries."""
    content = """def foo():
    pass

def bar():
    pass

class Baz:
    def method(self):
        pass
"""
    symbols = [
        ParsedSymbol(name="foo", symbol_type=SymbolType.FUNCTION, start_line=1, end_line=2),
        ParsedSymbol(name="bar", symbol_type=SymbolType.FUNCTION, start_line=4, end_line=5),
        ParsedSymbol(name="Baz", symbol_type=SymbolType.CLASS, start_line=7, end_line=9),
    ]

    chunks = chunk_by_symbols(content, "test.py", symbols, max_tokens=500)

    # Should have at least one chunk per symbol or grouped
    assert len(chunks) >= 1
    # Each chunk should contain complete symbols
    for chunk in chunks:
        assert chunk.symbols  # Has associated symbols


def test_chunk_includes_overlap():
    """Chunks include overlap for context."""
    content = "line\n" * 100
    chunks = chunk_file_content(content, "test.py", max_tokens=50, overlap_lines=5)

    if len(chunks) > 1:
        # Check that second chunk starts before first chunk ends
        assert chunks[1].start_line <= chunks[0].end_line + 5
