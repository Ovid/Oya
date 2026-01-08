# backend/src/oya/generation/architecture.py
"""Architecture page generator."""

from pathlib import Path

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_architecture_prompt


class ArchitectureGenerator:
    """Generates the repository architecture page.

    The architecture page provides system design documentation
    including component relationships, data flow, and diagrams.
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
        key_symbols: list[dict],
        dependencies: list[str],
    ) -> GeneratedPage:
        """Generate the architecture page.

        Args:
            file_tree: String representation of file structure.
            key_symbols: Important symbols across the codebase.
            dependencies: List of project dependencies.

        Returns:
            GeneratedPage with architecture content.
        """
        repo_name = self.repo.path.name

        prompt = get_architecture_prompt(
            repo_name=repo_name,
            file_tree=file_tree,
            key_symbols=key_symbols,
            dependencies=dependencies,
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
