"""Decorator pattern registry for reference and entry point detection.

This module defines patterns for framework decorators that:
1. Create references to types (e.g., FastAPI response_model=MyClass)
2. Mark symbols as entry points (e.g., route handlers, fixtures)

Parsers consult these patterns during AST traversal to extract
references that wouldn't otherwise be detected.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReferencePattern:
    """Pattern for decorators whose arguments create references.

    Attributes:
        decorator_name: Regex matching decorator name (e.g., "get|post|put").
        object_name: Regex matching object (e.g., "router|app"), None for bare decorators.
        arguments: Tuple of argument names that contain type references.
    """

    decorator_name: str
    object_name: str | None
    arguments: tuple[str, ...]


@dataclass(frozen=True)
class EntryPointPattern:
    """Pattern for decorators that mark symbols as externally invoked.

    Attributes:
        decorator_name: Regex matching decorator name.
        object_name: Regex matching object, None for bare decorators.
    """

    decorator_name: str
    object_name: str | None


# Registry keyed by language
REFERENCE_PATTERNS: dict[str, list[ReferencePattern]] = {
    "python": [
        # FastAPI/Starlette route handlers
        ReferencePattern(
            decorator_name=r"^(get|post|put|patch|delete|head|options|trace)$",
            object_name=r".*",  # router, app, or any object
            arguments=("response_model", "response_class"),
        ),
    ],
    "typescript": [],
}

ENTRY_POINT_PATTERNS: dict[str, list[EntryPointPattern]] = {
    "python": [
        # FastAPI/Starlette routes
        EntryPointPattern(
            decorator_name=r"^(get|post|put|patch|delete|head|options|trace)$",
            object_name=r".*",
        ),
        # pytest
        EntryPointPattern(decorator_name=r"^fixture$", object_name=r"^pytest$"),
        EntryPointPattern(decorator_name=r"^fixture$", object_name=None),  # bare @fixture
        EntryPointPattern(decorator_name=r"^parametrize$", object_name=r"^pytest\.mark$"),
        # Click CLI
        EntryPointPattern(decorator_name=r"^command$", object_name=r".*"),
        EntryPointPattern(decorator_name=r"^group$", object_name=r".*"),
        # Celery
        EntryPointPattern(decorator_name=r"^task$", object_name=r".*"),
        # SQLAlchemy events
        EntryPointPattern(decorator_name=r"^listens_for$", object_name=r"^event$"),
    ],
    "typescript": [],
}
