# JSONL Log Viewer Modal Design

## Overview

A modal dialog accessible from the TopBar that displays LLM query logs (`llm-queries.jsonl`) for the currently active repository. Provides entry-by-entry navigation, search, and log deletion.

## User Flow

1. User clicks log icon button in TopBar (visible when a repo is active)
2. Modal opens, fetching `llm-queries.jsonl` for the active repo
3. User navigates through entries using buttons or keyboard
4. User can search within logs, refresh, or delete all logs
5. User closes modal via X, clicking outside, or Escape

## Components

### New Files

**`frontend/src/components/LogViewerModal.tsx`**

Modal component containing:
- Modal wrapper with backdrop (pattern from `AddRepoModal`)
- Header with title, refresh button, delete button, close button
- Entry counter ("Entry 3 of 47")
- Navigation controls (First, Prev, Next, Last)
- Search input with find-next functionality
- JSON display area with syntax highlighting
- Keyboard event handling

### Modified Files

**`frontend/src/components/TopBar.tsx`**
- Add log icon button next to dark mode toggle
- State: `isLogViewerOpen` boolean
- Conditionally render button only when `activeRepo` exists
- Import and render `LogViewerModal`

## Backend API

### GET /api/repos/{repo_id}/logs/llm-queries

Fetches the raw JSONL content for the repo.

**Response (200):**
```json
{
  "content": "...",
  "size_bytes": 12345,
  "entry_count": 47
}
```

**Response (404):**
```json
{
  "detail": "No logs found"
}
```

Frontend parses JSONL into entries client-side.

### DELETE /api/repos/{repo_id}/logs/llm-queries

Deletes the log file.

**Response (200):**
```json
{
  "message": "Logs deleted"
}
```

**Response (404):**
```json
{
  "detail": "No logs to delete"
}
```

## UI States

### Normal State
- Entry counter visible
- Navigation buttons enabled/disabled based on position
- Search box functional
- Delete button visible

### Empty State (no logs)
- Message: "No LLM logs yet for this repository"
- Subtext: "Logs are created when you generate documentation or use Q&A"
- Navigation disabled
- Delete button hidden

### Delete Confirmation
- Inline confirmation replaces delete button
- Text: "Delete all LLM logs for this repo?"
- Cancel button (returns to normal)
- Delete button (red, performs deletion)

### Error State
- Error message displayed
- Retry button to re-fetch

## Styling

### Theme Integration (Tailwind)

```
Modal background: bg-white dark:bg-gray-800
Modal border: border-gray-200 dark:border-gray-700
Text: text-gray-900 dark:text-gray-100
Secondary text: text-gray-500 dark:text-gray-400
```

### JSON Syntax Highlighting

```
Keys: text-blue-600 dark:text-blue-400
Strings: text-amber-600 dark:text-amber-400
Numbers: text-green-600 dark:text-green-400
Booleans/null: text-purple-600 dark:text-purple-400
JSON background: bg-gray-900 dark:bg-gray-950
```

### Button Styles

```
Navigation: bg-indigo-600 hover:bg-indigo-700 text-white
Delete: bg-red-600 hover:bg-red-700 text-white
Disabled: opacity-50 cursor-not-allowed
```

### Modal Dimensions

```
Width: max-w-4xl (896px)
Height: max-h-[80vh]
JSON area: flex-1 overflow-y-auto
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `→` or `j` | Next entry |
| `←` or `k` | Previous entry |
| `Home` | First entry |
| `End` | Last entry |
| `Escape` | Close modal |
| `Enter` (in search) | Find next match |

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Network failure | Error message with Retry button |
| 404 response | Treated as empty state |
| Large files | Entry-by-entry nav keeps UI responsive |
| Parse error on line | Show error marker, continue to next |

## Implementation Notes

- No new Zustand store needed; state is local to modal
- Reuse modal backdrop/animation patterns from `AddRepoModal`
- Log icon: document or list icon from existing icon set
- Refresh loads fresh data without closing modal
