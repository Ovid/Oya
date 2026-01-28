# Synopsis Section for File Wiki Pages

**Date:** 2026-01-28
**Status:** Design Complete

## Overview

Add a "Synopsis" section to file wiki pages that shows developers how to *use* the code. The synopsis appears as section 2, immediately after "Purpose", showing caller-perspective code examples. Synopses are extracted from source documentation when available (Perl POD, Python docstrings, Rust doc examples, JSDoc), or AI-generated when missing.

## Goals

1. Provide quick, actionable code examples showing how to use each file's public API
2. Preserve existing synopses from source documentation (e.g., Perl's SYNOPSIS POD section)
3. Generate helpful synopses for languages/files that don't include them
4. Flag conflicts when extracted synopses diverge from actual code

## Section Structure

### Current File Page Sections

**Before:**
1. Purpose
2. Public API
3. Internal Details
4. Dependencies
5. Usage Examples

**After (with Synopsis):**
1. Purpose
2. **Synopsis** ← NEW
3. Public API (renumbered from 2)
4. Internal Details (renumbered from 3)
5. Dependencies (renumbered from 4)
6. Usage Examples (renumbered from 5)

### Synopsis Section Format

The Synopsis section contains:
- A code block with language-appropriate syntax highlighting
- Caller-perspective usage showing imports and basic API calls
- A marker indicating source: no marker (extracted from source) or "AI-Generated" (inferred by LLM)

**Example (extracted from source):**

```markdown
## 2. Synopsis

```python
from myproject.utils import validate_email, format_phone

is_valid = validate_email("user@example.com")
formatted = format_phone("5551234567")
```

**Example (AI-generated):**

```markdown
## 2. Synopsis

**AI-Generated Synopsis**

```java
import com.example.UserService;

UserService service = new UserService(config);
User user = service.findById(123);
service.updateEmail(user, "new@example.com");
```

## Synopsis Extraction Strategy

### Languages with Established Conventions

For languages with documentation conventions, attempt to extract existing synopses. If no synopsis is found, fall back to AI generation.

**Perl:**
- Look for POD `=head1 SYNOPSIS` or `=head2 SYNOPSIS` sections
- Fallback parser already detects `__END__` marker
- Extract content between `=head1 SYNOPSIS` and next `=head1`, `=head2`, or `=cut`
- If not found → AI-generate and mark "AI-Generated"

**Python:**
- Look in module-level docstrings for sections labeled "Example:", "Usage:", "Synopsis:", or containing code blocks
- Already captured via `ast.get_docstring()` in Python parser
- Parse docstring structure to identify example sections
- If not found → AI-generate and mark "AI-Generated"

**Rust:**
- Look for doc comments with `//! # Examples` followed by code blocks
- Extract code blocks (triple backticks) following that header
- If not found → AI-generate and mark "AI-Generated"

**JavaScript/TypeScript:**
- Look for JSDoc `@example` tags (requires parser enhancement)
- Extract code following `@example` tag until next JSDoc tag or end of comment
- If not found → AI-generate and mark "AI-Generated"

**All other languages:**
- No extraction attempted
- Always AI-generate and mark "AI-Generated"

## AI-Generated Synopsis Principles

When no synopsis is found in source documentation, the LLM generates one following these rules:

### Caller-Perspective Code

- Show how a **consumer** would import and use the public API
- Focus on the most common/important use case
- Include necessary imports at the top
- No setup boilerplate unless essential (no main functions, test assertions, or print statements)
- Keep it concise: typically 5-15 lines of code

### Examples by Language

**Python utility module:**
```python
from myproject.utils import validate_email, format_phone

# Validate email address
is_valid = validate_email("user@example.com")

# Format phone number
formatted = format_phone("5551234567")  # Returns "(555) 123-4567"
```

**Java class:**
```java
import com.example.UserService;

UserService service = new UserService(config);
User user = service.findById(123);
service.updateEmail(user, "new@example.com");
```

**TypeScript/React component:**
```typescript
import { Button } from './Button';

<Button variant="primary" onClick={handleClick}>
  Click Me
</Button>
```

## Conflict Handling

When a synopsis is extracted from source documentation but the actual code has diverged, detect and flag the conflict.

### Conflict Detection

During LLM generation phase (where both synopsis and parsed symbols are available):
- Compare symbols mentioned in synopsis code against parsed public API
- Check for: missing functions/classes, renamed symbols, signature mismatches
- Generate specific conflict notes

### Presentation

Show the original extracted synopsis unchanged, then add an inline note:

```markdown
## 2. Synopsis

```python
from mymodule import process_data

result = process_data(input_file, output_file)
```

**Note:** This synopsis may be outdated. The function `process_data` appears to have been renamed to `process_file` in the current code. Please verify the usage before relying on this example.
```

**Note characteristics:**
- Be specific about detected conflicts
- Keep it concise (1-2 sentences)
- Suggest verification rather than making absolute claims

## Implementation Plan

### 1. Data Model Changes

**File:** `backend/src/oya/parsing/models.py`

Add `synopsis` field to `ParsedFile`:

```python
@dataclass
class ParsedFile:
    path: str
    language: str
    symbols: list[ParsedSymbol]
    imports: list[str]
    exports: list[str]
    references: list[Reference]
    raw_content: str | None
    line_count: int
    metadata: dict
    synopsis: str | None = None  # NEW: Extracted synopsis code
```

### 2. Parser Enhancements

**Python Parser** (`backend/src/oya/parsing/python_parser.py`):
- Extract module-level docstring (already done)
- Add function to parse docstring for sections: "Example:", "Usage:", "Synopsis:", or code blocks
- Look for triple backticks or indented code blocks
- Return first matching section as synopsis
- Store in `ParsedFile.synopsis`

**Fallback Parser** (`backend/src/oya/parsing/fallback_parser.py`):
- **For Perl files:**
  - Add POD parsing logic
  - Look for `=head1 SYNOPSIS` or `=head2 SYNOPSIS`
  - Extract content until next `=head1`, `=head2`, or `=cut`
  - Clean up POD formatting (remove leading spaces, handle =over/=item lists)
- **For Rust files:**
  - Look for `//! # Examples` in doc comments
  - Extract code blocks (triple backticks) following that header

**TypeScript Parser** (`backend/src/oya/parsing/typescript_parser.py`):
- Currently doesn't extract JSDoc comments
- Add JSDoc parsing for `@example` tags
- Extract code following `@example` tag until next JSDoc tag or end of comment block

### 3. Prompt Template Changes

**File:** `backend/src/oya/generation/prompts.py`

Modify `FILE_TEMPLATE` (lines 449-528):
- Add Synopsis as section 2
- Renumber existing sections (Public API → 3, Internal Details → 4, Dependencies → 5, Usage Examples → 6)
- Add instructions for synopsis generation:
  - If extracted synopsis provided, include it verbatim
  - Check for conflicts between synopsis and parsed public API
  - If conflicts detected, add inline note describing discrepancies
  - If no extracted synopsis, generate caller-perspective code showing imports and usage
  - Mark AI-generated synopses with "**AI-Generated Synopsis**"
  - Keep synopsis concise (5-15 lines typically)

Modify `get_file_prompt()` function (lines 1185-1220):
- Add `synopsis: str | None = None` parameter
- Pass extracted synopsis to template if available

### 4. File Generator Changes

**File:** `backend/src/oya/generation/file.py`

Update `FileGenerator.generate()` method:
- Accept `synopsis` parameter from orchestrator
- Pass to `get_file_prompt()`
- LLM will handle synopsis generation/inclusion based on template instructions

### 5. Orchestrator Integration

**File:** `backend/src/oya/generation/orchestrator.py`

Update `generate_file_page()` (lines 1426-1457):
- Extract synopsis from parsed file: `parsed_file.synopsis`
- Pass to `FileGenerator.generate(synopsis=synopsis)`

## Edge Cases

### Files with No Public API

- Files with only private/internal functions
- Configuration files, constants-only files
- **Handling:** LLM determines if synopsis is appropriate; if no callable public API exists, may skip synopsis section or note "This file has no public API"

### Multi-Language Files

- `.tsx` files with TypeScript and JSX → Synopsis shows component usage, not just TS imports
- Python CLI applications → Synopsis shows command-line invocation, not just Python imports
- **Handling:** LLM adapts synopsis style to file's primary purpose

### Very Large APIs

- Files exporting 20+ functions/classes
- **Handling:**
  - Synopsis focuses on 2-3 most important functions
  - LLM uses `key_abstractions` from YAML frontmatter to prioritize
  - Keep synopsis under ~20 lines even for large APIs

### Non-Code Synopses

- Some documentation might have prose instead of code in Synopsis section
- **Validation:** Check if extracted content contains code-like patterns (imports, function calls, operators)
- If validation fails → Treat as "no synopsis found" and AI-generate instead

### Language Detection

- Use existing language detection from `FileGenerator.generate()` (line 60)
- Extracted synopses preserve their original language (Perl POD examples stay as Perl)
- AI-generated synopses match the file's detected language

## Testing Strategy

### Unit Tests

**Parser tests:**
- Test Python docstring extraction with various formats (Example:, Usage:, code blocks)
- Test Perl POD SYNOPSIS extraction with different POD structures
- Test Rust doc comment extraction
- Test JSDoc @example extraction
- Verify `ParsedFile.synopsis` field is populated correctly

**Generation tests:**
- Test synopsis section appears as section 2
- Test "AI-Generated Synopsis" marker appears when no source synopsis
- Test conflict detection and note generation
- Test synopsis omission for files with no public API

### Integration Tests

- Generate wikis for test repositories containing:
  - Perl modules with SYNOPSIS POD sections
  - Python modules with and without docstring examples
  - Files with outdated synopses (to test conflict detection)
  - Files with no public API
- Verify section numbering is correct
- Verify extracted vs. AI-generated synopses are marked correctly

## Success Criteria

1. Synopsis section appears as section 2 in all file wiki pages
2. Extracted synopses from Perl POD, Python docstrings, and Rust doc comments are preserved verbatim
3. Files without synopses receive AI-generated examples marked "AI-Generated Synopsis"
4. Conflicts between extracted synopses and current code are detected and flagged with specific inline notes
5. Section numbering updates correctly (Public API becomes 3, etc.)
6. Synopsis code blocks use appropriate language syntax highlighting

## Open Questions

None - design is complete and validated.

## References

- Example from request: Perl's `MooseX::Extended` SYNOPSIS section
- Existing file generation: `backend/src/oya/generation/file.py`
- Existing prompts: `backend/src/oya/generation/prompts.py`, FILE_TEMPLATE (lines 449-528)
- Parsing models: `backend/src/oya/parsing/models.py`
- Python parser: `backend/src/oya/parsing/python_parser.py`
- Fallback parser: `backend/src/oya/parsing/fallback_parser.py`
- TypeScript parser: `backend/src/oya/parsing/typescript_parser.py`
