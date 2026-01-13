# Phase 4 (Synthesis) in the Oya Generation Pipeline

## Overview

Phase 4 (Synthesis) is the pivotal phase that bridges low-level documentation (files and directories) with high-level documentation (architecture and overview). It takes the structured summaries collected from Phase 2 (Files) and Phase 3 (Directories) and synthesizes them into a unified codebase understanding map called a `SynthesisMap`. [1](#9-0) 

## Main Components

### 1. SynthesisGenerator Class

The `SynthesisGenerator` is the core component responsible for processing file and directory summaries. It takes all `FileSummary` and `DirectorySummary` objects collected during the generation pipeline and synthesizes them into a coherent `SynthesisMap`. [2](#9-1) 

The generator has two main attributes:
- **llm_client**: The LLM client for generating project summaries and identifying patterns (can be None for layer grouping only)
- **context_limit**: Maximum tokens allowed in a single LLM call (default: 100,000 tokens) [3](#9-2) 

### 2. Data Structures

#### SynthesisMap

The primary output data structure containing the aggregated codebase understanding: [4](#9-3) 

The `SynthesisMap` contains:
- **layers**: Dictionary mapping layer names to `LayerInfo` objects
- **key_components**: List of important `ComponentInfo` objects across the codebase
- **dependency_graph**: Mapping of layer dependencies
- **project_summary**: LLM-generated overall project description

#### LayerInfo

Represents a logical grouping of code by responsibility: [5](#9-4) 

#### ComponentInfo

Represents important abstractions that play significant roles in the system: [6](#9-5) 

## Core Responsibilities

The synthesis phase orchestrates four main operations: [7](#9-6) 

### 1. Layer Grouping

The `group_files_by_layer()` method groups files by their architectural layer classification (api, domain, infrastructure, utility, config, test). Each file appears in exactly one layer based on its layer classification from Phase 2. [8](#9-7) 

This provides default layer purposes for each category: [9](#9-8) 

### 2. Key Component Identification

Using the LLM, the synthesis phase identifies the 5-15 most important classes, functions, or modules that form the backbone of the system. The LLM analyzes all file and directory summaries to determine which components are central to the architecture. [10](#9-9) 

### 3. Dependency Graph Construction

The synthesis phase builds a dependency graph mapping which layers depend on which other layers (e.g., "api" depends on "domain", "domain" depends on "infrastructure").

### 4. Project Summary Generation

The LLM generates a comprehensive 2-3 sentence summary of what the project does, its main purpose, and key technologies used.

## Processing Flow

### Basic Flow

When summaries don't exceed the context limit, processing is straightforward: [11](#9-10) 

### Batching for Large Codebases

When the total token count exceeds the context limit, the synthesis phase implements batching: [12](#9-11) 

The batching strategy splits summaries into manageable chunks: [13](#9-12) 

Batch results are then merged: [14](#9-13) 

### Token Estimation

A simple character-based estimation is used to determine when batching is needed: [15](#9-14) 

## Integration with Phase 3 (Directory Documentation)

### Input from Phase 3

Phase 3 produces `DirectorySummary` objects that are passed directly to the synthesis phase: [16](#9-15) 

The orchestrator collects both file and directory summaries from Phases 2-3: [17](#9-16) 

### Cascade Behavior

If any files or directories are regenerated in Phases 2-3, the synthesis phase must also regenerate to ensure high-level documentation reflects the current state: [18](#9-17) [19](#9-18) 

### Storage

The synthesis map is saved to `synthesis.json` in the meta directory: [20](#9-19) 

## Integration with Phase 5 (Architecture)

### Output to Phase 5

The `SynthesisMap` becomes the primary context for generating architecture documentation. The architecture generator receives the synthesis map and uses it to create rich architecture pages: [21](#9-20) [22](#9-21) 

The architecture generator formats the synthesis map data into prompts: [23](#9-22) 

### Phase 6 Integration (Overview)

Similarly, the overview generator uses the synthesis map as its primary context: [24](#9-23) [25](#9-24) 

### Cascade to Higher Phases

When synthesis is regenerated, both Architecture (Phase 5) and Overview (Phase 6) are automatically regenerated: [26](#9-25) 

## Strengths

### 1. **Structured Aggregation**
The synthesis phase provides a well-defined interface between low-level (file/directory) and high-level (architecture/overview) documentation, creating a clean separation of concerns in the pipeline.

### 2. **Scalability Through Batching**
The batching mechanism allows the system to handle large codebases that exceed LLM context limits by processing summaries in chunks. [27](#9-26) 

### 3. **Graceful Degradation**
If the LLM fails or is unavailable, the system falls back to basic layer grouping, ensuring the pipeline continues: [28](#9-27) 

### 4. **Deterministic Layer Grouping**
Layer grouping is performed algorithmically based on file classifications, ensuring consistency regardless of LLM behavior.

### 5. **Incremental Regeneration Support**
The cascade behavior ensures that synthesis is only regenerated when needed, saving tokens and time: [29](#9-28) 

### 6. **Serialization Support**
The synthesis map can be persisted and loaded from JSON, enabling caching and incremental updates: [30](#9-29) 

## Weaknesses

### 1. **Rough Token Estimation**
The token estimation uses a simple character-based multiplier (0.25 tokens per character), which may be inaccurate for different languages or content types: [31](#9-30) 

This could cause batches to unexpectedly exceed context limits or create unnecessarily small batches.

### 2. **Simplistic Merge Strategy**
When batching is required, the merge strategy takes the longest project summary, which may not represent the full codebase if important information exists in shorter summaries from other batches: [32](#9-31) 

### 3. **Silent LLM Failure Handling**
When the LLM fails during batch processing, the exception is caught silently with a bare `except Exception: pass`, which may hide important errors: [33](#9-32) 

### 4. **Loss of Nuance in Component Deduplication**
The merge process deduplicates components by name only, potentially losing important distinctions between similarly-named components in different contexts: [34](#9-33) 

### 5. **Limited Context for Large Codebases**
Even with batching, the LLM may not have full context across all batches when identifying key components and dependencies, potentially missing cross-batch relationships.

### 6. **No Quality Metrics**
The system doesn't validate the quality of the synthesis output or measure how well the merged results represent the full codebase.

### 7. **Single-Pass Processing**
The synthesis phase processes summaries in a single pass without opportunities for refinement or validation of the generated synthesis map.

## Notes

Phase 4 (Synthesis) serves as a critical aggregation layer in the Oya pipeline, transforming detailed file and directory documentation into a high-level codebase understanding. Its strength lies in providing a clean, structured interface between low-level and high-level documentation with support for large codebases through batching. However, the simplistic merge strategies and token estimation methods represent areas where the implementation could be improved, particularly for very large or complex codebases where batch processing is required.

The cascade behavior ensures that changes to low-level documentation automatically trigger synthesis regeneration, which in turn triggers regeneration of all high-level documentation pages, maintaining consistency throughout the wiki.

### Citations

**File:** backend/src/oya/generation/synthesis.py (L1-5)
```python
"""Synthesis generator for bottom-up wiki generation.

This module provides the SynthesisGenerator class that synthesizes file and
directory summaries into a coherent codebase understanding map (SynthesisMap).
"""
```

**File:** backend/src/oya/generation/synthesis.py (L19-24)
```python
# Default context limit in tokens (conservative estimate for most models)
DEFAULT_CONTEXT_LIMIT = 100_000

# Approximate tokens per character (rough estimate)
TOKENS_PER_CHAR = 0.25

```

**File:** backend/src/oya/generation/synthesis.py (L26-49)
```python
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

    def __init__(self, llm_client, context_limit: int = DEFAULT_CONTEXT_LIMIT):
        """Initialize the SynthesisGenerator.

        Args:
            llm_client: The LLM client for generating summaries. Can be None
                       if only using layer grouping functionality.
            context_limit: Maximum tokens allowed in a single LLM call.
        """
        self.llm_client = llm_client
        self.context_limit = context_limit
```

**File:** backend/src/oya/generation/synthesis.py (L51-71)
```python
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
```

**File:** backend/src/oya/generation/synthesis.py (L76-100)
```python
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
```

**File:** backend/src/oya/generation/synthesis.py (L102-145)
```python
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
            response = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.3,  # Lower temperature for structured output
            )

            # Parse JSON response
            llm_result = self._parse_llm_response(response)

            # Merge LLM results into synthesis map
            if llm_result:
                synthesis_map.key_components = llm_result.get("key_components", [])
                synthesis_map.dependency_graph = llm_result.get("dependency_graph", {})
                synthesis_map.project_summary = llm_result.get("project_summary", "")
        except Exception:
            # On LLM failure, return the basic layer grouping
            pass

        return synthesis_map
```

**File:** backend/src/oya/generation/synthesis.py (L191-227)
```python
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

        return int(total_chars * TOKENS_PER_CHAR)
```

**File:** backend/src/oya/generation/synthesis.py (L229-288)
```python
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
```

**File:** backend/src/oya/generation/synthesis.py (L290-357)
```python
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

        return SynthesisMap(
            layers=merged_layers,
            key_components=merged_components,
            dependency_graph=merged_deps,
            project_summary=project_summary,
        )
```

**File:** backend/src/oya/generation/synthesis.py (L359-399)
```python
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
```

**File:** backend/src/oya/generation/synthesis.py (L401-418)
```python
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
```

**File:** backend/src/oya/generation/synthesis.py (L421-457)
```python
def save_synthesis_map(synthesis_map: SynthesisMap, meta_path: str) -> str:
    """Save a SynthesisMap to synthesis.json in the meta directory.

    Args:
        synthesis_map: The SynthesisMap to save.
        meta_path: Path to the .oyawiki/meta directory.

    Returns:
        Path to the saved synthesis.json file.
    """
    import hashlib
    from datetime import datetime, timezone
    from pathlib import Path

    meta_dir = Path(meta_path)
    meta_dir.mkdir(parents=True, exist_ok=True)

    synthesis_path = meta_dir / "synthesis.json"

    # Get the JSON representation
    json_content = synthesis_map.to_json()

    # Compute hash of the synthesis map for change detection
    synthesis_hash = hashlib.sha256(json_content.encode()).hexdigest()[:16]

    # Parse the JSON to add metadata
    import json

    data = json.loads(json_content)
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    data["synthesis_hash"] = synthesis_hash

    # Write to file
    with open(synthesis_path, "w") as f:
        json.dump(data, f, indent=2)

    return str(synthesis_path)
```

**File:** backend/src/oya/generation/summaries.py (L156-173)
```python
@dataclass
class LayerInfo:
    """Information about a code layer in the system architecture.

    Represents a logical grouping of code by responsibility (e.g., api, domain,
    infrastructure) with associated directories and files.

    Attributes:
        name: The layer name (e.g., "api", "domain", "infrastructure").
        purpose: Description of what this layer is responsible for.
        directories: List of directory paths belonging to this layer.
        files: List of file paths belonging to this layer.
    """

    name: str
    purpose: str
    directories: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
```

**File:** backend/src/oya/generation/summaries.py (L176-193)
```python
@dataclass
class ComponentInfo:
    """Information about a key component in the codebase.

    Represents an important abstraction (class, function, module) that plays
    a significant role in the system architecture.

    Attributes:
        name: The component name (e.g., class or function name).
        file: Path to the file containing this component.
        role: Description of what role this component plays in the system.
        layer: The architectural layer this component belongs to.
    """

    name: str
    file: str
    role: str
    layer: str
```

**File:** backend/src/oya/generation/summaries.py (L196-214)
```python
@dataclass
class SynthesisMap:
    """Aggregated codebase understanding synthesized from file and directory summaries.

    Combines all File_Summaries and Directory_Summaries into a coherent map of the
    codebase, including layer groupings, key components, and dependency relationships.
    This serves as the primary context for generating Architecture and Overview pages.

    Attributes:
        layers: Mapping of layer names to LayerInfo objects.
        key_components: List of important components identified across the codebase.
        dependency_graph: Mapping of component/layer names to their dependencies.
        project_summary: LLM-generated overall summary of the project.
    """

    layers: dict[str, LayerInfo] = field(default_factory=dict)
    key_components: list[ComponentInfo] = field(default_factory=list)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    project_summary: str = ""
```

**File:** backend/src/oya/generation/summaries.py (L216-244)
```python
    def to_json(self) -> str:
        """Serialize the SynthesisMap to a JSON string.

        Returns:
            JSON string representation of the SynthesisMap.
        """
        data = {
            "layers": {
                name: {
                    "name": layer.name,
                    "purpose": layer.purpose,
                    "directories": layer.directories,
                    "files": layer.files,
                }
                for name, layer in self.layers.items()
            },
            "key_components": [
                {
                    "name": comp.name,
                    "file": comp.file,
                    "role": comp.role,
                    "layer": comp.layer,
                }
                for comp in self.key_components
            ],
            "dependency_graph": self.dependency_graph,
            "project_summary": self.project_summary,
        }
        return json.dumps(data, indent=2)
```

**File:** backend/src/oya/generation/prompts.py (L54-96)
```python
SYNTHESIS_TEMPLATE = PromptTemplate(
    """Synthesize the following file and directory summaries into a coherent understanding of the codebase.

## File Summaries
{file_summaries}

## Directory Summaries
{directory_summaries}

---

Analyze the summaries above and produce a JSON response with the following structure:

```json
{{
  "key_components": [
    {{
      "name": "ComponentName",
      "file": "path/to/file.py",
      "role": "Description of what this component does and why it's important",
      "layer": "api|domain|infrastructure|utility|config|test"
    }}
  ],
  "dependency_graph": {{
    "layer_name": ["dependent_layer1", "dependent_layer2"]
  }},
  "project_summary": "A comprehensive 2-3 sentence summary of what this project does, its main purpose, and key technologies used."
}}
```

Guidelines:
1. **key_components**: Identify the 5-15 most important classes, functions, or modules that form the backbone of the system. Focus on:
   - Entry points and main orchestrators
   - Core domain models and services
   - Key infrastructure components
   - Important utilities used throughout

2. **dependency_graph**: Map which layers depend on which other layers. For example, "api" typically depends on "domain", and "domain" may depend on "infrastructure".

3. **project_summary**: Write a clear, informative summary that would help a new developer understand what this codebase does at a glance.

Respond with valid JSON only, no additional text."""
)
```

**File:** backend/src/oya/generation/prompts.py (L130-163)
```python
OVERVIEW_SYNTHESIS_TEMPLATE = PromptTemplate(
    """Generate a comprehensive overview page for the repository "{repo_name}".

## Project Summary (from code analysis)
{project_summary}

## System Layers
{layers}

## Key Components
{key_components}

## README Content (supplementary)
{readme_content}

## Project Structure
```
{file_tree}
```

## Package Information
{package_info}

---

Create a documentation overview that includes:
1. **Project Summary**: Use the project summary from code analysis as the primary source. If README content is available, incorporate any additional context it provides.
2. **Key Features**: Main capabilities and features based on the key components and layer structure
3. **Getting Started**: How to install and run the project (use README if available, otherwise infer from package info)
4. **Project Structure**: Overview of the directory organization based on the system layers
5. **Technology Stack**: Languages, frameworks, and key dependencies

Format the output as clean Markdown suitable for a wiki page."""
)
```

**File:** backend/src/oya/generation/prompts.py (L198-233)
```python
ARCHITECTURE_SYNTHESIS_TEMPLATE = PromptTemplate(
    """Generate an architecture documentation page for "{repo_name}".

## Project Structure
```
{file_tree}
```

## System Layers
{layers}

## Key Components
{key_components}

## Layer Dependencies
{dependency_graph}

## Project Summary
{project_summary}

## External Dependencies
{dependencies}

---

Create architecture documentation that includes:
1. **System Overview**: High-level description of the system architecture based on the project summary and layer structure
2. **Layer Architecture**: Describe each layer's purpose and responsibilities
3. **Component Diagram**: Create a Mermaid diagram showing the main components and their relationships based on the layer dependencies
4. **Key Components**: Document the most important classes and functions identified above
5. **Data Flow**: How data moves through the layers
6. **Design Patterns**: Notable patterns used in the codebase
7. **External Dependencies**: Key libraries and their purposes

Format the output as clean Markdown suitable for a wiki page."""
)
```

**File:** backend/src/oya/generation/orchestrator.py (L297-325)
```python
    def _should_regenerate_synthesis(
        self,
        files_regenerated: bool,
        directories_regenerated: bool,
    ) -> bool:
        """Check if synthesis needs to be regenerated.

        Synthesis should be regenerated when:
        - Any file's documentation was regenerated (cascade from files)
        - Any directory's documentation was regenerated (cascade from directories)
        - No existing synthesis.json exists

        Args:
            files_regenerated: True if any file was regenerated.
            directories_regenerated: True if any directory was regenerated.

        Returns:
            True if synthesis should be regenerated.
        """
        # If any files or directories were regenerated, synthesis must be regenerated
        if files_regenerated or directories_regenerated:
            return True

        # Check if synthesis.json exists
        synthesis_path = self.meta_path / "synthesis.json"
        if not synthesis_path.exists():
            return True

        return False
```

**File:** backend/src/oya/generation/orchestrator.py (L360-378)
```python
        # Phase 2: Files (run before directories to compute content hashes and collect summaries)
        file_pages, file_hashes, file_summaries = await self._run_files(
            analysis, progress_callback
        )
        for page in file_pages:
            await self._save_page(page)

        # Track if any files were regenerated (for cascade)
        files_regenerated = len(file_pages) > 0

        # Phase 3: Directories (uses file_hashes for signature computation and file_summaries for context)
        directory_pages, directory_summaries = await self._run_directories(
            analysis, file_hashes, progress_callback, file_summaries=file_summaries
        )
        for page in directory_pages:
            await self._save_page(page)

        # Track if any directories were regenerated (for cascade)
        directories_regenerated = len(directory_pages) > 0
```

**File:** backend/src/oya/generation/orchestrator.py (L380-419)
```python
        # Phase 4: Synthesis (combine file and directory summaries into SynthesisMap)
        # Cascade: regenerate synthesis if any files or directories were regenerated
        should_regenerate_synthesis = self._should_regenerate_synthesis(
            files_regenerated, directories_regenerated
        )

        if should_regenerate_synthesis:
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.SYNTHESIS,
                    step=0,
                    total_steps=1,
                    message="Synthesizing codebase understanding...",
                ),
            )
            synthesis_map = await self._run_synthesis(file_summaries, directory_summaries)
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.SYNTHESIS,
                    step=1,
                    total_steps=1,
                    message="Synthesis complete",
                ),
            )
        else:
            # Load existing synthesis map
            from oya.generation.synthesis import load_synthesis_map
            synthesis_map, _ = load_synthesis_map(str(self.meta_path))
            if synthesis_map is None:
                # Fallback: regenerate if loading fails
                await self._emit_progress(
                    progress_callback,
                    GenerationProgress(
                        phase=GenerationPhase.SYNTHESIS,
                        message="Synthesizing codebase understanding...",
                    ),
                )
                synthesis_map = await self._run_synthesis(file_summaries, directory_summaries)
```

**File:** backend/src/oya/generation/orchestrator.py (L421-467)
```python
        # Phase 5: Architecture (uses SynthesisMap as primary context)
        # Cascade: regenerate architecture only if synthesis was regenerated (Requirement 7.3, 7.5)
        if should_regenerate_synthesis:
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.ARCHITECTURE,
                    step=0,
                    total_steps=1,
                    message="Generating architecture page...",
                ),
            )
            architecture_page = await self._run_architecture(analysis, synthesis_map=synthesis_map)
            await self._save_page(architecture_page)
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.ARCHITECTURE,
                    step=1,
                    total_steps=1,
                    message="Architecture complete",
                ),
            )

        # Phase 6: Overview (uses SynthesisMap as primary context)
        # Cascade: regenerate overview only if synthesis was regenerated (Requirement 7.3, 7.5)
        if should_regenerate_synthesis:
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.OVERVIEW,
                    step=0,
                    total_steps=1,
                    message="Generating overview page...",
                ),
            )
            overview_page = await self._run_overview(analysis, synthesis_map=synthesis_map)
            await self._save_page(overview_page)
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.OVERVIEW,
                    step=1,
                    total_steps=1,
                    message="Overview complete",
                ),
            )
```

**File:** backend/src/oya/generation/orchestrator.py (L767-790)
```python
    async def _run_synthesis(
        self,
        file_summaries: list[FileSummary],
        directory_summaries: list[DirectorySummary],
    ) -> SynthesisMap:
        """Run synthesis phase to combine summaries into a SynthesisMap.

        Args:
            file_summaries: List of FileSummary objects from files phase.
            directory_summaries: List of DirectorySummary objects from directories phase.

        Returns:
            SynthesisMap containing aggregated codebase understanding.
        """
        # Generate the synthesis map
        synthesis_map = await self.synthesis_generator.generate(
            file_summaries=file_summaries,
            directory_summaries=directory_summaries,
        )

        # Save to synthesis.json
        save_synthesis_map(synthesis_map, str(self.meta_path))

        return synthesis_map
```

**File:** backend/src/oya/generation/architecture.py (L15-24)
```python
class ArchitectureGenerator:
    """Generates the repository architecture page.

    The architecture page provides system design documentation
    including component relationships, data flow, and diagrams.

    Supports two modes:
    1. Legacy mode: Uses key_symbols for architecture context
    2. Synthesis mode: Uses SynthesisMap for richer architecture context (preferred)
    """
```

**File:** backend/src/oya/generation/architecture.py (L36-66)
```python
    async def generate(
        self,
        file_tree: str,
        key_symbols: list[dict[str, Any]] | None = None,
        dependencies: list[str] | None = None,
        synthesis_map: SynthesisMap | None = None,
    ) -> GeneratedPage:
        """Generate the architecture page.

        Supports two modes:
        1. Legacy mode: Uses key_symbols for architecture context
        2. Synthesis mode: Uses SynthesisMap for richer architecture context

        Args:
            file_tree: String representation of file structure.
            key_symbols: Important symbols across the codebase (legacy mode).
            dependencies: List of project dependencies.
            synthesis_map: SynthesisMap with layer and component info (preferred).

        Returns:
            GeneratedPage with architecture content.
        """
        repo_name = self.repo.path.name

        prompt = get_architecture_prompt(
            repo_name=repo_name,
            file_tree=file_tree,
            key_symbols=key_symbols,
            dependencies=dependencies or [],
            synthesis_map=synthesis_map,
        )
```

**File:** backend/src/oya/generation/overview.py (L36-62)
```python
class OverviewGenerator:
    """Generates the repository overview page.

    The overview page provides a high-level introduction to the
    repository, including purpose, tech stack, and getting started.

    Supports two modes:
    1. Legacy mode: Uses README as primary context
    2. Synthesis mode: Uses SynthesisMap as primary context with README as supplementary
    """

    def __init__(self, llm_client, repo):
        """Initialize the overview generator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper for context.
        """
        self.llm_client = llm_client
        self.repo = repo

    async def generate(
        self,
        readme_content: str | None,
        file_tree: str,
        package_info: dict[str, Any],
        synthesis_map: SynthesisMap | None = None,
```

**File:** backend/tests/test_summaries.py (L1284-1292)
```python
class TestSynthesisBatchingForLargeInputs:
    """Property 9: Synthesis Batching for Large Inputs
    
    For any set of summaries exceeding the configured context limit, the 
    Synthesis_Generator SHALL process them in batches and produce a valid 
    merged Synthesis_Map without exceeding token limits in any single LLM call.
    
    Validates: Requirements 3.8
    """
```

