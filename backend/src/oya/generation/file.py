# backend/src/oya/generation/file.py
"""File page generator."""

import re
from pathlib import Path

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_file_prompt


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

    async def generate(
        self,
        file_path: str,
        content: str,
        symbols: list[dict],
        imports: list[str],
        architecture_summary: str,
    ) -> GeneratedPage:
        """Generate documentation for a file.

        Args:
            file_path: Path to the file being documented.
            content: Content of the file.
            symbols: List of symbol dictionaries defined in the file.
            imports: List of import statements.
            architecture_summary: Summary of how this file fits in the architecture.

        Returns:
            GeneratedPage with file documentation content.
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

        generated_content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        word_count = len(generated_content.split())
        slug = self._path_to_slug(file_path)

        return GeneratedPage(
            content=generated_content,
            page_type="file",
            path=f"files/{slug}.md",
            word_count=word_count,
            target=file_path,
        )

    def _detect_language(self, file_path: str) -> str:
        """Detect the programming language from the file extension.

        Args:
            file_path: Path to the file.

        Returns:
            Language identifier for syntax highlighting.
        """
        ext = Path(file_path).suffix.lower()
        return EXTENSION_LANGUAGES.get(ext, "")

    def _path_to_slug(self, path: str) -> str:
        """Convert a file path to a URL-safe slug.

        Args:
            path: File path to convert.

        Returns:
            URL-safe slug string.
        """
        slug = path.replace("/", "-").replace("\\", "-").replace(".", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug.lower())
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")
