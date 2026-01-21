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


class TestDocumentationFileFiltering:
    """Tests that documentation files skip class detection.

    English prose like "class you specify" in POD/markdown should not
    be misinterpreted as class declarations.
    """

    def test_skips_class_detection_for_pod_files(self, parser):
        """POD files should not have class patterns matched."""
        content = """=head1 NAME

aliased - Use shorter versions of class names.

=head1 DESCRIPTION

It loads the class you specify and exports into your namespace
a subroutine that returns the class name.
"""
        result = parser.parse_string(content, "README.pod")

        # Should not find "you" or "name" as classes
        class_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS]
        class_names = [s.name for s in class_symbols]
        assert "you" not in class_names
        assert "name" not in class_names

    def test_skips_class_detection_for_markdown_files(self, parser):
        """Markdown files should not have class patterns matched."""
        content = """# Documentation

This describes the class structure and how to use it.

You can create a new class instance by calling the constructor.
"""
        result = parser.parse_string(content, "README.md")

        # Should not find "structure" or "instance" as classes
        class_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS]
        assert len(class_symbols) == 0

    def test_skips_class_detection_for_rst_files(self, parser):
        """reStructuredText files should not have class patterns matched."""
        content = """
Documentation
=============

The class name is extracted from the module path.
"""
        result = parser.parse_string(content, "docs.rst")

        class_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS]
        class_names = [s.name for s in class_symbols]
        assert "name" not in class_names

    def test_skips_class_detection_for_txt_files(self, parser):
        """Plain text files should not have class patterns matched."""
        content = """NOTES

This class provides utility functions.
The interface design follows standard patterns.
"""
        result = parser.parse_string(content, "notes.txt")

        class_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS]
        assert len(class_symbols) == 0

    def test_still_detects_classes_in_code_files(self, parser):
        """Non-documentation files should still detect class patterns."""
        code = """
class User
  def initialize
  end
end
"""
        result = parser.parse_string(code, "user.rb")

        class_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS]
        class_names = [s.name for s in class_symbols]
        assert "User" in class_names

    def test_still_detects_functions_in_documentation_files(self, parser):
        """Documentation files should still detect function patterns if present."""
        content = """=head1 CODE EXAMPLE

sub example_function {
    my $x = shift;
    return $x * 2;
}
"""
        result = parser.parse_string(content, "example.pod")

        # Should still find functions
        func_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.FUNCTION]
        func_names = [s.name for s in func_symbols]
        assert "example_function" in func_names

    def test_perl_skips_classes_in_pod_after_end_marker(self, parser):
        """Perl files skip class detection in POD after __END__."""
        content = """use strict;
package MyModule;

sub greet {
    print "Hello\\n";
}

1;
__END__

=head1 DESCRIPTION

It loads the class you specify and exports the class name.
"""
        result = parser.parse_string(content, "module.pm")

        # Should find the function
        func_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.FUNCTION]
        func_names = [s.name for s in func_symbols]
        assert "greet" in func_names

        # Should NOT find "you" or "name" as classes (they're in POD after __END__)
        class_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS]
        class_names = [s.name for s in class_symbols]
        assert "you" not in class_names
        assert "name" not in class_names
