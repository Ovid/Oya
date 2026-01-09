"""Wiki page endpoints."""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from oya.api.deps import get_settings
from oya.config import Settings

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


class WikiPage(BaseModel):
    """Wiki page response."""
    content: str
    page_type: str
    path: str
    word_count: int
    source_path: str | None = None  # Original file/directory path for notes


class WikiTree(BaseModel):
    """Wiki tree structure."""
    overview: bool
    architecture: bool
    workflows: list[str]
    directories: list[str]
    files: list[str]


@router.get("/overview", response_model=WikiPage)
async def get_overview(
    settings: Settings = Depends(get_settings),
) -> WikiPage:
    """Get the overview page."""
    return _get_page(settings.wiki_path, "overview.md", "overview", None)


@router.get("/architecture", response_model=WikiPage)
async def get_architecture(
    settings: Settings = Depends(get_settings),
) -> WikiPage:
    """Get the architecture page."""
    return _get_page(settings.wiki_path, "architecture.md", "architecture", None)


@router.get("/workflows/{slug}", response_model=WikiPage)
async def get_workflow(
    slug: str,
    settings: Settings = Depends(get_settings),
) -> WikiPage:
    """Get a workflow page."""
    return _get_page(settings.wiki_path, f"workflows/{slug}.md", "workflow", slug)


@router.get("/directories/{slug}", response_model=WikiPage)
async def get_directory(
    slug: str,
    settings: Settings = Depends(get_settings),
) -> WikiPage:
    """Get a directory page."""
    return _get_page(settings.wiki_path, f"directories/{slug}.md", "directory", slug)


@router.get("/files/{slug}", response_model=WikiPage)
async def get_file(
    slug: str,
    settings: Settings = Depends(get_settings),
) -> WikiPage:
    """Get a file page."""
    return _get_page(settings.wiki_path, f"files/{slug}.md", "file", slug)


@router.get("/tree", response_model=WikiTree)
async def get_wiki_tree(
    settings: Settings = Depends(get_settings),
) -> WikiTree:
    """Get the wiki tree structure."""
    wiki_path = settings.wiki_path

    workflows = []
    directories = []
    files = []

    # Check workflows
    workflow_dir = wiki_path / "workflows"
    if workflow_dir.exists():
        workflows = [f.stem for f in workflow_dir.glob("*.md")]

    # Check directories
    dir_dir = wiki_path / "directories"
    if dir_dir.exists():
        directories = [f.stem for f in dir_dir.glob("*.md")]

    # Check files
    files_dir = wiki_path / "files"
    if files_dir.exists():
        files = [f.stem for f in files_dir.glob("*.md")]

    return WikiTree(
        overview=(wiki_path / "overview.md").exists(),
        architecture=(wiki_path / "architecture.md").exists(),
        workflows=sorted(workflows),
        directories=sorted(directories),
        files=sorted(files),
    )


def _get_page(wiki_path: Path, relative_path: str, page_type: str, slug: str | None = None) -> WikiPage:
    """Get a wiki page by path."""
    full_path = wiki_path / relative_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Page not found: {relative_path}")

    content = full_path.read_text(encoding="utf-8")
    word_count = len(content.split())

    # Extract source path from content title for file/directory pages
    source_path = None
    if page_type in ("file", "directory") and slug:
        # Try to extract from first heading (e.g., "# `lib/MooseX/Extended.pm`")
        for line in content.split("\n"):
            if line.startswith("# "):
                # Extract path from backticks or quotes
                import re
                match = re.search(r'[`"\']([^`"\']+)[`"\']', line)
                if match:
                    source_path = match.group(1)
                break

    return WikiPage(
        content=content,
        page_type=page_type,
        path=relative_path,
        word_count=word_count,
        source_path=source_path,
    )
