# backend/src/oya/generation/overview.py
"""Overview page generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from oya.generation.prompts import SYSTEM_PROMPT, get_overview_prompt

if TYPE_CHECKING:
    from oya.generation.summaries import SynthesisMap


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
        purpose: Purpose of directory/file (used in incremental regen).
        layer: Architectural layer for file pages (used in incremental regen).
    """

    content: str
    page_type: str
    path: str
    word_count: int
    target: str | None = None
    source_hash: str | None = None
    purpose: str | None = None
    layer: str | None = None


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
        architecture_diagram: str = "",
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
            architecture_diagram: Pre-generated Mermaid diagram for architecture visualization.

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
            architecture_diagram=architecture_diagram,
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
