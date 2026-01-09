"""Summary data models for bottom-up wiki generation.

These models capture structured information extracted from file and directory
documentation to enable synthesis into higher-level architecture understanding.
"""

from dataclasses import dataclass, field


# Valid layer classifications for code files
VALID_LAYERS = frozenset(["api", "domain", "infrastructure", "utility", "config", "test"])


@dataclass
class FileSummary:
    """Structured summary extracted from file documentation.
    
    Captures the essential information about a source file including its purpose,
    architectural layer, key abstractions, and dependencies.
    
    Attributes:
        file_path: Path to the source file relative to repository root.
        purpose: One-sentence description of what the file does.
        layer: Classification of code responsibility (api, domain, infrastructure, 
               utility, config, or test).
        key_abstractions: Primary classes, functions, or types defined in the file.
        internal_deps: Paths to other files in the repository that this file depends on.
        external_deps: External libraries or packages the file imports.
    """
    
    file_path: str
    purpose: str
    layer: str
    key_abstractions: list[str] = field(default_factory=list)
    internal_deps: list[str] = field(default_factory=list)
    external_deps: list[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate layer field after initialization."""
        if self.layer not in VALID_LAYERS:
            raise ValueError(
                f"Invalid layer '{self.layer}'. Must be one of: {', '.join(sorted(VALID_LAYERS))}"
            )
