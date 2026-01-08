# backend/src/oya/generation/directory.py
"""Directory page generator."""

import re
from pathlib import Path

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_directory_prompt


class DirectoryGenerator:
    """Generates directory documentation pages."""

    def __init__(self, llm_client, repo):
        self.llm_client = llm_client
        self.repo = repo

    async def generate(
        self,
        directory_path: str,
        file_list: list[str],
        symbols: list[dict],
        architecture_context: str,
    ) -> GeneratedPage:
        repo_name = self.repo.path.name

        prompt = get_directory_prompt(
            repo_name=repo_name,
            directory_path=directory_path,
            file_list=file_list,
            symbols=symbols,
            architecture_context=architecture_context,
        )

        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        word_count = len(content.split())
        slug = self._path_to_slug(directory_path)

        return GeneratedPage(
            content=content,
            page_type="directory",
            path=f"directories/{slug}.md",
            word_count=word_count,
            target=directory_path,
        )

    def _path_to_slug(self, path: str) -> str:
        slug = path.replace("/", "-").replace("\\", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug.lower())
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")
