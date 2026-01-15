"""Tech stack detection from file summaries.

Aggregates external dependencies from FileSummaries and maps them to
known libraries using the techstack.yaml configuration.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from oya.generation.summaries import FileSummary


@lru_cache(maxsize=1)
def load_techstack_config() -> dict[str, Any]:
    """Load tech stack configuration from YAML file.

    Returns:
        Dictionary containing library mappings.
    """
    config_path = Path(__file__).parent.parent / "constants" / "techstack.yaml"
    with open(config_path) as f:
        result: dict[str, Any] = yaml.safe_load(f)
        return result


def detect_tech_stack(
    file_summaries: list[FileSummary],
) -> dict[str, dict[str, list[str]]]:
    """Detect technology stack from file summaries.

    Aggregates external_deps from all file summaries and maps known
    libraries to their language and category.

    Args:
        file_summaries: List of FileSummary objects with external_deps.

    Returns:
        Nested dict: {language: {category: [display_names]}}
        Example: {"python": {"web_framework": ["FastAPI"]}}
    """
    config = load_techstack_config()
    libraries = config.get("libraries", {})

    # Collect all external deps
    all_deps: set[str] = set()
    for summary in file_summaries:
        all_deps.update(summary.external_deps)

    # Map to known libraries
    result: dict[str, dict[str, list[str]]] = {}

    for dep in all_deps:
        # Normalize dependency name (lowercase, handle common variations)
        dep_normalized = dep.lower().replace("_", "-").replace("::", "-")

        if dep_normalized in libraries:
            lib_info = libraries[dep_normalized]
            language = lib_info["language"]
            category = lib_info["category"]
            display = lib_info["display"]

            if language not in result:
                result[language] = {}
            if category not in result[language]:
                result[language][category] = []
            if display not in result[language][category]:
                result[language][category].append(display)

    return result
