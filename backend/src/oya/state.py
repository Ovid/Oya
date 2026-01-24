"""Global application state for active repo."""

from __future__ import annotations

from typing import Optional


class AppState:
    """Application state singleton."""

    _instance: Optional["AppState"] = None

    def __new__(cls) -> "AppState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._active_repo_id = None
        return cls._instance

    @property
    def active_repo_id(self) -> Optional[int]:
        return self._active_repo_id

    @active_repo_id.setter
    def active_repo_id(self, value: Optional[int]) -> None:
        self._active_repo_id = value


def get_app_state() -> AppState:
    """Get the application state singleton."""
    return AppState()


def reset_app_state() -> None:
    """Reset the application state (for testing)."""
    AppState._instance = None
