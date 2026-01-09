# backend/src/oya/generation/directory.py
"""Directory page generator."""

import re
from pathlib import Path

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_directory_prompt
from oya.generation.summaries import DirectorySummary, FileSummary, SummaryParser


class DirectoryGenerator:
    """Generates directory documentation pages."""

    def __init__(self, llm_client, repo):
        self.llm_client = llm_client
        self.repo = repo
        self._parser = SummaryParser()

    async def generate(
        self,
        directory_path: str,
        file_list: list[str],
        symbols: list[dict],
        architecture_context: str,
        file_summaries: list[FileSummary] | None = None,
    ) -> tuple[GeneratedPage, DirectorySummary]:
        """Generate directory documentation and extract summary.
        
        Args:
            directory_path: Path to the directory.
            file_list: List of files in the directory.
            symbols: List of symbol dictionaries defined in the directory.
            architecture_context: Summary of how this directory fits in the architecture.
            file_summaries: Optional list of FileSummary objects for files in the directory.
            
        Returns:
            A tuple of (GeneratedPage, DirectorySummary).
        """
        repo_name = self.repo.path.name

        prompt = get_directory_prompt(
            repo_name=repo_name,
            directory_path=directory_path,
            file_list=file_list,
            symbols=symbols,
            architecture_context=architecture_context,
            file_summaries=file_summaries or [],
        )

        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Parse the DirectorySummary from the LLM output
        clean_content, summary = self._parser.parse_directory_summary(
            content, directory_path
        )

        word_count = len(clean_content.split())
        slug = self._path_to_slug(directory_path)

        page = GeneratedPage(
            content=clean_content,
            page_type="directory",
            path=f"directories/{slug}.md",
            word_count=word_count,
            target=directory_path,
        )

        return page, summary

    def _path_to_slug(self, path: str) -> str:
        slug = path.replace("/", "-").replace("\\", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug.lower())
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")
