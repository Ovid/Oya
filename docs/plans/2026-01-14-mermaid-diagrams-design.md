# Mermaid Diagram Generation Design

**Date:** 2026-01-14

**Problem:** LLM-generated Mermaid diagrams often have syntax errors (invalid node labels, unescaped characters, malformed syntax) that cause rendering failures in the frontend.

**Solution:** Replace LLM-generated diagrams with Python-generated ones, plus syntax validation.

---

## Architecture Overview

**Components:**

1. **MermaidGenerator** - New module that generates diagrams programmatically from analysis data
2. **MermaidValidator** - Validates Mermaid syntax before including in pages
3. **Updated prompts** - Tell LLM to describe architecture in prose, not generate diagrams

**Data flow:**
```
Analysis Phase → SynthesisMap → MermaidGenerator → Validated Diagrams → Architecture Page
                                      ↓
                              MermaidValidator (catches errors)
```

---

## MermaidGenerator Module

**Location:** `backend/src/oya/generation/mermaid.py`

**Three generator classes:**

1. **LayerDiagramGenerator** - Creates flowchart showing architectural layers
   - Input: `SynthesisMap` (has layers, components, dependencies)
   - Output: Flowchart TB with subgraphs per layer

2. **DependencyGraphGenerator** - Creates graph of file/module imports
   - Input: `file_imports` dict from analysis phase
   - Output: Flowchart LR showing import relationships

3. **ClassDiagramGenerator** - Creates class relationship diagrams
   - Input: `ParsedSymbol` objects (classes with methods)
   - Output: Mermaid classDiagram syntax

**Key design principle:** All node labels are sanitized - escape special characters, truncate long names, replace newlines.

```python
def sanitize_label(text: str, max_length: int = 40) -> str:
    """Make text safe for Mermaid node labels."""
    # Remove/escape problematic chars: (), [], {}, quotes, newlines
    # Truncate with ellipsis if too long
```

---

## MermaidValidator Module

**Location:** `backend/src/oya/generation/mermaid_validator.py`

**Approach:** Regex-based syntax validation (no external dependencies)

**Validates:**
1. **Diagram type declaration** - Must start with valid type (`flowchart`, `classDiagram`, `sequenceDiagram`, etc.)
2. **Balanced brackets** - All `[]`, `()`, `{}`, `""` properly paired
3. **Node ID format** - IDs contain only alphanumeric, underscore, hyphen
4. **Arrow syntax** - Valid connectors (`-->`, `---`, `-.->`, `==>`, etc.)
5. **Subgraph structure** - Every `subgraph` has matching `end`

**API:**
```python
@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]  # Human-readable error messages
    line_numbers: list[int]  # Which lines have issues

def validate_mermaid(content: str) -> ValidationResult:
    """Validate Mermaid diagram syntax."""
```

**Usage in generation:**
```python
diagram = generator.create_layer_diagram(synthesis_map)
result = validate_mermaid(diagram)
if not result.valid:
    logger.warning(f"Generated invalid diagram: {result.errors}")
    # Fall back to simpler diagram or omit
```

---

## Integration with Architecture Generation

**Changes to `architecture.py`:**

1. **Remove diagram generation from LLM prompt** - Update `get_architecture_prompt()` to ask for prose descriptions only, not Mermaid code

2. **Generate diagrams in Python** - After LLM returns content, inject validated diagrams

```python
async def generate(self, ..., synthesis_map: SynthesisMap) -> GeneratedPage:
    # 1. LLM generates prose content (no diagrams)
    content = await self.llm_client.generate(prompt=prompt, ...)

    # 2. Python generates diagrams from analysis data
    diagrams = self.diagram_generator.generate_all(
        synthesis_map=synthesis_map,
        file_imports=file_imports,
        symbols=symbols,
    )

    # 3. Validate each diagram
    validated_diagrams = []
    for name, diagram in diagrams.items():
        result = validate_mermaid(diagram)
        if result.valid:
            validated_diagrams.append((name, diagram))
        else:
            logger.warning(f"Skipping invalid {name}: {result.errors}")

    # 4. Inject diagrams into content at appropriate sections
    content = self._inject_diagrams(content, validated_diagrams)

    return GeneratedPage(content=content, ...)
```

**Diagram injection:** Insert diagrams after their corresponding prose sections (e.g., layer diagram after "Layer Architecture" heading).

---

## Updated Prompts

**Changes to `prompts.py`:**

Remove diagram generation instructions from architecture prompt. Change from:

```
3. **Component Diagram**: Create a Mermaid diagram showing the main components...
```

To:

```
3. **Component Relationships**: Describe the main components and how they interact
   (diagrams will be generated automatically from code analysis)
```

**Benefits:**
- LLM focuses on what it's good at: prose explanations, insights, patterns
- Diagrams are always syntactically valid
- Consistent diagram style across all generated wikis
- Faster generation (no LLM tokens spent on diagram syntax)

---

## Summary

| Component | Purpose |
|-----------|---------|
| `mermaid.py` | Three generators: LayerDiagram, DependencyGraph, ClassDiagram |
| `mermaid_validator.py` | Regex-based syntax validation with clear error messages |
| `architecture.py` | Integration: generate prose → generate diagrams → validate → inject |
| `prompts.py` | Remove diagram instructions, ask for prose only |

**Future enhancement:** Add `mermaid-cli` render validation as optional step.
