# Analysis of the Eight-Step Generation Pipeline

Based on my review of the codebase, here's an analysis of the current pipeline design, along with suggestions for improvements and missing features.

## Current Pipeline Overview

The eight phases are: **Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows → Indexing**. [1](#0-0) 

This follows a **bottom-up approach** that was intentionally designed to ensure high-quality documentation even when no README exists, because the LLM actually reads and understands the code before writing high-level docs. [2](#0-1) 

## What Works Well

### 1. **Bottom-Up Ordering (Phases 1-4)**
The progression from code analysis → files → directories → synthesis is well-designed. It ensures that higher-level documentation is informed by actual code understanding rather than speculation. [3](#0-2) 

### 2. **Cascade Regeneration**
The cascade behavior is elegant: if files change, synthesis regenerates; if synthesis regenerates, architecture/overview/workflows regenerate. This maintains consistency across documentation levels. [4](#0-3) 

### 3. **Incremental Regeneration**
Hash-based skip logic minimizes unnecessary LLM calls, which is important for cost control. [5](#0-4) 

## Areas for Improvement

### 1. **Phase 4 (Synthesis) is Not User-Facing**
Synthesis is a pure transformation phase that doesn't generate wiki content—it just creates the `SynthesisMap` JSON file. [6](#0-5) 

**Suggestion:** Consider whether synthesis should generate a user-visible "Synthesis" wiki page that explains the discovered architecture in natural language. This would make the intermediate understanding more transparent and debuggable.

### 2. **Phase 8 (Indexing) Feels Disconnected**
Indexing is treated as a separate phase after all generation is complete. [7](#0-6) 

**Suggestion:** Consider whether indexing should be:
- Streamed incrementally as pages are generated (reducing time-to-searchable)
- Or kept separate but made optional (allowing faster iteration during development)

### 3. **Limited Error Recovery**
The system has fallback behavior for parsing failures, but errors are only logged—they don't surface to users. [8](#0-7) 

**Suggestion:** Add a post-generation validation phase that:
- Checks for parse failures and missing summaries
- Validates that all required fields are present
- Reports quality metrics to the user

### 4. **Cascade is All-or-Nothing**
If any file changes, synthesis always regenerates, and if synthesis regenerates, all high-level docs regenerate. [9](#0-8) 

**Suggestion:** Consider finer-grained cascade logic:
- Track which layers/components changed in synthesis
- Only regenerate architecture sections affected by those changes
- Use partial document updates instead of full regeneration

### 5. **Workflow Discovery Depends on Synthesis**
Workflows use entry points discovered during synthesis, but there's no fallback if synthesis fails or produces poor entry point detection. [10](#0-9) 

**Suggestion:** Add a dedicated entry point discovery phase before synthesis that uses multiple heuristics (not just LLM analysis):
- Decorator-based detection (`@app.route`, `@click.command`, etc.)
- Main function detection
- Framework-specific patterns

## What's Missing

### 1. **Quality Validation Phase**
There's no automated verification that generated content is coherent, accurate, or complete. The system could add a phase that:
- Checks for broken internal links
- Validates mermaid diagram syntax
- Ensures all referenced files/symbols exist
- Compares generated summaries against actual code structure

### 2. **Metrics and Analytics**
No tracking of:
- Token usage per phase
- Generation time breakdown
- Quality scores or confidence levels
- Coverage metrics (% of code documented)

**Suggestion:** Add a metrics collection phase that records these statistics to help users understand costs and identify quality issues.

### 3. **User Feedback Integration**
The notes system exists for corrections, but notes don't trigger regeneration automatically—users must manually regenerate. [11](#0-10) 

**Suggestion:** Add a feedback-driven regeneration mode that:
- Monitors notes for patterns
- Suggests prompt improvements
- Optionally auto-regenerates pages with new notes

### 4. **Differential/Preview Mode**
No way to preview what would change before committing to a full regeneration.

**Suggestion:** Add a "dry run" mode that:
- Shows which files would regenerate
- Estimates token costs
- Previews structural changes to synthesis map

### 5. **Cross-Repository Context**
For monorepo or multi-repo projects, there's no way to share context between related codebases.

**Suggestion:** Add optional inter-repo linking that:
- Shares synthesis maps between related repos
- Links to external documentation
- Understands package dependencies across repos

### 6. **Code Quality Integration**
The system detects architectural issues but doesn't integrate with existing code quality tools.

**Suggestion:** Add a phase that:
- Imports linter warnings
- References test coverage data
- Links to CI/CD metrics
- Correlates documentation quality with code quality

## Recommended Phase Ordering Change

Consider reordering to: **Analysis → Files → Directories → Entry Point Discovery → Synthesis → Architecture → Overview → Workflows → Validation → Indexing**

This separates concerns better:
- Entry point discovery happens before synthesis (more reliable)
- Validation happens before indexing (don't index broken content)
- Indexing remains last but is based on validated content

## Notes

The current pipeline is well-designed for its core use case: generating comprehensive documentation from code with minimal configuration. The bottom-up approach is sound, and the cascade behavior ensures consistency.

However, the main gaps are around **observability** (understanding what happened), **quality assurance** (verifying correctness), and **flexibility** (selective regeneration). Adding validation, metrics, and preview capabilities would significantly improve the developer experience without changing the core architecture.

The design documents show this pipeline evolved through careful iteration [12](#0-11) , so these improvements should be considered evolutionary enhancements rather than fundamental redesigns.

### Citations

**File:** backend/src/oya/generation/orchestrator.py (L229-229)
```python
    Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows
```

**File:** backend/src/oya/generation/orchestrator.py (L324-348)
```python
    def _has_new_notes(self, target: str, generated_at: str | None) -> bool:
        """Check if there are notes created after the page was generated.

        Args:
            target: Target path to check for notes.
            generated_at: Timestamp when the page was last generated.

        Returns:
            True if there are new notes, False otherwise.
        """
        if not generated_at or not hasattr(self.db, "execute"):
            return False

        try:
            cursor = self.db.execute(
                """
                SELECT COUNT(*) FROM notes
                WHERE target = ? AND created_at > ?
                """,
                (target, generated_at),
            )
            row = cursor.fetchone()
            return row[0] > 0 if row else False
        except Exception:
            return False
```

**File:** backend/src/oya/generation/orchestrator.py (L376-404)
```python
    def _should_regenerate_file(
        self, file_path: str, content: str, file_hashes: dict[str, str]
    ) -> tuple[bool, str]:
        """Check if a file page needs regeneration.

        Args:
            file_path: Path to the source file.
            content: Content of the source file.
            file_hashes: Dict to store computed hashes (modified in place).

        Returns:
            Tuple of (should_regenerate, content_hash).
        """
        content_hash = compute_content_hash(content)
        file_hashes[file_path] = content_hash

        existing = self._get_existing_page_info(file_path, "file")
        if not existing:
            return True, content_hash

        # Check if content changed
        if existing.get("source_hash") != content_hash:
            return True, content_hash

        # Check if there are new notes
        if self._has_new_notes(file_path, existing.get("generated_at")):
            return True, content_hash

        return False, content_hash
```

**File:** backend/src/oya/generation/orchestrator.py (L439-467)
```python
    def _should_regenerate_synthesis(
        self,
        files_regenerated: bool,
        directories_regenerated: bool,
    ) -> bool:
        """Check if synthesis needs to be regenerated.

        Synthesis should be regenerated when:
        - Any file's documentation was regenerated (cascade from files)
        - Any directory's documentation was regenerated (cascade from directories)
        - No existing synthesis.json exists

        Args:
            files_regenerated: True if any file was regenerated.
            directories_regenerated: True if any directory was regenerated.

        Returns:
            True if synthesis should be regenerated.
        """
        # If any files or directories were regenerated, synthesis must be regenerated
        if files_regenerated or directories_regenerated:
            return True

        # Check if synthesis.json exists
        synthesis_path = self.meta_path / "synthesis.json"
        if not synthesis_path.exists():
            return True

        return False
```

**File:** backend/src/oya/generation/orchestrator.py (L478-482)
```python
        This bottom-up approach ensures that:
        - File documentation is generated first, extracting structured summaries
        - Directory documentation uses file summaries for context
        - Synthesis combines all summaries into a coherent codebase map
        - Architecture and Overview use the synthesis map for accurate context
```

**File:** backend/src/oya/generation/orchestrator.py (L484-486)
```python
        Cascade behavior (Requirement 7.2):
        - If any file is regenerated, synthesis is regenerated
        - If synthesis is regenerated, architecture and overview are regenerated
```

**File:** backend/src/oya/generation/orchestrator.py (L522-572)
```python
        # Phase 4: Synthesis (combine file and directory summaries into SynthesisMap)
        # Cascade: regenerate synthesis if any files or directories were regenerated
        should_regenerate_synthesis = self._should_regenerate_synthesis(
            files_regenerated, directories_regenerated
        )

        synthesis_map: SynthesisMap | None = None
        if should_regenerate_synthesis:
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.SYNTHESIS,
                    step=0,
                    total_steps=1,
                    message="Synthesizing codebase understanding...",
                ),
            )
            synthesis_map = await self._run_synthesis(
                file_summaries,
                directory_summaries,
                file_contents=analysis["file_contents"],
                all_symbols=analysis["symbols"],
            )
            await self._emit_progress(
                progress_callback,
                GenerationProgress(
                    phase=GenerationPhase.SYNTHESIS,
                    step=1,
                    total_steps=1,
                    message="Synthesis complete",
                ),
            )
        else:
            # Load existing synthesis map
            synthesis_map, _ = load_synthesis_map(str(self.meta_path))
            if synthesis_map is None:
                # Fallback: regenerate if loading fails
                await self._emit_progress(
                    progress_callback,
                    GenerationProgress(
                        phase=GenerationPhase.SYNTHESIS,
                        message="Synthesizing codebase understanding...",
                    ),
                )
                synthesis_map = await self._run_synthesis(
                    file_summaries,
                    directory_summaries,
                    file_contents=analysis["file_contents"],
                    all_symbols=analysis["symbols"],
                )

```

**File:** backend/src/oya/generation/orchestrator.py (L962-964)
```python
        # Use entry points from synthesis_map (already discovered during synthesis)
        if not synthesis_map or not synthesis_map.entry_points:
            return pages
```

**File:** .kiro/specs/bottom-up-generation/design.md (L1-13)
```markdown
# Design Document: Bottom-Up Wiki Generation

## Overview

This design refactors the wiki generation pipeline to use a bottom-up approach. Instead of generating Architecture and Overview pages first (which rely on README.md existing), the system will:

1. Generate file documentation first, extracting structured File_Summaries
2. Generate directory documentation, informed by File_Summaries
3. Synthesize all summaries into a Synthesis_Map
4. Generate Architecture and Overview using the Synthesis_Map as primary context

This ensures high-quality documentation even when no README exists, because the LLM has actually read and understood the code before writing high-level docs.

```

**File:** backend/src/oya/api/routers/repos.py (L536-577)
```python

        # Index wiki content for Q&A search (in staging)
        db.execute(
            """UPDATE generations
            SET current_phase = '8:indexing', current_step = 0, total_steps = 0
            WHERE id = ?""",
            (job_id,),
        )
        db.commit()

        # Use staging chroma path for indexing
        staging_chroma_path = staging_meta_path / "chroma"
        vectorstore = VectorStore(staging_chroma_path)
        indexing_service = IndexingService(
            vectorstore=vectorstore,
            db=staging_db,  # Use staging db for FTS content
            wiki_path=staging_wiki_path,
            meta_path=staging_meta_path,
        )

        # Progress callback for indexing
        async def indexing_progress_callback(step: int, total: int, message: str) -> None:
            db.execute(
                """
                UPDATE generations
                SET current_step = ?, total_steps = ?
                WHERE id = ?
                """,
                (step, total, job_id),
            )
            db.commit()

        # Clear old index and reindex with new content
        indexing_service.clear_index()
        await indexing_service.index_wiki_pages(
            embedding_provider=settings.active_provider,
            embedding_model=settings.active_model,
            progress_callback=indexing_progress_callback,
            synthesis_map=generation_result.synthesis_map,
            analysis_symbols=generation_result.analysis_symbols,
            file_imports=generation_result.file_imports,
        )
```

**File:** docs/plans/2026-01-14-phase7-synthesis-and-error-visibility-design.md (L116-156)
```markdown

### 2. Error Visibility

#### 2.1 Synthesis LLM Failures

**File:** `backend/src/oya/generation/synthesis.py`

Change silent exception handling in `_process_batch()`:

```python
# Before
except Exception:
    # On LLM failure, return the basic layer grouping
    pass

# After
except Exception as e:
    logger.error(
        "LLM call failed during synthesis, falling back to basic layer grouping. "
        f"Error: {type(e).__name__}: {e}"
    )
```

Add similar logging in `_parse_llm_response()` for JSON parse failures.

#### 2.2 Summary Fallback Logging

**File:** `backend/src/oya/generation/summaries.py`

Add logging to `_fallback_file_summary()`:

```python
def _fallback_file_summary(self, file_path: str) -> FileSummary:
    logger.warning(
        f"YAML parsing failed for {file_path}, using fallback summary "
        "(purpose='Unknown', layer='utility')"
    )
    return FileSummary(...)
```

Add similar logging to `_fallback_directory_summary()`.
```

