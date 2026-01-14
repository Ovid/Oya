"""Property-based tests for summary data models.

Feature: bottom-up-generation
"""

import logging

from hypothesis import given, settings, strategies as st, HealthCheck

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



# Strategy for generating valid LayerInfo data
@st.composite
def layer_info_strategy(draw):
    """Generate valid LayerInfo data."""
    return {
        "name": draw(st.sampled_from(VALID_LAYERS)),
        "purpose": draw(st.text(alphabet=YAML_SAFE_ALPHABET, min_size=1, max_size=200).filter(lambda x: x.strip())),
        "directories": draw(st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.", min_size=1, max_size=50).filter(lambda x: x.strip()),
            min_size=0, max_size=5
        )),
        "files": draw(st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.", min_size=1, max_size=50).filter(lambda x: x.strip()),
            min_size=0, max_size=10
        )),
    }


# Strategy for generating valid ComponentInfo data
@st.composite
def component_info_strategy(draw):
    """Generate valid ComponentInfo data."""
    return {
        "name": draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_", min_size=1, max_size=50).filter(lambda x: x.strip())),
        "file": draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.", min_size=1, max_size=50).filter(lambda x: x.strip())),
        "role": draw(st.text(alphabet=YAML_SAFE_ALPHABET, min_size=1, max_size=200).filter(lambda x: x.strip())),
        "layer": draw(st.sampled_from(VALID_LAYERS)),
    }


# Strategy for generating valid SynthesisMap data
@st.composite
def synthesis_map_strategy(draw):
    """Generate valid SynthesisMap data."""
    # Generate layers dict with 1-6 layers
    num_layers = draw(st.integers(min_value=1, max_value=6))
    selected_layers = draw(st.permutations(VALID_LAYERS).map(lambda x: list(x)[:num_layers]))
    
    layers = {}
    for layer_name in selected_layers:
        layer_data = draw(layer_info_strategy())
        layer_data["name"] = layer_name  # Ensure name matches key
        layers[layer_name] = layer_data
    
    # Generate key_components list
    key_components = draw(st.lists(component_info_strategy(), min_size=0, max_size=10))
    
    # Generate dependency_graph (layer -> list of dependent layers)
    dependency_graph = {}
    for layer_name in selected_layers:
        # Each layer can depend on 0-3 other layers
        possible_deps = [layer for layer in selected_layers if layer != layer_name]
        num_deps = draw(st.integers(min_value=0, max_value=min(3, len(possible_deps))))
        if num_deps > 0 and possible_deps:
            deps = draw(st.permutations(possible_deps).map(lambda x: list(x)[:num_deps]))
            dependency_graph[layer_name] = deps
        else:
            dependency_graph[layer_name] = []
    
    # Generate project_summary
    project_summary = draw(st.text(alphabet=YAML_SAFE_ALPHABET, min_size=1, max_size=500).filter(lambda x: x.strip()))
    
    return {
        "layers": layers,
        "key_components": key_components,
        "dependency_graph": dependency_graph,
        "project_summary": project_summary,
    }


class TestSynthesisMapJSONRoundTrip:
    """Property 8: Synthesis_Map JSON Round-Trip
    
    For any valid Synthesis_Map, serializing to JSON and deserializing back 
    SHALL produce an equivalent Synthesis_Map object.
    
    Validates: Requirements 3.5
    """

    @given(data=synthesis_map_strategy())
    @settings(max_examples=100)
    def test_synthesis_map_json_round_trip(self, data):
        """Feature: bottom-up-generation, Property 8: Synthesis_Map JSON Round-Trip
        
        Serializing and deserializing a SynthesisMap produces an equivalent object.
        """
        from oya.generation.summaries import SynthesisMap, LayerInfo, ComponentInfo
        
        # Build the SynthesisMap from generated data
        layers = {
            name: LayerInfo(
                name=layer_data["name"],
                purpose=layer_data["purpose"],
                directories=layer_data["directories"],
                files=layer_data["files"],
            )
            for name, layer_data in data["layers"].items()
        }
        
        key_components = [
            ComponentInfo(
                name=comp["name"],
                file=comp["file"],
                role=comp["role"],
                layer=comp["layer"],
            )
            for comp in data["key_components"]
        ]
        
        original = SynthesisMap(
            layers=layers,
            key_components=key_components,
            dependency_graph=data["dependency_graph"],
            project_summary=data["project_summary"],
        )
        
        # Serialize to JSON
        json_str = original.to_json()
        
        # Deserialize back
        restored = SynthesisMap.from_json(json_str)
        
        # Verify equivalence
        assert restored.project_summary == original.project_summary
        assert restored.dependency_graph == original.dependency_graph
        
        # Verify layers
        assert set(restored.layers.keys()) == set(original.layers.keys())
        for layer_name, original_layer in original.layers.items():
            restored_layer = restored.layers[layer_name]
            assert restored_layer.name == original_layer.name
            assert restored_layer.purpose == original_layer.purpose
            assert restored_layer.directories == original_layer.directories
            assert restored_layer.files == original_layer.files
        
        # Verify key_components
        assert len(restored.key_components) == len(original.key_components)
        for orig_comp, rest_comp in zip(original.key_components, restored.key_components):
            assert rest_comp.name == orig_comp.name
            assert rest_comp.file == orig_comp.file
            assert rest_comp.role == orig_comp.role
            assert rest_comp.layer == orig_comp.layer

    @given(data=synthesis_map_strategy())
    @settings(max_examples=100)
    def test_synthesis_map_to_json_produces_valid_json(self, data):
        """Feature: bottom-up-generation, Property 8: Synthesis_Map JSON Round-Trip
        
        to_json() produces valid JSON that can be parsed.
        """
        import json
        from oya.generation.summaries import SynthesisMap, LayerInfo, ComponentInfo
        
        # Build the SynthesisMap from generated data
        layers = {
            name: LayerInfo(
                name=layer_data["name"],
                purpose=layer_data["purpose"],
                directories=layer_data["directories"],
                files=layer_data["files"],
            )
            for name, layer_data in data["layers"].items()
        }
        
        key_components = [
            ComponentInfo(
                name=comp["name"],
                file=comp["file"],
                role=comp["role"],
                layer=comp["layer"],
            )
            for comp in data["key_components"]
        ]
        
        synthesis_map = SynthesisMap(
            layers=layers,
            key_components=key_components,
            dependency_graph=data["dependency_graph"],
            project_summary=data["project_summary"],
        )
        
        # to_json() should produce valid JSON
        json_str = synthesis_map.to_json()
        
        # Should be parseable as JSON
        parsed = json.loads(json_str)
        
        # Should have expected top-level keys
        assert "layers" in parsed
        assert "key_components" in parsed
        assert "dependency_graph" in parsed
        assert "project_summary" in parsed


class TestFileSummaryPersistenceRoundTrip:
    """Property 3: File_Summary Persistence Round-Trip
    
    For any File_Summary generated and persisted to the database, querying the 
    database for that file's metadata and deserializing SHALL produce an 
    equivalent File_Summary object.
    
    Validates: Requirements 1.8
    """

    @given(data=file_summary_strategy())
    @settings(max_examples=100)
    def test_file_summary_dict_round_trip(self, data):
        """Feature: bottom-up-generation, Property 3: File_Summary Persistence Round-Trip
        
        Serializing a FileSummary to dict and deserializing produces equivalent object.
        """
        from oya.generation.summaries import FileSummary
        
        # Create original FileSummary
        original = FileSummary(
            file_path=data["file_path"],
            purpose=data["purpose"],
            layer=data["layer"],
            key_abstractions=data["key_abstractions"],
            internal_deps=data["internal_deps"],
            external_deps=data["external_deps"],
        )
        
        # Serialize to dict (for JSON storage in metadata column)
        serialized = original.to_dict()
        
        # Deserialize back
        restored = FileSummary.from_dict(serialized)
        
        # Verify equivalence
        assert restored.file_path == original.file_path
        assert restored.purpose == original.purpose
        assert restored.layer == original.layer
        assert restored.key_abstractions == original.key_abstractions
        assert restored.internal_deps == original.internal_deps
        assert restored.external_deps == original.external_deps

    @given(data=file_summary_strategy())
    @settings(max_examples=100)
    def test_file_summary_json_round_trip(self, data):
        """Feature: bottom-up-generation, Property 3: File_Summary Persistence Round-Trip
        
        Serializing a FileSummary to JSON and deserializing produces equivalent object.
        """
        import json
        from oya.generation.summaries import FileSummary
        
        # Create original FileSummary
        original = FileSummary(
            file_path=data["file_path"],
            purpose=data["purpose"],
            layer=data["layer"],
            key_abstractions=data["key_abstractions"],
            internal_deps=data["internal_deps"],
            external_deps=data["external_deps"],
        )
        
        # Serialize to dict, then to JSON (simulating database storage)
        serialized_dict = original.to_dict()
        json_str = json.dumps(serialized_dict)
        
        # Deserialize from JSON back to dict, then to FileSummary
        restored_dict = json.loads(json_str)
        restored = FileSummary.from_dict(restored_dict)
        
        # Verify equivalence
        assert restored.file_path == original.file_path
        assert restored.purpose == original.purpose
        assert restored.layer == original.layer
        assert restored.key_abstractions == original.key_abstractions
        assert restored.internal_deps == original.internal_deps
        assert restored.external_deps == original.external_deps

    @given(data=file_summary_strategy())
    @settings(max_examples=100)
    def test_file_summary_to_dict_produces_valid_dict(self, data):
        """Feature: bottom-up-generation, Property 3: File_Summary Persistence Round-Trip
        
        to_dict() produces a dict with all required keys.
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
        
        result = summary.to_dict()
        
        # Should be a dict with all required keys
        assert isinstance(result, dict)
        assert "file_path" in result
        assert "purpose" in result
        assert "layer" in result
        assert "key_abstractions" in result
        assert "internal_deps" in result
        assert "external_deps" in result
        
        # Values should match
        assert result["file_path"] == data["file_path"]
        assert result["purpose"] == data["purpose"]
        assert result["layer"] == data["layer"]
        assert result["key_abstractions"] == data["key_abstractions"]
        assert result["internal_deps"] == data["internal_deps"]
        assert result["external_deps"] == data["external_deps"]



class TestDirectorySummaryPersistenceRoundTrip:
    """Property 6: Directory_Summary Persistence Round-Trip
    
    For any Directory_Summary generated and persisted to the database, querying 
    the database for that directory's metadata and deserializing SHALL produce 
    an equivalent Directory_Summary object.
    
    Validates: Requirements 2.7
    """

    @given(data=directory_summary_strategy())
    @settings(max_examples=100)
    def test_directory_summary_dict_round_trip(self, data):
        """Feature: bottom-up-generation, Property 6: Directory_Summary Persistence Round-Trip
        
        Serializing a DirectorySummary to dict and deserializing produces equivalent object.
        """
        from oya.generation.summaries import DirectorySummary
        
        # Create original DirectorySummary
        original = DirectorySummary(
            directory_path=data["directory_path"],
            purpose=data["purpose"],
            contains=data["contains"],
            role_in_system=data["role_in_system"],
        )
        
        # Serialize to dict (for JSON storage in metadata column)
        serialized = original.to_dict()
        
        # Deserialize back
        restored = DirectorySummary.from_dict(serialized)
        
        # Verify equivalence
        assert restored.directory_path == original.directory_path
        assert restored.purpose == original.purpose
        assert restored.contains == original.contains
        assert restored.role_in_system == original.role_in_system

    @given(data=directory_summary_strategy())
    @settings(max_examples=100)
    def test_directory_summary_json_round_trip(self, data):
        """Feature: bottom-up-generation, Property 6: Directory_Summary Persistence Round-Trip
        
        Serializing a DirectorySummary to JSON and deserializing produces equivalent object.
        """
        import json
        from oya.generation.summaries import DirectorySummary
        
        # Create original DirectorySummary
        original = DirectorySummary(
            directory_path=data["directory_path"],
            purpose=data["purpose"],
            contains=data["contains"],
            role_in_system=data["role_in_system"],
        )
        
        # Serialize to dict, then to JSON (simulating database storage)
        serialized_dict = original.to_dict()
        json_str = json.dumps(serialized_dict)
        
        # Deserialize from JSON back to dict, then to DirectorySummary
        restored_dict = json.loads(json_str)
        restored = DirectorySummary.from_dict(restored_dict)
        
        # Verify equivalence
        assert restored.directory_path == original.directory_path
        assert restored.purpose == original.purpose
        assert restored.contains == original.contains
        assert restored.role_in_system == original.role_in_system

    @given(data=directory_summary_strategy())
    @settings(max_examples=100)
    def test_directory_summary_to_dict_produces_valid_dict(self, data):
        """Feature: bottom-up-generation, Property 6: Directory_Summary Persistence Round-Trip
        
        to_dict() produces a dict with all required keys.
        """
        from oya.generation.summaries import DirectorySummary
        
        summary = DirectorySummary(
            directory_path=data["directory_path"],
            purpose=data["purpose"],
            contains=data["contains"],
            role_in_system=data["role_in_system"],
        )
        
        result = summary.to_dict()
        
        # Should be a dict with all required keys
        assert isinstance(result, dict)
        assert "directory_path" in result
        assert "purpose" in result
        assert "contains" in result
        assert "role_in_system" in result
        
        # Values should match
        assert result["directory_path"] == data["directory_path"]
        assert result["purpose"] == data["purpose"]
        assert result["contains"] == data["contains"]
        assert result["role_in_system"] == data["role_in_system"]


# Strategy for generating a list of FileSummaries with various layers
@st.composite
def file_summaries_for_layer_grouping_strategy(draw):
    """Generate a list of FileSummaries for testing layer grouping.
    
    Ensures we have at least one file and files are distributed across layers.
    """
    # Generate between 1 and 20 file summaries
    num_files = draw(st.integers(min_value=1, max_value=20))
    
    file_summaries = []
    for i in range(num_files):
        # Generate path components separately to ensure valid paths
        dir_name = draw(st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
            min_size=1,
            max_size=20
        ).filter(lambda x: x.strip()))
        file_name = draw(st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
            min_size=1,
            max_size=20
        ).filter(lambda x: x.strip()))
        
        # Build a valid file path with guaranteed "/" and unique suffix
        file_path = f"{dir_name}/{file_name}_{i}.py"
        
        purpose = draw(st.text(alphabet=YAML_SAFE_ALPHABET, min_size=1, max_size=100).filter(lambda x: x.strip()))
        layer = draw(st.sampled_from(VALID_LAYERS))
        key_abstractions = draw(st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_", min_size=1, max_size=30).filter(lambda x: x.strip()),
            min_size=0, max_size=3
        ))
        
        file_summaries.append({
            "file_path": file_path,
            "purpose": purpose,
            "layer": layer,
            "key_abstractions": key_abstractions,
            "internal_deps": [],
            "external_deps": [],
        })
    
    return file_summaries


class TestSynthesisMapLayerGroupingCompleteness:
    """Property 7: Synthesis_Map Layer Grouping Completeness
    
    For any set of File_Summaries with layer classifications, the resulting 
    Synthesis_Map SHALL contain all files grouped under their respective layers, 
    with no file appearing in multiple layers and no file missing from all layers.
    
    Validates: Requirements 3.2
    """

    @given(file_summaries_data=file_summaries_for_layer_grouping_strategy())
    @settings(max_examples=100)
    def test_all_files_appear_in_exactly_one_layer(self, file_summaries_data):
        """Feature: bottom-up-generation, Property 7: Synthesis_Map Layer Grouping Completeness
        
        All files appear in exactly one layer - no duplicates, no missing files.
        """
        from oya.generation.summaries import FileSummary
        from oya.generation.synthesis import SynthesisGenerator
        
        # Create FileSummary objects from generated data
        file_summaries = [
            FileSummary(
                file_path=data["file_path"],
                purpose=data["purpose"],
                layer=data["layer"],
                key_abstractions=data["key_abstractions"],
                internal_deps=data["internal_deps"],
                external_deps=data["external_deps"],
            )
            for data in file_summaries_data
        ]
        
        # Create SynthesisGenerator and group files by layer
        generator = SynthesisGenerator(llm_client=None)
        synthesis_map = generator.group_files_by_layer(file_summaries)
        
        # Collect all file paths from all layers
        all_files_in_layers = []
        for layer_name, layer_info in synthesis_map.layers.items():
            all_files_in_layers.extend(layer_info.files)
        
        # Get original file paths
        original_file_paths = [fs.file_path for fs in file_summaries]
        
        # Property 1: No file should be missing from all layers
        # Every original file should appear in some layer
        for file_path in original_file_paths:
            assert file_path in all_files_in_layers, f"File {file_path} is missing from all layers"
        
        # Property 2: No file should appear in multiple layers
        # The count of files in layers should equal the count of unique files
        assert len(all_files_in_layers) == len(set(all_files_in_layers)), \
            "Some files appear in multiple layers"
        
        # Property 3: Total files in layers should equal original file count
        assert len(all_files_in_layers) == len(original_file_paths), \
            f"Expected {len(original_file_paths)} files, found {len(all_files_in_layers)} in layers"

    @given(file_summaries_data=file_summaries_for_layer_grouping_strategy())
    @settings(max_examples=100)
    def test_files_grouped_under_correct_layer(self, file_summaries_data):
        """Feature: bottom-up-generation, Property 7: Synthesis_Map Layer Grouping Completeness
        
        Each file appears under its correct layer classification.
        """
        from oya.generation.summaries import FileSummary
        from oya.generation.synthesis import SynthesisGenerator
        
        # Create FileSummary objects from generated data
        file_summaries = [
            FileSummary(
                file_path=data["file_path"],
                purpose=data["purpose"],
                layer=data["layer"],
                key_abstractions=data["key_abstractions"],
                internal_deps=data["internal_deps"],
                external_deps=data["external_deps"],
            )
            for data in file_summaries_data
        ]
        
        # Create SynthesisGenerator and group files by layer
        generator = SynthesisGenerator(llm_client=None)
        synthesis_map = generator.group_files_by_layer(file_summaries)
        
        # For each file summary, verify it's in the correct layer
        for fs in file_summaries:
            expected_layer = fs.layer
            
            # The file should be in the layer matching its classification
            if expected_layer in synthesis_map.layers:
                assert fs.file_path in synthesis_map.layers[expected_layer].files, \
                    f"File {fs.file_path} with layer {expected_layer} not found in that layer"
            else:
                # If the layer doesn't exist in the map, that's a failure
                assert False, f"Layer {expected_layer} not found in synthesis_map.layers"

    @given(file_summaries_data=file_summaries_for_layer_grouping_strategy())
    @settings(max_examples=100)
    def test_only_valid_layers_in_synthesis_map(self, file_summaries_data):
        """Feature: bottom-up-generation, Property 7: Synthesis_Map Layer Grouping Completeness
        
        Only valid layer names appear in the synthesis map.
        """
        from oya.generation.summaries import FileSummary, VALID_LAYERS
        from oya.generation.synthesis import SynthesisGenerator
        
        # Create FileSummary objects from generated data
        file_summaries = [
            FileSummary(
                file_path=data["file_path"],
                purpose=data["purpose"],
                layer=data["layer"],
                key_abstractions=data["key_abstractions"],
                internal_deps=data["internal_deps"],
                external_deps=data["external_deps"],
            )
            for data in file_summaries_data
        ]
        
        # Create SynthesisGenerator and group files by layer
        generator = SynthesisGenerator(llm_client=None)
        synthesis_map = generator.group_files_by_layer(file_summaries)
        
        # All layer names in the synthesis map should be valid
        for layer_name in synthesis_map.layers.keys():
            assert layer_name in VALID_LAYERS, \
                f"Invalid layer name {layer_name} in synthesis map"


# Strategy for generating large sets of FileSummaries for batching tests
@st.composite
def large_file_summaries_strategy(draw):
    """Generate a large set of FileSummaries that would exceed context limits.
    
    Generates summaries with substantial content to simulate real-world scenarios
    where batching would be necessary.
    """
    # Generate between 10 and 50 file summaries with substantial content
    num_files = draw(st.integers(min_value=10, max_value=50))
    
    file_summaries = []
    for i in range(num_files):
        # Generate path components
        dir_name = draw(st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
            min_size=5,
            max_size=30
        ).filter(lambda x: x.strip()))
        file_name = draw(st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
            min_size=5,
            max_size=30
        ).filter(lambda x: x.strip()))
        
        file_path = f"{dir_name}/{file_name}_{i}.py"
        
        # Generate substantial purpose text (100-500 chars)
        purpose = draw(st.text(
            alphabet=YAML_SAFE_ALPHABET,
            min_size=100,
            max_size=500
        ).filter(lambda x: x.strip()))
        
        layer = draw(st.sampled_from(VALID_LAYERS))
        
        # Generate multiple key abstractions
        key_abstractions = draw(st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
                min_size=5,
                max_size=50
            ).filter(lambda x: x.strip()),
            min_size=2,
            max_size=10
        ))
        
        # Generate internal dependencies
        internal_deps = draw(st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789/_-.",
                min_size=10,
                max_size=60
            ).filter(lambda x: x.strip()),
            min_size=1,
            max_size=8
        ))
        
        # Generate external dependencies
        external_deps = draw(st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
                min_size=3,
                max_size=30
            ).filter(lambda x: x.strip()),
            min_size=1,
            max_size=5
        ))
        
        file_summaries.append({
            "file_path": file_path,
            "purpose": purpose,
            "layer": layer,
            "key_abstractions": key_abstractions,
            "internal_deps": internal_deps,
            "external_deps": external_deps,
        })
    
    return file_summaries


class TestSynthesisBatchingForLargeInputs:
    """Property 9: Synthesis Batching for Large Inputs
    
    For any set of summaries exceeding the configured context limit, the 
    Synthesis_Generator SHALL process them in batches and produce a valid 
    merged Synthesis_Map without exceeding token limits in any single LLM call.
    
    Validates: Requirements 3.8
    """

    @given(file_summaries_data=large_file_summaries_strategy())
    @settings(max_examples=100)
    def test_batching_produces_valid_synthesis_map(self, file_summaries_data):
        """Feature: bottom-up-generation, Property 9: Synthesis Batching for Large Inputs
        
        Large inputs are processed in batches and produce a valid merged SynthesisMap.
        """
        from oya.generation.summaries import FileSummary, DirectorySummary
        from oya.generation.synthesis import SynthesisGenerator
        
        # Create FileSummary objects from generated data
        file_summaries = [
            FileSummary(
                file_path=data["file_path"],
                purpose=data["purpose"],
                layer=data["layer"],
                key_abstractions=data["key_abstractions"],
                internal_deps=data["internal_deps"],
                external_deps=data["external_deps"],
            )
            for data in file_summaries_data
        ]
        
        # Create empty directory summaries for this test
        directory_summaries: list[DirectorySummary] = []
        
        # Create SynthesisGenerator with a small context limit to force batching
        generator = SynthesisGenerator(llm_client=None)
        
        # Estimate token count for summaries
        total_tokens = generator.estimate_token_count(file_summaries, directory_summaries)
        
        # Set a context limit that's smaller than total to force batching
        # Use a small limit to ensure batching happens
        context_limit = max(1000, total_tokens // 3)
        
        # Get batches
        batches = generator.create_batches(
            file_summaries, 
            directory_summaries, 
            context_limit=context_limit
        )
        
        # Property 1: At least one batch should be created
        assert len(batches) >= 1, "Should create at least one batch"
        
        # Property 2: Each batch should not exceed the context limit
        for i, batch in enumerate(batches):
            batch_file_summaries, batch_dir_summaries = batch
            batch_tokens = generator.estimate_token_count(
                batch_file_summaries, 
                batch_dir_summaries
            )
            # Allow some tolerance for estimation
            assert batch_tokens <= context_limit * 1.1, \
                f"Batch {i} exceeds context limit: {batch_tokens} > {context_limit}"
        
        # Property 3: All files should be covered across all batches
        all_files_in_batches = set()
        for batch_file_summaries, _ in batches:
            for fs in batch_file_summaries:
                all_files_in_batches.add(fs.file_path)
        
        original_files = {fs.file_path for fs in file_summaries}
        assert all_files_in_batches == original_files, \
            "All files should be covered across batches"

    @given(file_summaries_data=large_file_summaries_strategy())
    @settings(max_examples=100)
    def test_batching_with_large_context_creates_single_batch(self, file_summaries_data):
        """Feature: bottom-up-generation, Property 9: Synthesis Batching for Large Inputs
        
        When context limit is large enough, a single batch is created.
        """
        from oya.generation.summaries import FileSummary, DirectorySummary
        from oya.generation.synthesis import SynthesisGenerator
        
        # Create FileSummary objects from generated data
        file_summaries = [
            FileSummary(
                file_path=data["file_path"],
                purpose=data["purpose"],
                layer=data["layer"],
                key_abstractions=data["key_abstractions"],
                internal_deps=data["internal_deps"],
                external_deps=data["external_deps"],
            )
            for data in file_summaries_data
        ]
        
        directory_summaries: list[DirectorySummary] = []
        
        generator = SynthesisGenerator(llm_client=None)
        
        # Use a very large context limit
        context_limit = 1_000_000  # 1M tokens should fit everything
        
        batches = generator.create_batches(
            file_summaries, 
            directory_summaries, 
            context_limit=context_limit
        )
        
        # Should create exactly one batch when limit is large enough
        assert len(batches) == 1, \
            f"Expected 1 batch with large context limit, got {len(batches)}"
        
        # The single batch should contain all files
        batch_file_summaries, _ = batches[0]
        assert len(batch_file_summaries) == len(file_summaries), \
            "Single batch should contain all files"

    @given(file_summaries_data=file_summaries_for_layer_grouping_strategy())
    @settings(max_examples=100)
    def test_merged_synthesis_map_contains_all_layers(self, file_summaries_data):
        """Feature: bottom-up-generation, Property 9: Synthesis Batching for Large Inputs
        
        Merged SynthesisMap from batches contains all layers from all files.
        """
        from oya.generation.summaries import FileSummary, DirectorySummary
        from oya.generation.synthesis import SynthesisGenerator
        
        # Create FileSummary objects from generated data
        file_summaries = [
            FileSummary(
                file_path=data["file_path"],
                purpose=data["purpose"],
                layer=data["layer"],
                key_abstractions=data["key_abstractions"],
                internal_deps=data["internal_deps"],
                external_deps=data["external_deps"],
            )
            for data in file_summaries_data
        ]
        
        directory_summaries: list[DirectorySummary] = []
        
        generator = SynthesisGenerator(llm_client=None)
        
        # Force batching with small context limit
        context_limit = 500
        
        batches = generator.create_batches(
            file_summaries, 
            directory_summaries, 
            context_limit=context_limit
        )
        
        # Merge batch results
        merged_map = generator.merge_batch_results(
            [generator.group_files_by_layer(batch_fs) for batch_fs, _ in batches]
        )
        
        # Get expected layers from original files
        expected_layers = {fs.layer for fs in file_summaries}
        
        # Merged map should contain all expected layers
        assert set(merged_map.layers.keys()) == expected_layers, \
            f"Expected layers {expected_layers}, got {set(merged_map.layers.keys())}"
        
        # All files should be in the merged map
        all_files_in_merged = set()
        for layer_info in merged_map.layers.values():
            all_files_in_merged.update(layer_info.files)
        
        original_files = {fs.file_path for fs in file_summaries}
        assert all_files_in_merged == original_files, \
            "Merged map should contain all original files"



class TestSynthesisMapPersistence:
    """Tests for SynthesisMap persistence to synthesis.json.
    
    Validates: Requirements 3.6
    """

    def test_save_and_load_synthesis_map(self, tmp_path):
        """Test that SynthesisMap can be saved and loaded from synthesis.json."""
        from oya.generation.summaries import SynthesisMap, LayerInfo, ComponentInfo
        from oya.generation.synthesis import save_synthesis_map, load_synthesis_map
        
        # Create a SynthesisMap
        synthesis_map = SynthesisMap(
            layers={
                "api": LayerInfo(
                    name="api",
                    purpose="REST API endpoints",
                    directories=["src/api"],
                    files=["src/api/routes.py", "src/api/handlers.py"],
                ),
                "domain": LayerInfo(
                    name="domain",
                    purpose="Core business logic",
                    directories=["src/domain"],
                    files=["src/domain/models.py"],
                ),
            },
            key_components=[
                ComponentInfo(
                    name="Router",
                    file="src/api/routes.py",
                    role="Main API router",
                    layer="api",
                ),
            ],
            dependency_graph={"api": ["domain"]},
            project_summary="A test project",
        )
        
        # Save to temp directory
        meta_path = str(tmp_path / "meta")
        saved_path = save_synthesis_map(synthesis_map, meta_path)
        
        # Verify file was created
        assert saved_path.endswith("synthesis.json")
        import os
        assert os.path.exists(saved_path)
        
        # Load it back
        loaded_map, synthesis_hash = load_synthesis_map(meta_path)
        
        # Verify loaded data matches
        assert loaded_map is not None
        assert synthesis_hash is not None
        assert len(synthesis_hash) == 16  # SHA256 truncated to 16 chars
        
        # Verify layers
        assert set(loaded_map.layers.keys()) == {"api", "domain"}
        assert loaded_map.layers["api"].files == ["src/api/routes.py", "src/api/handlers.py"]
        
        # Verify key_components
        assert len(loaded_map.key_components) == 1
        assert loaded_map.key_components[0].name == "Router"
        
        # Verify dependency_graph
        assert loaded_map.dependency_graph == {"api": ["domain"]}
        
        # Verify project_summary
        assert loaded_map.project_summary == "A test project"

    def test_load_nonexistent_synthesis_map(self, tmp_path):
        """Test that loading from nonexistent path returns None."""
        from oya.generation.synthesis import load_synthesis_map
        
        meta_path = str(tmp_path / "nonexistent")
        loaded_map, synthesis_hash = load_synthesis_map(meta_path)
        
        assert loaded_map is None
        assert synthesis_hash is None

    def test_synthesis_hash_changes_with_content(self, tmp_path):
        """Test that synthesis_hash changes when content changes."""
        from oya.generation.summaries import SynthesisMap, LayerInfo
        from oya.generation.synthesis import save_synthesis_map, load_synthesis_map
        
        meta_path = str(tmp_path / "meta")
        
        # Create and save first map
        map1 = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="API", directories=[], files=["a.py"])},
            key_components=[],
            dependency_graph={},
            project_summary="Version 1",
        )
        save_synthesis_map(map1, meta_path)
        _, hash1 = load_synthesis_map(meta_path)
        
        # Create and save second map with different content
        map2 = SynthesisMap(
            layers={"api": LayerInfo(name="api", purpose="API", directories=[], files=["b.py"])},
            key_components=[],
            dependency_graph={},
            project_summary="Version 2",
        )
        save_synthesis_map(map2, meta_path)
        _, hash2 = load_synthesis_map(meta_path)
        
        # Hashes should be different
        assert hash1 != hash2

    @given(data=synthesis_map_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_synthesis_map_persistence_round_trip(self, data, tmp_path):
        """Property test: Any SynthesisMap can be saved and loaded correctly."""
        from oya.generation.summaries import SynthesisMap, LayerInfo, ComponentInfo
        from oya.generation.synthesis import save_synthesis_map, load_synthesis_map
        
        # Build the SynthesisMap from generated data
        layers = {
            name: LayerInfo(
                name=layer_data["name"],
                purpose=layer_data["purpose"],
                directories=layer_data["directories"],
                files=layer_data["files"],
            )
            for name, layer_data in data["layers"].items()
        }
        
        key_components = [
            ComponentInfo(
                name=comp["name"],
                file=comp["file"],
                role=comp["role"],
                layer=comp["layer"],
            )
            for comp in data["key_components"]
        ]
        
        original = SynthesisMap(
            layers=layers,
            key_components=key_components,
            dependency_graph=data["dependency_graph"],
            project_summary=data["project_summary"],
        )
        
        # Use a unique path for each test run
        import uuid
        meta_path = str(tmp_path / f"meta_{uuid.uuid4().hex[:8]}")
        
        # Save and load
        save_synthesis_map(original, meta_path)
        loaded, synthesis_hash = load_synthesis_map(meta_path)
        
        # Verify loaded correctly
        assert loaded is not None
        assert synthesis_hash is not None
        
        # Verify layers match
        assert set(loaded.layers.keys()) == set(original.layers.keys())
        for layer_name in original.layers:
            assert loaded.layers[layer_name].files == original.layers[layer_name].files
            assert loaded.layers[layer_name].directories == original.layers[layer_name].directories
        
        # Verify key_components match
        assert len(loaded.key_components) == len(original.key_components)
        
        # Verify dependency_graph matches
        assert loaded.dependency_graph == original.dependency_graph
        
        # Verify project_summary matches
        assert loaded.project_summary == original.project_summary


def test_parse_file_summary_logs_warning_on_invalid_layer(caplog):
    """Test that invalid layer values log a warning before coercing to utility."""
    from oya.generation.summaries import SummaryParser

    parser = SummaryParser()
    markdown = """---
file_summary:
  purpose: "Test file"
  layer: invalid_layer
  key_abstractions: []
  internal_deps: []
  external_deps: []
---

# Test File
"""

    with caplog.at_level(logging.WARNING, logger="oya.generation.summaries"):
        clean_md, summary = parser.parse_file_summary(markdown, "test/file.py")

    # Should coerce to utility
    assert summary.layer == "utility"

    # Should have logged a warning
    assert "Invalid layer 'invalid_layer'" in caplog.text
    assert "test/file.py" in caplog.text
    assert "defaulting to 'utility'" in caplog.text
