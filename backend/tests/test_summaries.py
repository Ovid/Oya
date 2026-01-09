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
