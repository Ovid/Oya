# backend/src/oya/generation/overview.py
"""Overview page generator."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oya.generation.prompts import SYSTEM_PROMPT, get_overview_prompt


@dataclass
class GeneratedPage:
    """Result of page generation.

    Attributes:
        content: Generated markdown content.
        page_type: Type of wiki page.
        path: Relative path for the wiki page.
        word_count: Number of words in content.
        target: Optional target (file/directory path).
        source_hash: Hash of source content (for incremental regeneration).
    """

    content: str
    page_type: str
    path: str
    word_count: int
    target: str | None = None
    source_hash: str | None = None


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
        package_info: dict,
        synthesis_map: Any = None,
    ) -> GeneratedPage:
        """Generate the overview page.

        Supports two modes:
        1. Legacy mode: Uses README as primary context
        2. Synthesis mode: Uses SynthesisMap as primary context with README as supplementary

        Args:
            readme_content: Content of README file (if any).
            file_tree: String representation of file structure.
            package_info: Package metadata dict.
            synthesis_map: SynthesisMap with layer and component info (preferred).

        Returns:
            GeneratedPage with overview content.
        """
        repo_name = self.repo.path.name

        prompt = get_overview_prompt(
            repo_name=repo_name,
            readme_content=readme_content or "",
            file_tree=file_tree,
            package_info=package_info,
            synthesis_map=synthesis_map,
        )

        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        word_count = len(content.split())

        return GeneratedPage(
            content=content,
            page_type="overview",
            path="overview.md",
            word_count=word_count,
        )
