"""Fallback parser tests for unsupported languages."""

import pytest

from oya.parsing import SymbolType
from oya.parsing.fallback_parser import FallbackParser


@pytest.fixture
def parser():
    """Create fallback parser instance."""
    return FallbackParser()


def test_parser_accepts_any_extension(parser):
    """Fallback parser accepts any file extension."""
    from pathlib import Path

    assert parser.can_parse(Path("test.pl"))  # Perl
    assert parser.can_parse(Path("test.rb"))  # Ruby
    assert parser.can_parse(Path("test.go"))  # Go
    assert parser.can_parse(Path("test.rs"))  # Rust


def test_extracts_function_like_patterns(parser):
    """Extracts function-like patterns from code."""
    code = """
sub greet {
    my $name = shift;
    print "Hello, $name\n";
}

sub helper {
    return 42;
}
"""
    result = parser.parse_string(code, "test.pl")

    assert result.ok
    # Should find something, even if not perfect
    assert len(result.file.symbols) > 0


def test_extracts_class_like_patterns(parser):
    """Extracts class-like patterns from code."""
    code = """
class User
  def initialize(name)
    @name = name
  end

  def greet
    puts "Hello, #{@name}"
  end
end
"""
    result = parser.parse_string(code, "test.rb")

    assert result.ok
    # Should find class and methods
    symbols = result.file.symbols
    assert any("User" in s.name for s in symbols)


def test_counts_lines(parser):
    """Reports correct line count."""
    code = "line1\nline2\nline3\n"
    result = parser.parse_string(code, "test.txt")

    assert result.ok
    assert result.file.line_count == 3


def test_always_succeeds(parser):
    """Fallback parser never fails, even on binary-looking content."""
    code = "random garbage @#$%^&*()"
    result = parser.parse_string(code, "test.unknown")

    assert result.ok  # Should still succeed


def test_extracts_go_functions(parser):
    """Extracts Go function patterns."""
    code = """
func main() {
    fmt.Println("Hello")
}

func helper(x int) int {
    return x * 2
}
"""
    result = parser.parse_string(code, "test.go")

    assert result.ok
    funcs = [s for s in result.file.symbols if s.symbol_type == SymbolType.FUNCTION]
    names = [f.name for f in funcs]
    assert "main" in names or any("main" in n for n in names)
