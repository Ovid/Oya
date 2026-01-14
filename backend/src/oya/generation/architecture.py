# backend/src/oya/generation/architecture.py
"""Architecture page generator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from oya.generation.mermaid import DiagramGenerator
from oya.generation.mermaid_validator import validate_mermaid
from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_architecture_prompt

if TYPE_CHECKING:
    from oya.generation.summaries import SynthesisMap
    from oya.parsing.models import ParsedSymbol


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
        self.diagram_generator = DiagramGenerator()

    async def generate(
        self,
        file_tree: str,
        key_symbols: list[dict[str, Any]] | None = None,
        dependencies: list[str] | None = None,
        synthesis_map: SynthesisMap | None = None,
        file_imports: dict[str, list[str]] | None = None,
        symbols: list[ParsedSymbol] | None = None,
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
            file_imports: Dict mapping file paths to imported file paths (for diagrams).
            symbols: List of ParsedSymbol objects from parsing (for diagrams).

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

        # Generate and inject diagrams
        diagrams = self.diagram_generator.generate_all(
            synthesis_map=synthesis_map,
            file_imports=file_imports,
            symbols=symbols,
        )
        content = self._inject_diagrams(content, diagrams)

        word_count = len(content.split())

        return GeneratedPage(
            content=content,
            page_type="architecture",
            path="architecture.md",
            word_count=word_count,
        )

    def _inject_diagrams(
        self, content: str, diagrams: dict[str, str]
    ) -> str:
        """Inject validated Mermaid diagrams into the architecture content.

        Adds a "## Generated Diagrams" section at the end with each
        validated diagram in a mermaid code block.

        Args:
            content: The LLM-generated architecture content.
            diagrams: Dict mapping diagram name to Mermaid content.

        Returns:
            Content with diagrams appended.
        """
        validated_diagrams = []

        # Define diagram titles
        diagram_titles = {
            "layer": "System Layers",
            "dependency": "File Dependencies",
            "class": "Class Structure",
        }

        for name, diagram_content in diagrams.items():
            validation = validate_mermaid(diagram_content)
            if validation.valid:
                title = diagram_titles.get(name, name.title())
                validated_diagrams.append((title, diagram_content))

        if not validated_diagrams:
            return content

        # Append diagrams section
        lines = [content.rstrip(), "", "## Generated Diagrams", ""]

        for title, diagram_content in validated_diagrams:
            lines.append(f"### {title}")
            lines.append("")
            lines.append("```mermaid")
            lines.append(diagram_content)
            lines.append("```")
            lines.append("")

        return "\n".join(lines)
