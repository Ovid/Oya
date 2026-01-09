"""Summary data models for bottom-up wiki generation.

These models capture structured information extracted from file and directory
documentation to enable synthesis into higher-level architecture understanding.
"""

import re
from dataclasses import dataclass, field

import yaml


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


@dataclass
class DirectorySummary:
    """Structured summary extracted from directory documentation.
    
    Captures the essential information about a directory/module including its purpose,
    contained files, and role in the overall system architecture.
    
    Attributes:
        directory_path: Path to the directory relative to repository root.
        purpose: One-sentence description of what the directory/module is responsible for.
        contains: List of files contained in the directory.
        role_in_system: Description of how this directory fits into the overall architecture.
    """
    
    directory_path: str
    purpose: str
    contains: list[str] = field(default_factory=list)
    role_in_system: str = ""



class SummaryParser:
    """Parses structured summaries from LLM-generated markdown.
    
    Extracts YAML summary blocks from markdown content and converts them
    to FileSummary or DirectorySummary objects. The YAML block is stripped
    from the returned markdown content.
    """
    
    # Regex pattern to match YAML blocks delimited by ---
    YAML_BLOCK_PATTERN = re.compile(
        r'^---\s*\n(.*?)\n---\s*\n?',
        re.MULTILINE | re.DOTALL
    )
    
    def parse_file_summary(
        self, 
        markdown: str, 
        file_path: str
    ) -> tuple[str, FileSummary]:
        """Parse File_Summary from markdown, return (clean_markdown, summary).
        
        Extracts the YAML block containing file_summary data from the markdown,
        parses it into a FileSummary object, and returns the markdown with the
        YAML block removed.
        
        Args:
            markdown: The full markdown content potentially containing a YAML block.
            file_path: The path to the file being summarized.
            
        Returns:
            A tuple of (clean_markdown, FileSummary) where clean_markdown has
            the YAML block removed.
        """
        # Try to extract YAML block
        match = self.YAML_BLOCK_PATTERN.search(markdown)
        
        if not match:
            # No YAML block found, return fallback
            return markdown, self._fallback_file_summary(file_path)
        
        yaml_content = match.group(1)
        
        try:
            data = yaml.safe_load(yaml_content)
            
            if not isinstance(data, dict) or 'file_summary' not in data:
                return markdown, self._fallback_file_summary(file_path)
            
            summary_data = data['file_summary']
            
            # Extract fields with defaults
            purpose = summary_data.get('purpose', 'Unknown')
            layer = summary_data.get('layer', 'utility')
            
            # Validate layer
            if layer not in VALID_LAYERS:
                layer = 'utility'
            
            key_abstractions = summary_data.get('key_abstractions', [])
            if not isinstance(key_abstractions, list):
                key_abstractions = []
            
            internal_deps = summary_data.get('internal_deps', [])
            if not isinstance(internal_deps, list):
                internal_deps = []
            
            external_deps = summary_data.get('external_deps', [])
            if not isinstance(external_deps, list):
                external_deps = []
            
            summary = FileSummary(
                file_path=file_path,
                purpose=purpose,
                layer=layer,
                key_abstractions=key_abstractions,
                internal_deps=internal_deps,
                external_deps=external_deps,
            )
            
            # Remove YAML block from markdown
            clean_markdown = self.YAML_BLOCK_PATTERN.sub('', markdown).strip()
            
            return clean_markdown, summary
            
        except yaml.YAMLError:
            # Malformed YAML, return fallback
            return markdown, self._fallback_file_summary(file_path)
    
    def _fallback_file_summary(self, file_path: str) -> FileSummary:
        """Create a fallback FileSummary with default values.
        
        Used when YAML parsing fails or no YAML block is found.
        """
        return FileSummary(
            file_path=file_path,
            purpose="Unknown",
            layer="utility",
            key_abstractions=[],
            internal_deps=[],
            external_deps=[],
        )

    def parse_directory_summary(
        self,
        markdown: str,
        directory_path: str
    ) -> tuple[str, DirectorySummary]:
        """Parse Directory_Summary from markdown, return (clean_markdown, summary).
        
        Extracts the YAML block containing directory_summary data from the markdown,
        parses it into a DirectorySummary object, and returns the markdown with the
        YAML block removed.
        
        Args:
            markdown: The full markdown content potentially containing a YAML block.
            directory_path: The path to the directory being summarized.
            
        Returns:
            A tuple of (clean_markdown, DirectorySummary) where clean_markdown has
            the YAML block removed.
        """
        # Try to extract YAML block
        match = self.YAML_BLOCK_PATTERN.search(markdown)
        
        if not match:
            # No YAML block found, return fallback
            return markdown, self._fallback_directory_summary(directory_path)
        
        yaml_content = match.group(1)
        
        try:
            data = yaml.safe_load(yaml_content)
            
            if not isinstance(data, dict) or 'directory_summary' not in data:
                return markdown, self._fallback_directory_summary(directory_path)
            
            summary_data = data['directory_summary']
            
            # Extract fields with defaults
            purpose = summary_data.get('purpose', 'Unknown')
            
            contains = summary_data.get('contains', [])
            if not isinstance(contains, list):
                contains = []
            
            role_in_system = summary_data.get('role_in_system', '')
            
            summary = DirectorySummary(
                directory_path=directory_path,
                purpose=purpose,
                contains=contains,
                role_in_system=role_in_system,
            )
            
            # Remove YAML block from markdown
            clean_markdown = self.YAML_BLOCK_PATTERN.sub('', markdown).strip()
            
            return clean_markdown, summary
            
        except yaml.YAMLError:
            # Malformed YAML, return fallback
            return markdown, self._fallback_directory_summary(directory_path)
    
    def _fallback_directory_summary(self, directory_path: str) -> DirectorySummary:
        """Create a fallback DirectorySummary with default values.
        
        Used when YAML parsing fails or no YAML block is found.
        """
        return DirectorySummary(
            directory_path=directory_path,
            purpose="Unknown",
            contains=[],
            role_in_system="",
        )
