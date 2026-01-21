# Consolidate Wiki Generation UI - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate wiki generation to a single TopBar entry point and disable Q&A when no wiki exists.

**Architecture:** Remove the "Generate Documentation" button from PageLoader and replace with a welcoming message directing users to the TopBar. Add `hasWiki` check to AskPanel to disable input when no wiki exists.

**Tech Stack:** React, TypeScript, Tailwind CSS

---

## Task 1: Simplify PageLoader.tsx

**Files:**
- Modify: `frontend/src/components/PageLoader.tsx`

**Step 1: Remove unused state and imports**

Remove lines 18-20 (state declarations):
```tsx
  const [generatingJobId, setGeneratingJobId] = useState<string | null>(null)
  const [generationError, setGenerationError] = useState<string | null>(null)
  const [isStartingGeneration, setIsStartingGeneration] = useState(false)
```

Update line 13 to remove `startGeneration` from destructuring:
```tsx
  const { dispatch, refreshTree, refreshStatus, state } = useApp()
```

**Step 2: Remove handleGenerate function**

Delete lines 59-69:
```tsx
  const handleGenerate = async () => {
    setGenerationError(null)
    setIsStartingGeneration(true)
    const jobId = await startGeneration()
    if (jobId) {
      setGeneratingJobId(jobId)
    } else {
      // Generation failed to start
      setIsStartingGeneration(false)
    }
  }
```

**Step 3: Simplify handleGenerationComplete**

Update `handleGenerationComplete` (lines 71-95) to remove references to removed state. New version:
```tsx
  const handleGenerationComplete = useCallback(async () => {
    // Clear the current job from global state
    dispatch({ type: 'SET_CURRENT_JOB', payload: null })
    // Refresh the wiki tree, repo status, and reload the page
    await refreshTree()
    await refreshStatus()
    // Re-trigger page load
    setLoading(true)
    setNotFound(false)
    try {
      const data = await loadPage()
      setPage(data)
      dispatch({ type: 'SET_CURRENT_PAGE', payload: data })
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true)
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load page')
      }
    } finally {
      setLoading(false)
    }
  }, [loadPage, dispatch, refreshTree, refreshStatus])
```

**Step 4: Simplify handleGenerationError**

Update `handleGenerationError` (lines 97-106) to remove references to removed state. New version:
```tsx
  const handleGenerationError = useCallback(
    (_errorMessage: string) => {
      // Clear the current job from global state
      dispatch({ type: 'SET_CURRENT_JOB', payload: null })
    },
    [dispatch]
  )
```

**Step 5: Simplify generation progress check**

Update lines 108-120 to remove `generatingJobId` and `isStartingGeneration` checks:
```tsx
  // Show generation progress if a global job is running
  const activeJobId = state.currentJob?.status === 'running' ? state.currentJob.job_id : null
  if (activeJobId) {
    return (
      <GenerationProgress
        jobId={activeJobId}
        onComplete={handleGenerationComplete}
        onError={handleGenerationError}
      />
    )
  }
```

**Step 6: Replace notFound block with welcome message**

Replace the entire `if (notFound)` block (lines 132-185) with:
```tsx
  if (notFound) {
    return (
      <div className="text-center py-12">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
          />
        </svg>
        <h2 className="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
          Welcome to Ọya!
        </h2>
        <p className="mt-2 text-gray-600 dark:text-gray-400 max-w-md mx-auto">
          To get started, click <strong>Generate Wiki</strong> in the top bar.
        </p>
      </div>
    )
  }
```

**Step 7: Run TypeScript check**

Run: `cd /Users/poecurt/projects/oya/frontend && npm run build`
Expected: Build succeeds with no type errors

**Step 8: Commit**

```bash
git add frontend/src/components/PageLoader.tsx
git commit -m "refactor: remove duplicate Generate Documentation button from PageLoader

Single entry point for wiki generation via TopBar button.
Replaced with welcome message directing users to TopBar."
```

---

## Task 2: Update AskPanel.tsx to disable when no wiki

**Files:**
- Modify: `frontend/src/components/AskPanel.tsx`

**Step 1: Add hasWiki check**

After line 51 (`const isGenerating = ...`), add:
```tsx
  const hasWiki = state.wikiTree && state.wikiTree.length > 0
```

**Step 2: Add no-wiki banner**

After the existing generation banner (lines 219-224), add a new banner for no-wiki state:
```tsx
      {/* No wiki banner */}
      {!hasWiki && !isGenerating && (
        <div className="p-3 bg-yellow-50 dark:bg-yellow-900/20 text-yellow-800 dark:text-yellow-200 text-sm border-b border-yellow-200 dark:border-yellow-800">
          Generate a wiki first to enable Q&A.
        </div>
      )}
```

**Step 3: Update input disabled state**

Update line 325 to include `!hasWiki`:
```tsx
            disabled={isLoading || isGenerating || !hasWiki}
```

**Step 4: Update submit button disabled state**

Update line 330 to include `!hasWiki`:
```tsx
            disabled={isLoading || !question.trim() || isGenerating || !hasWiki}
```

**Step 5: Run TypeScript check**

Run: `cd /Users/poecurt/projects/oya/frontend && npm run build`
Expected: Build succeeds with no type errors

**Step 6: Run tests**

Run: `cd /Users/poecurt/projects/oya/frontend && npm run test`
Expected: All tests pass

**Step 7: Commit**

```bash
git add frontend/src/components/AskPanel.tsx
git commit -m "feat: disable Q&A input when no wiki exists

Shows yellow banner explaining wiki must be generated first.
Input and submit button disabled until wiki is available."
```

---

## Task 3: Manual verification

**Step 1: Start the dev server**

Run: `cd /Users/poecurt/projects/oya/frontend && npm run dev`

**Step 2: Verify no-wiki state**

1. Navigate to a repo without a generated wiki
2. Verify: Main content shows "Welcome to Ọya!" message with instruction to click "Generate Wiki" in top bar
3. Verify: No "Generate Documentation" button exists
4. Verify: Q&A panel shows yellow banner "Generate a wiki first to enable Q&A."
5. Verify: Q&A input is disabled

**Step 3: Verify generation still works**

1. Click "Generate Wiki" in TopBar
2. Verify: IndexingPreviewModal opens
3. Verify: Generation completes successfully
4. Verify: Q&A input becomes enabled after generation

---

## Audit Complete

`startGeneration` is still used by:
- `TopBar.tsx:19,208` - main Generate Wiki button
- `InterruptedGenerationBanner.tsx:4,13` - resume interrupted generation

No orphaned code. No further cleanup needed.
