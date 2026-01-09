# backend/src/oya/generation/architecture.py
"""Architecture page generator."""

from pathlib import Path
from typing import Any

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_architecture_prompt


class ArchitectureGenerator:
    """Generates the repository architecture page.

    The architecture page provides system design documentation
    including component relationships, data flow, and diagrams.

    Supports two modes:
    1. Legacy mode: Uses key_symbols for architecture context
    2. Synthesis mode: Uses SynthesisMap for richer architecture context (preferred)
    """

    def __init__(self, llm_client, repo):
        """Initialize the architecture generator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper for context.
        """
        self.llm_client = llm_client
        self.repo = repo

    async def generate(
        self,
        file_tree: str,
        key_symbols: list[dict[str, Any]] | None = None,
        dependencies: list[str] | None = None,
        synthesis_map: Any = None,
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

        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        word_count = len(content.split())

        return GeneratedPage(
            content=content,
            page_type="architecture",
            path="architecture.md",
            word_count=word_count,
        )
