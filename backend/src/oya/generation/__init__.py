# backend/src/oya/generation/__init__.py
"""Wiki generation pipeline module."""

from oya.generation.architecture import ArchitectureGenerator
from oya.generation.directory import DirectoryGenerator
from oya.generation.file import FileGenerator
from oya.generation.chunking import (
    Chunk,
    chunk_by_symbols,
    chunk_file_content,
    estimate_tokens,
)
from oya.generation.overview import (
    GeneratedPage,
    OverviewGenerator,
)
from oya.generation.prompts import (
    ARCHITECTURE_TEMPLATE,
    DIRECTORY_TEMPLATE,
    FILE_TEMPLATE,
    OVERVIEW_TEMPLATE,
    SYSTEM_PROMPT,
    WORKFLOW_TEMPLATE,
    PromptTemplate,
    get_architecture_prompt,
    get_directory_prompt,
    get_file_prompt,
    get_overview_prompt,
    get_workflow_prompt,
)
from oya.generation.workflows import (
    DiscoveredWorkflow,
    WorkflowDiscovery,
    WorkflowGenerator,
)

__all__ = [
    # Architecture Generator
    "ArchitectureGenerator",
    # Directory Generator
    "DirectoryGenerator",
    # File Generator
    "FileGenerator",
    # Chunking
    "Chunk",
    "chunk_by_symbols",
    "chunk_file_content",
    "estimate_tokens",
    # Overview Generator
    "GeneratedPage",
    "OverviewGenerator",
    # Prompts
    "ARCHITECTURE_TEMPLATE",
    "DIRECTORY_TEMPLATE",
    "FILE_TEMPLATE",
    "OVERVIEW_TEMPLATE",
    "SYSTEM_PROMPT",
    "WORKFLOW_TEMPLATE",
    "PromptTemplate",
    "get_architecture_prompt",
    "get_directory_prompt",
    "get_file_prompt",
    "get_overview_prompt",
    "get_workflow_prompt",
    # Workflow Discovery and Generation
    "DiscoveredWorkflow",
    "WorkflowDiscovery",
    "WorkflowGenerator",
]
