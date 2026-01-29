# Error Handling Improvements Design

## Problem

Errors are being silently discarded throughout the codebase, making debugging extremely difficult. Recent example: frontend silently discarded an error during wiki generation, causing the process to stop without any indication of why.

Two main issues:
1. **Silent error discarding** - `try/catch` with `pass` or empty catch blocks
2. **Generic exception catching** - `except Exception:` without trying specific exceptions first

## Solution

1. Add error handling policy to CLAUDE.md
2. Create frontend toast/modal notification system
3. Convert existing frontend error handling to use new system
4. Fix high-risk backend silent error handling

---

## Part 1: CLAUDE.md Policy

Add new "## Error Handling" section:

```markdown
## Error Handling

### Never Silently Discard Errors
Errors that disappear make debugging impossible. Every error must either:
1. **Propagate** - Let it bubble up to a handler that can deal with it
2. **Log** - Record what went wrong with context (file, operation, relevant data)
3. **Transform** - Convert to a user-visible error state or message

### Catch Specific Exceptions
```python
# BAD - catches everything including bugs
except Exception:
    pass

# GOOD - catches what you expect
except (FileNotFoundError, PermissionError) as e:
    logger.warning(f"Could not read {path}: {e}")
```

### When Generic Except is Acceptable
Only in these cases, and MUST include a comment explaining why:
1. **Resource cleanup in finally/close()** - Best-effort cleanup where failure doesn't matter
2. **Graceful degradation** - Feature works without this, AND you log the fallback
3. **Top-level handlers** - API endpoints, CLI entry points that must not crash

### Required Documentation for `pass` in Except
If you must use `pass`, the comment must explain:
- What errors are expected
- Why ignoring them is safe
- What the fallback behavior is

```python
# ACCEPTABLE - documented, specific scenario
except sqlite3.OperationalError:
    # Column already exists from previous migration - safe to ignore
    pass

# UNACCEPTABLE - no explanation
except Exception:
    pass
```

### Distinguish "No Results" from "Query Failed"
Never return empty collections on error - this hides failures:
```python
# BAD - caller can't tell if search failed or found nothing
except Exception:
    return []

# GOOD - caller knows something went wrong
except ChromaDBError as e:
    logger.error(f"Vector search failed: {e}")
    raise SearchError(f"Search unavailable: {e}") from e
```
```

---

## Part 2: Frontend Notification System

### Architecture

```
uiStore.ts (extended)
├── toasts: Toast[]           # Queue of toast notifications
├── errorModal: ErrorModal | null  # Current blocking error modal
├── addToast(message, type)   # Show non-blocking notification
├── dismissToast(id)          # Remove a toast
├── showErrorModal(title, message)  # Show blocking modal
└── dismissErrorModal()       # Close modal

components/
├── ToastContainer.tsx        # Renders toast queue (bottom-right corner)
├── ErrorModal.tsx            # Reusable modal (extracted from GenerationProgress)
└── App.tsx                   # Mounts ToastContainer and ErrorModal globally
```

### When to Use Which

| Scenario | UI | Example |
|----------|-----|---------|
| Background operation failed, app still works | Toast | "Couldn't refresh job status" |
| Feature degraded but usable | Toast | "Search unavailable, showing cached results" |
| User action failed | Toast | "Failed to save note" |
| Critical failure requiring acknowledgment | Modal | "Wiki generation failed: {error}" |
| Initialization failure blocking usage | Modal | "Could not connect to backend" |

### Toast Behavior
- Auto-dismiss after 5 seconds (configurable)
- Manual dismiss via X button
- Types: `error` (red), `warning` (yellow), `info` (blue)
- Stack up to 3 visible, queue the rest

---

## Part 3: Frontend Files to Convert

### 1. `stores/initialize.ts` - Silent error discards during app startup
```typescript
// Lines 58-60, 74-76
// Current:
} catch {
  // Ignore errors when checking generation status
}

// Convert to:
} catch (e) {
  useUIStore.getState().addToast('Could not check generation status', 'warning')
}
```

### 2. `stores/wikiStore.ts` - Mixed patterns
- Line 37-39: Already sets error state - add toast for visibility
- Line 46-48: Silent ignore for "wiki may not exist" - keep silent (expected case)

### 3. `stores/generationStore.ts` - Line 46-48
- Already sets `error` state - convert to use `showErrorModal()` since generation failure is critical

### 4. `components/GenerationProgress.tsx` - Lines 229-276
- Extract inline error modal to reusable `ErrorModal.tsx`
- Use `useUIStore.getState().showErrorModal()` instead

### 5. `main.tsx` - Line 8
```typescript
// Current:
void initializeApp().catch(console.error)

// Convert to:
void initializeApp().catch((e) => {
  useUIStore.getState().showErrorModal('Initialization Failed', e.message)
})
```

### Files to Leave Unchanged
- `api/client.ts` - SSE parsing errors logged to console (too noisy for toasts)
- `PageLoader.tsx` - Good inline error display for contextual errors
- `AskPanel.tsx` - Q&A errors should show inline in the panel

---

## Part 4: Backend High-Risk Fixes

### 1. `vectorstore/issues.py` - Query failures hidden as empty results

```python
# Lines 119-120 - query_issues()
except Exception as e:
    logger.error(f"Issue query failed: {e}")
    raise

# Lines 73-74 - delete_issues_for_file()
except Exception as e:
    logger.warning(f"Failed to delete issues for {file_path}: {e}")
```

### 2. `vectorstore/store.py` - Line 115-116
Keep as-is but add logging:
```python
except Exception as e:
    logger.debug(f"Cleanup error (non-critical): {e}")
```

### 3. `generation/orchestrator.py` - Multiple silent failures

```python
# Lines 330-331 - _get_cache_info()
except Exception as e:
    logger.warning(f"Failed to parse cache metadata: {e}")

# Lines 357-358 - _has_new_notes()
except Exception as e:
    logger.error(f"Database error checking notes: {e}")
    raise

# Lines 886-887, 899-900 - package metadata parsing
except (json.JSONDecodeError, KeyError) as e:
    logger.debug(f"Could not parse package.json: {e}")
except (tomllib.TOMLDecodeError, KeyError) as e:
    logger.debug(f"Could not parse pyproject.toml: {e}")

# Lines 1651-1653, 1714-1716 - Database recording
except sqlite3.OperationalError as e:
    if "no such table" in str(e):
        logger.debug("Page tracking table not yet created, skipping record")
    else:
        logger.error(f"Failed to record generated page: {e}")
        raise
```

### 4. `generation/prompts.py` - Line 1407-1408
```python
except Exception as e:
    logger.error(f"Failed to fetch notes from database: {e}")
    return []  # Graceful degradation OK, but now logged
```

### Lower Priority (Keep As-Is)
- `llm/client.py` - Logging failures shouldn't break app
- `db/migrations.py` - Migration edge cases acceptable
- `qa/service.py` - Graceful degradation for search fallbacks

---

## Implementation Order

| Step | Description | Files |
|------|-------------|-------|
| 1 | Add error handling policy to CLAUDE.md | `CLAUDE.md` |
| 2 | Extend uiStore with toast/modal state | `stores/uiStore.ts` |
| 3 | Create ToastContainer component | `components/ToastContainer.tsx` (new) |
| 4 | Extract ErrorModal component | `components/ErrorModal.tsx` (new) |
| 5 | Mount global components in App | `App.tsx` |
| 6 | Convert GenerationProgress to use ErrorModal | `components/GenerationProgress.tsx` |
| 7 | Convert initialize.ts to use toasts | `stores/initialize.ts` |
| 8 | Convert generationStore to use modal | `stores/generationStore.ts` |
| 9 | Convert wikiStore to use toasts | `stores/wikiStore.ts` |
| 10 | Convert main.tsx to use modal | `main.tsx` |
| 11 | Fix vectorstore/issues.py | `vectorstore/issues.py` |
| 12 | Fix vectorstore/store.py | `vectorstore/store.py` |
| 13 | Fix generation/orchestrator.py | `generation/orchestrator.py` |
| 14 | Fix generation/prompts.py | `generation/prompts.py` |

## Testing

- Frontend: Add tests for ToastContainer and ErrorModal components
- Frontend: Update existing tests that mock error scenarios
- Backend: Existing tests should still pass (adding logging, not changing behavior except for "raise" cases)
