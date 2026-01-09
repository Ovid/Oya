"""Property-based tests for summary data models.

Feature: bottom-up-generation
"""

from hypothesis import given, settings, strategies as st

# Valid layer values as defined in requirements
VALID_LAYERS = ["api", "domain", "infrastructure", "utility", "config", "test"]


# Strategy for generating valid FileSummary data
@st.composite
def file_summary_strategy(draw):
    """Generate valid FileSummary data."""
    return {
        "file_path": draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip())),
        "purpose": draw(st.text(min_size=1, max_size=500).filter(lambda x: x.strip())),
        "layer": draw(st.sampled_from(VALID_LAYERS)),
        "key_abstractions": draw(st.lists(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()), min_size=0, max_size=10)),
        "internal_deps": draw(st.lists(st.text(min_size=1, max_size=100).filter(lambda x: x.strip()), min_size=0, max_size=10)),
        "external_deps": draw(st.lists(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()), min_size=0, max_size=10)),
    }


class TestFileSummaryCompleteness:
    """Property 1: File_Summary Completeness
    
    For any valid source file processed by the File_Generator, the resulting 
    File_Summary SHALL contain all required fields (purpose, layer, key_abstractions, 
    internal_deps, external_deps) with the layer field being one of the valid values 
    (api, domain, infrastructure, utility, config, test).
    
    Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6
    """

    @given(data=file_summary_strategy())
    @settings(max_examples=100)
    def test_file_summary_has_all_required_fields(self, data):
        """Feature: bottom-up-generation, Property 1: File_Summary Completeness
        
        Any valid FileSummary must have all required fields populated.
        """
        from oya.generation.summaries import FileSummary
        
        summary = FileSummary(
            file_path=data["file_path"],
            purpose=data["purpose"],
            layer=data["layer"],
            key_abstractions=data["key_abstractions"],
            internal_deps=data["internal_deps"],
            external_deps=data["external_deps"],
        )
        
        # All required fields must be present and accessible
        assert summary.file_path is not None
        assert summary.purpose is not None
        assert summary.layer is not None
        assert summary.key_abstractions is not None
        assert summary.internal_deps is not None
        assert summary.external_deps is not None
        
        # Layer must be one of the valid values
        assert summary.layer in VALID_LAYERS

    @given(layer=st.sampled_from(VALID_LAYERS))
    @settings(max_examples=100)
    def test_layer_validation_accepts_valid_layers(self, layer):
        """Feature: bottom-up-generation, Property 1: File_Summary Completeness
        
        Layer field must accept all valid layer values.
        """
        from oya.generation.summaries import FileSummary
        
        summary = FileSummary(
            file_path="test/file.py",
            purpose="Test purpose",
            layer=layer,
            key_abstractions=[],
            internal_deps=[],
            external_deps=[],
        )
        
        assert summary.layer == layer
        assert summary.layer in VALID_LAYERS

    @given(invalid_layer=st.text(min_size=1).filter(lambda x: x not in VALID_LAYERS))
    @settings(max_examples=100)
    def test_layer_validation_rejects_invalid_layers(self, invalid_layer):
        """Feature: bottom-up-generation, Property 1: File_Summary Completeness
        
        Layer field must reject invalid layer values.
        """
        from oya.generation.summaries import FileSummary
        import pytest
        
        with pytest.raises(ValueError):
            FileSummary(
                file_path="test/file.py",
                purpose="Test purpose",
                layer=invalid_layer,
                key_abstractions=[],
                internal_deps=[],
                external_deps=[],
            )


# Strategy for generating valid DirectorySummary data
@st.composite
def directory_summary_strategy(draw):
    """Generate valid DirectorySummary data."""
    return {
        "directory_path": draw(st.text(min_size=1, max_size=100).filter(lambda x: x.strip())),
        "purpose": draw(st.text(min_size=1, max_size=500).filter(lambda x: x.strip())),
        "contains": draw(st.lists(st.text(min_size=1, max_size=100).filter(lambda x: x.strip()), min_size=1, max_size=20)),
        "role_in_system": draw(st.text(min_size=1, max_size=500).filter(lambda x: x.strip())),
    }


class TestDirectorySummaryCompleteness:
    """Property 4: Directory_Summary Completeness
    
    For any directory processed by the Directory_Generator, the resulting 
    Directory_Summary SHALL contain all required fields (purpose, contains, 
    role_in_system) with non-empty values.
    
    Validates: Requirements 2.2, 2.3, 2.4
    """

    @given(data=directory_summary_strategy())
    @settings(max_examples=100)
    def test_directory_summary_has_all_required_fields(self, data):
        """Feature: bottom-up-generation, Property 4: Directory_Summary Completeness
        
        Any valid DirectorySummary must have all required fields populated.
        """
        from oya.generation.summaries import DirectorySummary
        
        summary = DirectorySummary(
            directory_path=data["directory_path"],
            purpose=data["purpose"],
            contains=data["contains"],
            role_in_system=data["role_in_system"],
        )
        
        # All required fields must be present and accessible
        assert summary.directory_path is not None
        assert summary.purpose is not None
        assert summary.contains is not None
        assert summary.role_in_system is not None
        
        # Fields must have non-empty values (as per requirements)
        assert len(summary.directory_path.strip()) > 0
        assert len(summary.purpose.strip()) > 0
        assert len(summary.contains) > 0
        assert len(summary.role_in_system.strip()) > 0

    @given(data=directory_summary_strategy())
    @settings(max_examples=100)
    def test_directory_summary_contains_is_list(self, data):
        """Feature: bottom-up-generation, Property 4: Directory_Summary Completeness
        
        The contains field must be a list of file paths.
        """
        from oya.generation.summaries import DirectorySummary
        
        summary = DirectorySummary(
            directory_path=data["directory_path"],
            purpose=data["purpose"],
            contains=data["contains"],
            role_in_system=data["role_in_system"],
        )
        
        # contains must be a list
        assert isinstance(summary.contains, list)
        # All items in contains must be strings
        for item in summary.contains:
            assert isinstance(item, str)


# Safe alphabet for YAML strings (alphanumeric and basic punctuation, no quotes or backslashes)
YAML_SAFE_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-."


# Strategy for generating valid YAML summary blocks in markdown
@st.composite
def yaml_file_summary_markdown_strategy(draw):
    """Generate markdown content with a valid YAML file_summary block."""
    # Generate valid FileSummary data using YAML-safe characters
    file_path = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.", min_size=1, max_size=50).filter(lambda x: x.strip()))
    purpose = draw(st.text(alphabet=YAML_SAFE_ALPHABET, min_size=1, max_size=100).filter(lambda x: x.strip()))
    layer = draw(st.sampled_from(VALID_LAYERS))
    key_abstractions = draw(st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_", min_size=1, max_size=30).filter(lambda x: x.strip()),
        min_size=0, max_size=5
    ))
    internal_deps = draw(st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.", min_size=1, max_size=50).filter(lambda x: x.strip()),
        min_size=0, max_size=3
    ))
    external_deps = draw(st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=30).filter(lambda x: x.strip()),
        min_size=0, max_size=3
    ))
    
    # Build YAML block
    yaml_lines = [
        "---",
        "file_summary:",
        f'  purpose: "{purpose}"',
        f"  layer: {layer}",
        "  key_abstractions:",
    ]
    for abstraction in key_abstractions:
        yaml_lines.append(f'    - "{abstraction}"')
    if not key_abstractions:
        yaml_lines.append("    []")
    
    yaml_lines.append("  internal_deps:")
    for dep in internal_deps:
        yaml_lines.append(f'    - "{dep}"')
    if not internal_deps:
        yaml_lines.append("    []")
    
    yaml_lines.append("  external_deps:")
    for dep in external_deps:
        yaml_lines.append(f'    - "{dep}"')
    if not external_deps:
        yaml_lines.append("    []")
    
    yaml_lines.append("---")
    yaml_block = "\n".join(yaml_lines)
    
    # Generate markdown content after the YAML block (YAML-safe)
    markdown_content = draw(st.text(alphabet=YAML_SAFE_ALPHABET + "#*[]()!", min_size=1, max_size=200).filter(lambda x: x.strip()))
    
    full_markdown = f"{yaml_block}\n\n{markdown_content}"
    
    return {
        "markdown": full_markdown,
        "expected_summary": {
            "purpose": purpose,
            "layer": layer,
            "key_abstractions": key_abstractions,
            "internal_deps": internal_deps,
            "external_deps": external_deps,
        },
        "expected_clean_markdown": markdown_content,
    }


@st.composite
def yaml_directory_summary_markdown_strategy(draw):
    """Generate markdown content with a valid YAML directory_summary block."""
    # Generate valid DirectorySummary data using YAML-safe characters
    directory_path = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.", min_size=1, max_size=50).filter(lambda x: x.strip()))
    purpose = draw(st.text(alphabet=YAML_SAFE_ALPHABET, min_size=1, max_size=100).filter(lambda x: x.strip()))
    contains = draw(st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.", min_size=1, max_size=50).filter(lambda x: x.strip()),
        min_size=1, max_size=5
    ))
    role_in_system = draw(st.text(alphabet=YAML_SAFE_ALPHABET, min_size=1, max_size=100).filter(lambda x: x.strip()))
    
    # Build YAML block
    yaml_lines = [
        "---",
        "directory_summary:",
        f'  purpose: "{purpose}"',
        "  contains:",
    ]
    for file in contains:
        yaml_lines.append(f'    - "{file}"')
    
    yaml_lines.append(f'  role_in_system: "{role_in_system}"')
    yaml_lines.append("---")
    yaml_block = "\n".join(yaml_lines)
    
    # Generate markdown content after the YAML block (YAML-safe)
    markdown_content = draw(st.text(alphabet=YAML_SAFE_ALPHABET + "#*[]()!", min_size=1, max_size=200).filter(lambda x: x.strip()))
    
    full_markdown = f"{yaml_block}\n\n{markdown_content}"
    
    return {
        "markdown": full_markdown,
        "expected_summary": {
            "purpose": purpose,
            "contains": contains,
            "role_in_system": role_in_system,
        },
        "expected_clean_markdown": markdown_content,
    }


class TestYAMLParsingAndStripping:
    """Property 14: YAML Parsing and Stripping
    
    For any markdown content containing a valid YAML summary block (delimited by `---`),
    the parser SHALL extract the summary data AND return markdown content with the 
    YAML block removed.
    
    Validates: Requirements 8.1, 8.4, 8.5
    """

    @given(data=yaml_file_summary_markdown_strategy())
    @settings(max_examples=100)
    def test_file_summary_yaml_extraction_and_stripping(self, data):
        """Feature: bottom-up-generation, Property 14: YAML Parsing and Stripping
        
        Valid YAML file_summary blocks are extracted and stripped from markdown.
        """
        from oya.generation.summaries import SummaryParser
        
        parser = SummaryParser()
        clean_markdown, summary = parser.parse_file_summary(
            data["markdown"], 
            file_path="test/file.py"
        )
        
        # Summary should have correct values extracted from YAML
        assert summary.purpose == data["expected_summary"]["purpose"]
        assert summary.layer == data["expected_summary"]["layer"]
        assert summary.key_abstractions == data["expected_summary"]["key_abstractions"]
        assert summary.internal_deps == data["expected_summary"]["internal_deps"]
        assert summary.external_deps == data["expected_summary"]["external_deps"]
        
        # Clean markdown should not contain the YAML block
        assert "---" not in clean_markdown or clean_markdown.count("---") == 0
        assert "file_summary:" not in clean_markdown
        
        # Clean markdown should contain the original content (stripped)
        assert clean_markdown.strip() == data["expected_clean_markdown"].strip()

    @given(data=yaml_directory_summary_markdown_strategy())
    @settings(max_examples=100)
    def test_directory_summary_yaml_extraction_and_stripping(self, data):
        """Feature: bottom-up-generation, Property 14: YAML Parsing and Stripping
        
        Valid YAML directory_summary blocks are extracted and stripped from markdown.
        """
        from oya.generation.summaries import SummaryParser
        
        parser = SummaryParser()
        clean_markdown, summary = parser.parse_directory_summary(
            data["markdown"],
            directory_path="test/dir"
        )
        
        # Summary should have correct values extracted from YAML
        assert summary.purpose == data["expected_summary"]["purpose"]
        assert summary.contains == data["expected_summary"]["contains"]
        assert summary.role_in_system == data["expected_summary"]["role_in_system"]
        
        # Clean markdown should not contain the YAML block
        assert "---" not in clean_markdown or clean_markdown.count("---") == 0
        assert "directory_summary:" not in clean_markdown
        
        # Clean markdown should contain the original content (stripped)
        assert clean_markdown.strip() == data["expected_clean_markdown"].strip()


# Strategy for generating malformed YAML content
@st.composite
def malformed_yaml_strategy(draw):
    """Generate various types of malformed YAML content."""
    malformed_type = draw(st.sampled_from([
        "missing_closing_delimiter",
        "invalid_yaml_syntax",
        "missing_summary_key",
        "wrong_summary_type",
        "empty_yaml_block",
        "no_yaml_block",
        "truncated_yaml",
    ]))
    
    if malformed_type == "missing_closing_delimiter":
        # YAML block without closing ---
        return "---\nfile_summary:\n  purpose: test\n  layer: api\n\nSome markdown content"
    
    elif malformed_type == "invalid_yaml_syntax":
        # Invalid YAML syntax (bad indentation, missing colons, etc.)
        return "---\nfile_summary\n  purpose test\n  layer: : api\n---\n\nSome markdown content"
    
    elif malformed_type == "missing_summary_key":
        # Valid YAML but missing file_summary key
        return "---\nother_key:\n  purpose: test\n  layer: api\n---\n\nSome markdown content"
    
    elif malformed_type == "wrong_summary_type":
        # file_summary is not a dict
        return "---\nfile_summary: just a string\n---\n\nSome markdown content"
    
    elif malformed_type == "empty_yaml_block":
        # Empty YAML block
        return "---\n---\n\nSome markdown content"
    
    elif malformed_type == "no_yaml_block":
        # No YAML block at all, just markdown
        markdown = draw(st.text(alphabet=YAML_SAFE_ALPHABET + "#*[]()!", min_size=1, max_size=200).filter(lambda x: x.strip()))
        return markdown
    
    elif malformed_type == "truncated_yaml":
        # Truncated/incomplete YAML
        return "---\nfile_summary:\n  purpose: test\n  layer:"
    
    return "Just plain markdown without any YAML"


class TestFileSummaryFallbackOnParseFailure:
    """Property 2: File_Summary Fallback on Parse Failure
    
    For any malformed or missing YAML summary block in LLM output, the parser 
    SHALL return a fallback File_Summary with purpose="Unknown" and layer="utility", 
    and the system SHALL not raise an exception.
    
    Validates: Requirements 1.7, 8.3
    """

    @given(malformed_content=malformed_yaml_strategy())
    @settings(max_examples=100)
    def test_malformed_yaml_returns_fallback_file_summary(self, malformed_content):
        """Feature: bottom-up-generation, Property 2: File_Summary Fallback on Parse Failure
        
        Malformed YAML returns fallback with purpose="Unknown", layer="utility".
        """
        from oya.generation.summaries import SummaryParser
        
        parser = SummaryParser()
        file_path = "test/malformed_file.py"
        
        # Should not raise an exception
        clean_markdown, summary = parser.parse_file_summary(malformed_content, file_path)
        
        # Summary should be a valid FileSummary with fallback values
        assert summary is not None
        assert summary.file_path == file_path
        assert summary.purpose == "Unknown"
        assert summary.layer == "utility"
        assert summary.key_abstractions == []
        assert summary.internal_deps == []
        assert summary.external_deps == []

    @given(file_path=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.", min_size=1, max_size=100).filter(lambda x: x.strip()))
    @settings(max_examples=100)
    def test_fallback_preserves_file_path(self, file_path):
        """Feature: bottom-up-generation, Property 2: File_Summary Fallback on Parse Failure
        
        Fallback summary preserves the original file_path.
        """
        from oya.generation.summaries import SummaryParser
        
        parser = SummaryParser()
        # Content with no valid YAML
        content = "# Just some markdown\n\nNo YAML here."
        
        clean_markdown, summary = parser.parse_file_summary(content, file_path)
        
        # File path should be preserved in fallback
        assert summary.file_path == file_path
        assert summary.purpose == "Unknown"
        assert summary.layer == "utility"

    @given(
        random_garbage=st.binary(min_size=1, max_size=500).map(
            lambda b: b.decode('utf-8', errors='replace')
        )
    )
    @settings(max_examples=100)
    def test_random_garbage_returns_fallback(self, random_garbage):
        """Feature: bottom-up-generation, Property 2: File_Summary Fallback on Parse Failure
        
        Random garbage input returns fallback without raising exceptions.
        """
        from oya.generation.summaries import SummaryParser
        
        parser = SummaryParser()
        file_path = "test/garbage.py"
        
        # Should not raise an exception even with garbage input
        clean_markdown, summary = parser.parse_file_summary(random_garbage, file_path)
        
        # Should return a valid fallback summary
        assert summary is not None
        assert summary.file_path == file_path
        # Fallback values
        assert summary.purpose == "Unknown"
        assert summary.layer == "utility"



# Strategy for generating malformed YAML content for directory summaries
@st.composite
def malformed_directory_yaml_strategy(draw):
    """Generate various types of malformed YAML content for directory summaries."""
    malformed_type = draw(st.sampled_from([
        "missing_closing_delimiter",
        "invalid_yaml_syntax",
        "missing_summary_key",
        "wrong_summary_type",
        "empty_yaml_block",
        "no_yaml_block",
        "truncated_yaml",
    ]))
    
    if malformed_type == "missing_closing_delimiter":
        # YAML block without closing ---
        return "---\ndirectory_summary:\n  purpose: test\n  contains:\n    - file.py\n\nSome markdown content"
    
    elif malformed_type == "invalid_yaml_syntax":
        # Invalid YAML syntax (bad indentation, missing colons, etc.)
        return "---\ndirectory_summary\n  purpose test\n  contains: : []\n---\n\nSome markdown content"
    
    elif malformed_type == "missing_summary_key":
        # Valid YAML but missing directory_summary key
        return "---\nother_key:\n  purpose: test\n  contains: []\n---\n\nSome markdown content"
    
    elif malformed_type == "wrong_summary_type":
        # directory_summary is not a dict
        return "---\ndirectory_summary: just a string\n---\n\nSome markdown content"
    
    elif malformed_type == "empty_yaml_block":
        # Empty YAML block
        return "---\n---\n\nSome markdown content"
    
    elif malformed_type == "no_yaml_block":
        # No YAML block at all, just markdown
        markdown = draw(st.text(alphabet=YAML_SAFE_ALPHABET + "#*[]()!", min_size=1, max_size=200).filter(lambda x: x.strip()))
        return markdown
    
    elif malformed_type == "truncated_yaml":
        # Truncated/incomplete YAML
        return "---\ndirectory_summary:\n  purpose: test\n  contains:"
    
    return "Just plain markdown without any YAML"


class TestDirectorySummaryFallbackOnParseFailure:
    """Property 5: Directory_Summary Fallback on Parse Failure
    
    For any malformed or missing YAML summary block in directory LLM output, 
    the parser SHALL return a fallback Directory_Summary with purpose="Unknown", 
    and the system SHALL not raise an exception.
    
    Validates: Requirements 2.5
    """

    @given(malformed_content=malformed_directory_yaml_strategy())
    @settings(max_examples=100)
    def test_malformed_yaml_returns_fallback_directory_summary(self, malformed_content):
        """Feature: bottom-up-generation, Property 5: Directory_Summary Fallback on Parse Failure
        
        Malformed YAML returns fallback with purpose="Unknown".
        """
        from oya.generation.summaries import SummaryParser
        
        parser = SummaryParser()
        directory_path = "test/malformed_dir"
        
        # Should not raise an exception
        clean_markdown, summary = parser.parse_directory_summary(malformed_content, directory_path)
        
        # Summary should be a valid DirectorySummary with fallback values
        assert summary is not None
        assert summary.directory_path == directory_path
        assert summary.purpose == "Unknown"
        assert summary.contains == []
        assert summary.role_in_system == ""

    @given(directory_path=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.", min_size=1, max_size=100).filter(lambda x: x.strip()))
    @settings(max_examples=100)
    def test_fallback_preserves_directory_path(self, directory_path):
        """Feature: bottom-up-generation, Property 5: Directory_Summary Fallback on Parse Failure
        
        Fallback summary preserves the original directory_path.
        """
        from oya.generation.summaries import SummaryParser
        
        parser = SummaryParser()
        # Content with no valid YAML
        content = "# Just some markdown\n\nNo YAML here."
        
        clean_markdown, summary = parser.parse_directory_summary(content, directory_path)
        
        # Directory path should be preserved in fallback
        assert summary.directory_path == directory_path
        assert summary.purpose == "Unknown"

    @given(
        random_garbage=st.binary(min_size=1, max_size=500).map(
            lambda b: b.decode('utf-8', errors='replace')
        )
    )
    @settings(max_examples=100)
    def test_random_garbage_returns_fallback_directory(self, random_garbage):
        """Feature: bottom-up-generation, Property 5: Directory_Summary Fallback on Parse Failure
        
        Random garbage input returns fallback without raising exceptions.
        """
        from oya.generation.summaries import SummaryParser
        
        parser = SummaryParser()
        directory_path = "test/garbage_dir"
        
        # Should not raise an exception even with garbage input
        clean_markdown, summary = parser.parse_directory_summary(random_garbage, directory_path)
        
        # Should return a valid fallback summary
        assert summary is not None
        assert summary.directory_path == directory_path
        # Fallback values
        assert summary.purpose == "Unknown"

