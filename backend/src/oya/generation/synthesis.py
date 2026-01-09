"""Synthesis generator for bottom-up wiki generation.

This module provides the SynthesisGenerator class that synthesizes file and
directory summaries into a coherent codebase understanding map (SynthesisMap).
"""

from oya.generation.summaries import (
    DirectorySummary,
    FileSummary,
    LayerInfo,
    SynthesisMap,
    VALID_LAYERS,
)


class SynthesisGenerator:
    """Generates Synthesis_Map from collected file and directory summaries.
    
    The SynthesisGenerator takes all File_Summaries and Directory_Summaries
    collected during the generation pipeline and synthesizes them into a
    coherent SynthesisMap that can be used by Architecture and Overview
    generators.
    
    Attributes:
        llm_client: The LLM client for generating project summaries and
                   identifying patterns (can be None for layer grouping only).
    """
    
    def __init__(self, llm_client):
        """Initialize the SynthesisGenerator.
        
        Args:
            llm_client: The LLM client for generating summaries. Can be None
                       if only using layer grouping functionality.
        """
        self.llm_client = llm_client
    
    async def generate(
        self,
        file_summaries: list[FileSummary],
        directory_summaries: list[DirectorySummary],
    ) -> SynthesisMap:
        """Generate a SynthesisMap from all collected summaries.
        
        This method orchestrates the synthesis process:
        1. Groups files by their layer classification
        2. Identifies key components across the codebase
        3. Builds a dependency graph
        4. Generates an overall project summary using the LLM
        
        Args:
            file_summaries: List of FileSummary objects from all processed files.
            directory_summaries: List of DirectorySummary objects from all
                               processed directories.
        
        Returns:
            A SynthesisMap containing the aggregated codebase understanding.
        """
        # Start with layer grouping
        synthesis_map = self.group_files_by_layer(file_summaries)
        
        # TODO: In future tasks, add:
        # - Key component identification (Task 13)
        # - Dependency graph building (Task 13)
        # - LLM-based project summary generation (Task 13)
        # - Batch processing for large inputs (Task 13)
        
        return synthesis_map
    
    def group_files_by_layer(
        self,
        file_summaries: list[FileSummary],
    ) -> SynthesisMap:
        """Group files by their layer classification.
        
        Creates a SynthesisMap with LayerInfo objects for each layer that
        contains at least one file. Each file appears in exactly one layer
        based on its layer classification.
        
        Args:
            file_summaries: List of FileSummary objects to group.
        
        Returns:
            A SynthesisMap with files grouped into layers.
        """
        # Initialize layers dict - only create layers that have files
        layers: dict[str, LayerInfo] = {}
        
        # Group files by their layer classification
        for file_summary in file_summaries:
            layer_name = file_summary.layer
            
            # Create layer if it doesn't exist
            if layer_name not in layers:
                layers[layer_name] = LayerInfo(
                    name=layer_name,
                    purpose=self._get_layer_purpose(layer_name),
                    directories=[],
                    files=[],
                )
            
            # Add file to its layer
            layers[layer_name].files.append(file_summary.file_path)
        
        return SynthesisMap(
            layers=layers,
            key_components=[],
            dependency_graph={},
            project_summary="",
        )
    
    def _get_layer_purpose(self, layer_name: str) -> str:
        """Get a default purpose description for a layer.
        
        Args:
            layer_name: The name of the layer.
        
        Returns:
            A default purpose description for the layer.
        """
        layer_purposes = {
            "api": "REST API endpoints and request handling",
            "domain": "Core business logic and domain models",
            "infrastructure": "External service integrations and infrastructure concerns",
            "utility": "Shared utilities and helper functions",
            "config": "Configuration management and settings",
            "test": "Test files and testing utilities",
        }
        return layer_purposes.get(layer_name, f"Files classified as {layer_name}")
