# Full Regeneration Option Design

## Summary

Add a generation mode toggle (incremental vs full) to the IndexingPreviewModal. Incremental remains the default and behaves as today. Full regeneration wipes all `.oyawiki` data except `.oyaignore` before running the standard pipeline, forcing a complete rebuild.

## User Flow

1. User clicks "Generate Wiki" in TopBar
2. IndexingPreviewModal opens with a **radio group** at the top:
   - **Incremental** (default): "Only regenerate changed files"
   - **Full**: "Wipe all data and regenerate from scratch"
3. If **Incremental** is selected: existing file tree is shown as normal
4. If **Full** is selected:
   - File tree is hidden (not relevant since everything regenerates)
   - Warning banner: "This will delete all existing wiki data (pages, database, vector store, notes) except .oyaignore. The entire wiki will be regenerated."
5. User clicks "Generate Wiki" button at bottom
6. Confirmation dialog reflects the selected mode
7. Generation proceeds

## Frontend Changes

### IndexingPreviewModal.tsx

- Add `generationMode` state: `"incremental" | "full"` (default `"incremental"`)
- Add radio group UI at top of modal body
- Conditionally render file tree (only for incremental) or warning banner (for full)
- Update `onGenerate` prop signature: `onGenerate: (mode: "incremental" | "full") => void`
- Pass mode when calling `onGenerate`

### TopBar.tsx

- Update `handleGenerate` to accept and forward the `mode` parameter
- Pass mode to `startGeneration()`

### api/client.ts

- Update `initRepo()` to accept optional `mode` parameter
- Send `mode` in POST body: `{ mode: "incremental" | "full" }`

### stores/generationStore.ts

- Update `startGeneration()` to accept optional `mode` parameter
- Pass to `initRepo(mode)`

## Backend Changes

### api/routers/repos.py

- Add request body model: `InitRequest` with `mode: Literal["incremental", "full"]` defaulting to `"incremental"`
- `init_repo()` accepts `InitRequest` body
- Pass mode to `_run_generation()`
- In `_run_generation()`, when `mode == "full"`:
  1. If production `.oyawiki` exists:
     - Save `.oyaignore` if it exists (from meta dir, not .oyawiki)
     - Delete the production `.oyawiki` directory
  2. `prepare_staging_directory()` runs as normal -- finds no production dir, creates empty staging
  3. Orchestrator runs against empty staging, regenerating everything

### No changes needed to:

- `orchestrator.py` -- already handles empty staging correctly
- `staging.py` -- existing logic works for both paths
- `repo_paths.py` -- no structural changes

## Key Design Decision

The "full" mode works by **wiping production before staging begins**, rather than adding a flag through the orchestrator. This is simpler because:
- The orchestrator already handles first-run (empty staging) correctly
- No need to bypass hash-checking logic
- The staging/promotion flow remains unchanged
- `.oyaignore` lives in the meta directory (not inside .oyawiki), so it survives naturally

## Files Modified

| File | Change |
|------|--------|
| `frontend/src/components/IndexingPreviewModal.tsx` | Radio group, conditional file tree, warning banner, updated callback |
| `frontend/src/components/TopBar.tsx` | Pass mode through onGenerate handler |
| `frontend/src/api/client.ts` | Add mode param to initRepo() |
| `frontend/src/stores/generationStore.ts` | Add mode param to startGeneration() |
| `backend/src/oya/api/routers/repos.py` | Accept mode, wipe production on full |
