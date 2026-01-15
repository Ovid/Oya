"""Code metrics computation from file summaries.

Computes quantitative metrics about codebase size and distribution
across architectural layers.
"""

from __future__ import annotations

from collections import defaultdict

from oya.generation.summaries import CodeMetrics, FileSummary


def compute_code_metrics(
    file_summaries: list[FileSummary],
    file_contents: dict[str, str],
) -> CodeMetrics:
    """Compute code metrics from analyzed files.

    Args:
        file_summaries: List of FileSummary objects with layer classifications.
        file_contents: Mapping of file paths to their contents for LOC counting.

    Returns:
        CodeMetrics with file counts and lines of code by layer.
    """
    files_by_layer: dict[str, int] = defaultdict(int)
    lines_by_layer: dict[str, int] = defaultdict(int)

    for summary in file_summaries:
        layer = summary.layer
        files_by_layer[layer] += 1

        content = file_contents.get(summary.file_path, "")
        if content:
            loc = len(content.splitlines())
            lines_by_layer[layer] += loc

    return CodeMetrics(
        total_files=len(file_summaries),
        files_by_layer=dict(files_by_layer),
        lines_by_layer=dict(lines_by_layer),
        total_lines=sum(lines_by_layer.values()),
    )
