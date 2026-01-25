# backend/src/oya/generation/file.py
"""File page generator."""

import logging
from pathlib import Path

from oya.config import EXTENSION_LANGUAGES
from oya.generation.mermaid import ClassDiagramGenerator, DependencyGraphGenerator
from oya.generation.mermaid_validator import validate_mermaid
from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_file_prompt
from oya.generation.summaries import FileSummary, SummaryParser, path_to_slug
from oya.parsing.models import ParsedSymbol

logger = logging.getLogger(__name__)


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
        self._class_diagram_gen = ClassDiagramGenerator()
        self._dep_diagram_gen = DependencyGraphGenerator()

    async def generate(
        self,
        file_path: str,
        content: str,
        symbols: list[dict],
        imports: list[str],
        architecture_summary: str,
        parsed_symbols: list[ParsedSymbol] | None = None,
        file_imports: dict[str, list[str]] | None = None,
        notes: list[dict] | None = None,
    ) -> tuple[GeneratedPage, FileSummary]:
        """Generate documentation for a file.

        Args:
            file_path: Path to the file being documented.
            content: Content of the file.
            symbols: List of symbol dictionaries defined in the file.
            imports: List of import statements.
            architecture_summary: Summary of how this file fits in the architecture.
            parsed_symbols: Optional list of ParsedSymbol objects for class diagrams.
            file_imports: Optional dict of all file imports for dependency diagrams.
            notes: Optional list of human-authored notes to incorporate into documentation.

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
            notes=notes,
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

        # Generate diagrams
        diagrams_md = self._generate_diagrams(file_path, parsed_symbols, file_imports)
        if diagrams_md:
            clean_content += diagrams_md

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

    def _generate_diagrams(
        self,
        file_path: str,
        parsed_symbols: list[ParsedSymbol] | None,
        file_imports: dict[str, list[str]] | None,
    ) -> str:
        """Generate Mermaid diagrams for the file.

        Only includes diagrams that are both valid AND useful.
        Skips diagrams that don't add value (e.g., classes with no methods,
        dependencies with no edges).

        Args:
            file_path: Path to the file being documented.
            parsed_symbols: Optional list of ParsedSymbol objects.
            file_imports: Optional dict of all file imports.

        Returns:
            Markdown string with diagrams, or empty string if no useful diagrams.
        """
        diagrams = []

        # Class diagram if we have parsed symbols with classes
        if parsed_symbols:
            class_diagram = self._class_diagram_gen.generate(parsed_symbols)
            if class_diagram:
                result = validate_mermaid(class_diagram)
                # Check both validity AND usefulness
                if result.valid and ClassDiagramGenerator.is_useful(class_diagram):
                    diagrams.append(("Class Structure", class_diagram))

        # Dependency diagram if we have import data
        if file_imports:
            dep_diagram = self._dep_diagram_gen.generate_for_file(file_path, file_imports)
            if dep_diagram:
                result = validate_mermaid(dep_diagram)
                # Check both validity AND usefulness
                if result.valid and DependencyGraphGenerator.is_useful(dep_diagram):
                    diagrams.append(("Dependencies", dep_diagram))

        if not diagrams:
            return ""

        lines = ["\n\n## Diagrams"]
        for title, diagram in diagrams:
            lines.append(f"\n### {title}\n")
            lines.append(f"```mermaid\n{diagram}\n```")

        return "\n".join(lines)
