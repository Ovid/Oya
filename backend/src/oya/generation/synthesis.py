"""Synthesis generator for bottom-up wiki generation.

This module provides the SynthesisGenerator class that synthesizes file and
directory summaries into a coherent codebase understanding map (SynthesisMap).
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from oya.config import ConfigError, load_settings
from oya.generation.summaries import (
    ComponentInfo,
    DirectorySummary,
    FileSummary,
    LayerInfo,
    SynthesisMap,
)
from oya.generation.prompts import get_synthesis_prompt, SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class SynthesisGenerator:
    """Generates Synthesis_Map from collected file and directory summaries.

    The SynthesisGenerator takes all File_Summaries and Directory_Summaries
    collected during the generation pipeline and synthesizes them into a
    coherent SynthesisMap that can be used by Architecture and Overview
    generators.

    Attributes:
        llm_client: The LLM client for generating project summaries and
                   identifying patterns (can be None for layer grouping only).
        context_limit: Maximum tokens allowed in a single LLM call.
    """

    def __init__(self, llm_client, context_limit: int | None = None):
        """Initialize the SynthesisGenerator.

        Args:
            llm_client: The LLM client for generating summaries. Can be None
                       if only using layer grouping functionality.
            context_limit: Maximum tokens allowed in a single LLM call.
        """
        self.llm_client = llm_client
        if context_limit is None:
            try:
                settings = load_settings()
                context_limit = settings.generation.context_limit
            except (ValueError, OSError, ConfigError):
                # Settings not available
                context_limit = 100_000  # Default from CONFIG_SCHEMA
        self.context_limit = context_limit

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

        # If we have an LLM client, use it to enhance the synthesis
        if self.llm_client is not None:
            # Check if we need batching
            total_tokens = self.estimate_token_count(file_summaries, directory_summaries)

            if total_tokens > self.context_limit:
                # Process in batches
                batches = self.create_batches(
                    file_summaries, directory_summaries, self.context_limit
                )

                # Process each batch and collect results
                batch_results = []
                for batch_file_summaries, batch_dir_summaries in batches:
                    batch_result = await self._process_batch(
                        batch_file_summaries, batch_dir_summaries
                    )
                    batch_results.append(batch_result)

                # Merge batch results
                synthesis_map = self.merge_batch_results(batch_results)
            else:
                # Process all at once
                synthesis_map = await self._process_batch(file_summaries, directory_summaries)

        return synthesis_map

    async def _process_batch(
        self,
        file_summaries: list[FileSummary],
        directory_summaries: list[DirectorySummary],
    ) -> SynthesisMap:
        """Process a single batch of summaries using the LLM.

        Args:
            file_summaries: List of FileSummary objects for this batch.
            directory_summaries: List of DirectorySummary objects for this batch.

        Returns:
            A SynthesisMap for this batch.
        """
        # Start with layer grouping
        synthesis_map = self.group_files_by_layer(file_summaries)

        if self.llm_client is None:
            return synthesis_map

        # Generate prompt
        prompt = get_synthesis_prompt(file_summaries, directory_summaries)

        try:
            # Call LLM
            try:
                settings = load_settings()
                temperature = settings.generation.temperature
            except (ValueError, OSError, ConfigError):
                # Settings not available
                temperature = 0.3  # Default from CONFIG_SCHEMA
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=temperature,
            )

            # Parse JSON response
            llm_result = self._parse_llm_response(response)

            # Merge LLM results into synthesis map
            if llm_result:
                synthesis_map.key_components = llm_result.get("key_components", [])
                synthesis_map.dependency_graph = llm_result.get("dependency_graph", {})
                synthesis_map.project_summary = llm_result.get("project_summary", "")
                synthesis_map.layer_interactions = llm_result.get("layer_interactions", "")
        except Exception as e:
            logger.error(
                "LLM call failed during synthesis, falling back to basic layer grouping. "
                f"Error: {type(e).__name__}: {e}"
            )

        return synthesis_map

    def _parse_llm_response(self, response: str) -> dict | None:
        """Parse the LLM JSON response.

        Args:
            response: Raw LLM response string.

        Returns:
            Parsed dict or None if parsing fails.
        """
        try:
            # Try to extract JSON from the response
            # Handle cases where LLM wraps JSON in markdown code blocks
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            data = json.loads(response)

            # Convert key_components to ComponentInfo objects
            key_components = []
            for comp in data.get("key_components", []):
                if isinstance(comp, dict):
                    key_components.append(
                        ComponentInfo(
                            name=comp.get("name", ""),
                            file=comp.get("file", ""),
                            role=comp.get("role", ""),
                            layer=comp.get("layer", "utility"),
                        )
                    )

            return {
                "key_components": key_components,
                "dependency_graph": data.get("dependency_graph", {}),
                "project_summary": data.get("project_summary", ""),
                "layer_interactions": data.get("layer_interactions", ""),
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def estimate_token_count(
        self,
        file_summaries: list[FileSummary],
        directory_summaries: list[DirectorySummary],
    ) -> int:
        """Estimate the token count for a set of summaries.

        Uses a simple character-based estimation. This is a rough approximation
        since actual tokenization varies by model.

        Args:
            file_summaries: List of FileSummary objects.
            directory_summaries: List of DirectorySummary objects.

        Returns:
            Estimated token count.
        """
        total_chars = 0

        for fs in file_summaries:
            total_chars += len(fs.file_path)
            total_chars += len(fs.purpose)
            total_chars += len(fs.layer)
            total_chars += sum(len(a) for a in fs.key_abstractions)
            total_chars += sum(len(d) for d in fs.internal_deps)
            total_chars += sum(len(d) for d in fs.external_deps)

        for ds in directory_summaries:
            total_chars += len(ds.directory_path)
            total_chars += len(ds.purpose)
            total_chars += sum(len(f) for f in ds.contains)
            total_chars += len(ds.role_in_system)

        # Add overhead for formatting (markdown, labels, etc.)
        total_chars = int(total_chars * 1.5)

        try:
            settings = load_settings()
            tokens_per_char = settings.generation.tokens_per_char
        except (ValueError, OSError, ConfigError):
            # Settings not available
            tokens_per_char = 0.25  # Default from CONFIG_SCHEMA
        return int(total_chars * tokens_per_char)

    def create_batches(
        self,
        file_summaries: list[FileSummary],
        directory_summaries: list[DirectorySummary],
        context_limit: int,
    ) -> list[tuple[list[FileSummary], list[DirectorySummary]]]:
        """Split summaries into batches that fit within the context limit.

        Args:
            file_summaries: List of FileSummary objects.
            directory_summaries: List of DirectorySummary objects.
            context_limit: Maximum tokens per batch.

        Returns:
            List of (file_summaries, directory_summaries) tuples for each batch.
        """
        batches = []
        current_file_batch: list[FileSummary] = []
        current_dir_batch: list[DirectorySummary] = []
        current_tokens = 0

        # Process file summaries first
        for fs in file_summaries:
            fs_tokens = self.estimate_token_count([fs], [])

            if current_tokens + fs_tokens > context_limit and current_file_batch:
                # Start a new batch
                batches.append((current_file_batch, current_dir_batch))
                current_file_batch = []
                current_dir_batch = []
                current_tokens = 0

            current_file_batch.append(fs)
            current_tokens += fs_tokens

        # Process directory summaries
        for ds in directory_summaries:
            ds_tokens = self.estimate_token_count([], [ds])

            if current_tokens + ds_tokens > context_limit and (
                current_file_batch or current_dir_batch
            ):
                # Start a new batch
                batches.append((current_file_batch, current_dir_batch))
                current_file_batch = []
                current_dir_batch = []
                current_tokens = 0

            current_dir_batch.append(ds)
            current_tokens += ds_tokens

        # Add the last batch if not empty
        if current_file_batch or current_dir_batch:
            batches.append((current_file_batch, current_dir_batch))

        # Ensure at least one batch exists
        if not batches:
            batches.append(([], []))

        return batches

    def merge_batch_results(
        self,
        batch_results: list[SynthesisMap],
    ) -> SynthesisMap:
        """Merge multiple SynthesisMap results from batches into one.

        Args:
            batch_results: List of SynthesisMap objects from batch processing.

        Returns:
            A merged SynthesisMap containing all data from all batches.
        """
        if not batch_results:
            return SynthesisMap()

        if len(batch_results) == 1:
            return batch_results[0]

        # Merge layers
        merged_layers: dict[str, LayerInfo] = {}
        for result in batch_results:
            for layer_name, layer_info in result.layers.items():
                if layer_name not in merged_layers:
                    merged_layers[layer_name] = LayerInfo(
                        name=layer_name,
                        purpose=layer_info.purpose,
                        directories=[],
                        files=[],
                    )
                # Merge files and directories (avoid duplicates)
                for f in layer_info.files:
                    if f not in merged_layers[layer_name].files:
                        merged_layers[layer_name].files.append(f)
                for d in layer_info.directories:
                    if d not in merged_layers[layer_name].directories:
                        merged_layers[layer_name].directories.append(d)

        # Merge key_components (avoid duplicates by name)
        merged_components: list[ComponentInfo] = []
        seen_component_names: set[str] = set()
        for result in batch_results:
            for comp in result.key_components:
                if comp.name not in seen_component_names:
                    merged_components.append(comp)
                    seen_component_names.add(comp.name)

        # Merge dependency_graph
        merged_deps: dict[str, list[str]] = {}
        for result in batch_results:
            for key, deps in result.dependency_graph.items():
                if key not in merged_deps:
                    merged_deps[key] = []
                for dep in deps:
                    if dep not in merged_deps[key]:
                        merged_deps[key].append(dep)

        # Combine project summaries (take the longest/most detailed one)
        project_summary = ""
        for result in batch_results:
            if len(result.project_summary) > len(project_summary):
                project_summary = result.project_summary

        # Combine layer_interactions (take the longest/most detailed one)
        layer_interactions = ""
        for result in batch_results:
            if len(result.layer_interactions) > len(layer_interactions):
                layer_interactions = result.layer_interactions

        return SynthesisMap(
            layers=merged_layers,
            key_components=merged_components,
            dependency_graph=merged_deps,
            project_summary=project_summary,
            layer_interactions=layer_interactions,
        )

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


def save_synthesis_map(synthesis_map: SynthesisMap, meta_path: str) -> str:
    """Save a SynthesisMap to synthesis.json in the meta directory.

    Args:
        synthesis_map: The SynthesisMap to save.
        meta_path: Path to the .oyawiki/meta directory.

    Returns:
        Path to the saved synthesis.json file.
    """
    meta_dir = Path(meta_path)
    meta_dir.mkdir(parents=True, exist_ok=True)

    synthesis_path = meta_dir / "synthesis.json"

    # Get the JSON representation
    json_content = synthesis_map.to_json()

    # Compute hash of the synthesis map for change detection
    synthesis_hash = hashlib.sha256(json_content.encode()).hexdigest()[:16]

    # Parse the JSON to add metadata
    data = json.loads(json_content)
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data["synthesis_hash"] = synthesis_hash

    # Write to file
    with open(synthesis_path, "w") as f:
        json.dump(data, f, indent=2)

    return str(synthesis_path)


def load_synthesis_map(meta_path: str) -> tuple[SynthesisMap | None, str | None]:
    """Load a SynthesisMap from synthesis.json in the meta directory.

    Args:
        meta_path: Path to the .oyawiki/meta directory.

    Returns:
        Tuple of (SynthesisMap, synthesis_hash) or (None, None) if not found.
    """
    synthesis_path = Path(meta_path) / "synthesis.json"

    if not synthesis_path.exists():
        return None, None

    try:
        with open(synthesis_path) as f:
            data = json.load(f)

        # Extract metadata
        synthesis_hash = data.pop("synthesis_hash", None)
        data.pop("generated_at", None)  # Remove metadata before parsing

        # Convert back to JSON string for parsing
        json_str = json.dumps(data)
        synthesis_map = SynthesisMap.from_json(json_str)

        return synthesis_map, synthesis_hash
    except (json.JSONDecodeError, KeyError, FileNotFoundError):
        return None, None
