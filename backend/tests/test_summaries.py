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
