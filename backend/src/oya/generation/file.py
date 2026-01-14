# backend/src/oya/generation/file.py
"""File page generator."""

import logging
from pathlib import Path

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_file_prompt
from oya.generation.summaries import FileSummary, SummaryParser, path_to_slug

logger = logging.getLogger(__name__)


# Extension to language mapping for syntax highlighting
EXTENSION_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".sh": "bash",
    ".sql": "sql",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
}


class FileGenerator:
    """Generates file documentation pages."""

    def __init__(self, llm_client, repo):
        """Initialize the file generator.

        Args:
            llm_client: LLM client for generation.
            repo: Repository wrapper for context.
        """
        self.llm_client = llm_client
        self.repo = repo
        self._parser = SummaryParser()

    async def generate(
        self,
        file_path: str,
        content: str,
        symbols: list[dict],
        imports: list[str],
        architecture_summary: str,
    ) -> tuple[GeneratedPage, FileSummary]:
        """Generate documentation for a file.

        Args:
            file_path: Path to the file being documented.
            content: Content of the file.
            symbols: List of symbol dictionaries defined in the file.
            imports: List of import statements.
            architecture_summary: Summary of how this file fits in the architecture.

        Returns:
            Tuple of (GeneratedPage with file documentation, FileSummary extracted from output).
        """
        language = self._detect_language(file_path)

        prompt = get_file_prompt(
            file_path=file_path,
            content=content,
            symbols=symbols,
            imports=imports,
            architecture_summary=architecture_summary,
            language=language,
        )

        # First attempt
        generated_content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Parse the YAML summary block and get clean markdown
        clean_content, file_summary = self._parser.parse_file_summary(generated_content, file_path)

        # Check if parsing produced fallback (indicates failure)
        if file_summary.purpose == "Unknown":
            logger.warning(f"YAML parsing failed for {file_path}, retrying...")

            # Retry once with same prompt
            generated_content = await self.llm_client.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )
            clean_content, file_summary = self._parser.parse_file_summary(
                generated_content, file_path
            )

            if file_summary.purpose == "Unknown":
                logger.error(f"YAML parsing failed after retry for {file_path}")

        word_count = len(clean_content.split())
        slug = path_to_slug(file_path, include_extension=True)

        page = GeneratedPage(
            content=clean_content,
            page_type="file",
            path=f"files/{slug}.md",
            word_count=word_count,
            target=file_path,
        )

        return page, file_summary

    def _detect_language(self, file_path: str) -> str:
        """Detect the programming language from the file extension.

        Args:
            file_path: Path to the file.

        Returns:
            Language identifier for syntax highlighting.
        """
        ext = Path(file_path).suffix.lower()
        return EXTENSION_LANGUAGES.get(ext, "")
