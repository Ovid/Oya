# backend/src/oya/generation/directory.py
"""Directory page generator."""

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_directory_prompt
from oya.generation.summaries import (
    DirectorySummary,
    FileSummary,
    SummaryParser,
    path_to_slug,
)


class DirectoryGenerator:
    """Generates directory documentation pages."""

    def __init__(self, llm_client, repo):
        """Initialize the directory generator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper for context.
        """
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
        child_summaries: list[DirectorySummary] | None = None,
        project_name: str | None = None,
        notes: list[dict] | None = None,
    ) -> tuple[GeneratedPage, DirectorySummary]:
        """Generate directory documentation and extract summary.

        Args:
            directory_path: Path to the directory (empty string for root).
            file_list: List of files in the directory.
            symbols: List of symbol dictionaries defined in the directory.
            architecture_context: Summary of how this directory fits in the architecture.
            file_summaries: Optional list of FileSummary objects for files in the directory.
            child_summaries: Optional list of DirectorySummary objects for child directories.
            project_name: Optional project name for breadcrumb (defaults to repo name).
            notes: Optional list of human correction notes for this directory.

        Returns:
            A tuple of (GeneratedPage, DirectorySummary).
        """
        repo_name = self.repo.path.name
        proj_name = project_name or repo_name

        prompt = get_directory_prompt(
            repo_name=repo_name,
            directory_path=directory_path,
            file_list=file_list,
            symbols=symbols,
            architecture_context=architecture_context,
            file_summaries=file_summaries or [],
            subdirectory_summaries=child_summaries or [],
            project_name=proj_name,
            notes=notes,
        )

        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Parse the DirectorySummary from the LLM output
        clean_content, summary = self._parser.parse_directory_summary(content, directory_path)

        word_count = len(clean_content.split())

        # Handle root directory slug
        if directory_path:
            slug = path_to_slug(directory_path, include_extension=False)
        else:
            slug = "root"

        page = GeneratedPage(
            content=clean_content,
            page_type="directory",
            path=f"directories/{slug}.md",
            word_count=word_count,
            target=directory_path,
        )

        return page, summary
