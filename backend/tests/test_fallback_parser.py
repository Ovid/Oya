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
    """Tests that documentation files produce no symbols.

    Documentation files (markdown, POD, rst, txt) should not have any
    symbols extracted to avoid misinterpreting code examples as actual
    code. This prevents planning documents with code snippets from
    creating false entry points in workflow detection.
    """

    def test_no_symbols_for_pod_files(self, parser):
        """POD files should produce no symbols."""
        content = """=head1 NAME

aliased - Use shorter versions of class names.

=head1 CODE EXAMPLE

sub example_function {
    my $x = shift;
    return $x * 2;
}
"""
        result = parser.parse_string(content, "README.pod")

        assert result.ok
        assert len(result.file.symbols) == 0

    def test_no_symbols_for_markdown_files(self, parser):
        """Markdown files should produce no symbols."""
        content = """# Documentation

This describes the class structure and how to use it.

```python
def main():
    print("Hello")

def execute(task):
    task.run()
```
"""
        result = parser.parse_string(content, "README.md")

        assert result.ok
        assert len(result.file.symbols) == 0

    def test_no_symbols_for_rst_files(self, parser):
        """reStructuredText files should produce no symbols."""
        content = """
Documentation
=============

The class name is extracted from the module path.

.. code-block:: python

   class MyClass:
       def run(self):
           pass
"""
        result = parser.parse_string(content, "docs.rst")

        assert result.ok
        assert len(result.file.symbols) == 0

    def test_no_symbols_for_txt_files(self, parser):
        """Plain text files should produce no symbols."""
        content = """NOTES

This class provides utility functions.
The interface design follows standard patterns.

def main():
    pass
"""
        result = parser.parse_string(content, "notes.txt")

        assert result.ok
        assert len(result.file.symbols) == 0

    def test_no_symbols_for_adoc_files(self, parser):
        """AsciiDoc files should produce no symbols."""
        content = """= Documentation

Some text with code examples.

[source,python]
----
def execute():
    pass
----
"""
        result = parser.parse_string(content, "docs.adoc")

        assert result.ok
        assert len(result.file.symbols) == 0

    def test_no_symbols_for_rdoc_files(self, parser):
        """Ruby documentation files should produce no symbols."""
        content = """= MyClass

This is a Ruby documentation file.

== Methods

=== run

Runs the main process.

  def run
    execute_tasks
  end
"""
        result = parser.parse_string(content, "README.rdoc")

        assert result.ok
        assert len(result.file.symbols) == 0

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

    def test_still_detects_functions_in_code_files(self, parser):
        """Non-documentation files should still detect function patterns."""
        code = """
sub example_function {
    my $x = shift;
    return $x * 2;
}
"""
        result = parser.parse_string(code, "module.pl")

        func_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.FUNCTION]
        func_names = [s.name for s in func_symbols]
        assert "example_function" in func_names

    def test_perl_detects_symbols_in_code_section(self, parser):
        """Perl files detect symbols before __END__ marker."""
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

        # Should find the function (Perl file, not documentation)
        func_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.FUNCTION]
        func_names = [s.name for s in func_symbols]
        assert "greet" in func_names

        # Should NOT find "you" or "name" as classes (they're in POD after __END__)
        class_symbols = [s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS]
        class_names = [s.name for s in class_symbols]
        assert "you" not in class_names
        assert "name" not in class_names

    def test_markdown_with_entry_point_code_examples(self, parser):
        """Markdown with code examples containing entry point names produces no symbols.

        This specifically tests the scenario where planning documents contain
        code examples with function names like 'main', 'execute', 'run' that
        would otherwise be detected as entry points for workflow generation.
        """
        content = """# Implementation Plan

## Database Connection

```python
def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
    return self.conn.execute(sql, params)

def main():
    db = Database()
    db.execute("SELECT 1")
```

## Running the System

The `run` function starts the server:

```python
async def run():
    await server.start()
```
"""
        result = parser.parse_string(content, "2026-01-08-implementation.md")

        assert result.ok
        # No symbols should be extracted - these are just documentation
        assert len(result.file.symbols) == 0

    def test_documentation_files_still_return_metadata(self, parser):
        """Documentation files return valid ParseResult with metadata but no symbols."""
        content = """# README

This is documentation.
Line 2.
Line 3.
"""
        result = parser.parse_string(content, "README.md")

        assert result.ok
        assert result.file is not None
        assert result.file.language == "unknown"
        assert result.file.line_count == 5
        assert len(result.file.symbols) == 0


def test_extract_perl_pod_synopsis():
    """Should extract SYNOPSIS section from Perl POD."""
    code = """package My::Module;

sub do_something {
    my $x = 1;
}

__END__

=head1 NAME

My::Module - Example module

=head1 SYNOPSIS

    use My::Module;

    my $obj = My::Module->new();
    $obj->do_something();

=head1 DESCRIPTION

This module does something.

=cut
"""
    parser = FallbackParser()
    result = parser.parse_string(code, "Module.pm")

    expected = """use My::Module;

my $obj = My::Module->new();
$obj->do_something();"""

    assert result.file.synopsis == expected


def test_extract_perl_pod_synopsis_head2():
    """Should extract SYNOPSIS from =head2 as well."""
    code = """__END__

=head1 NAME

Test

=head2 SYNOPSIS

    use Test;

=cut
"""
    parser = FallbackParser()
    result = parser.parse_string(code, "Test.pm")
    assert result.file.synopsis == "use Test;"


def test_no_synopsis_when_no_pod():
    """Should return None when Perl file has no POD."""
    code = """package My::Module;
sub foo {}
"""
    parser = FallbackParser()
    result = parser.parse_string(code, "Module.pm")
    assert result.file.synopsis is None


def test_empty_synopsis_returns_none():
    """Should return None when SYNOPSIS section is empty."""
    code = """=head1 NAME

Test::Module

=head1 SYNOPSIS

=head1 DESCRIPTION

Some description here.
"""
    parser = FallbackParser()
    result = parser.parse_string(code, "Test.pm")
    assert result.file.synopsis is None
