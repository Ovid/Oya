# Design Document: Indexing Preview

## Overview

The Indexing Preview feature provides a modal UI that displays all directories and files that will be indexed during wiki generation. Users can selectively exclude items before generation, with exclusions persisted to `.oyawiki/.oyaignore`. The feature reuses existing `FileFilter` logic to guarantee the preview matches actual generation behavior.

## Architecture

The feature follows the existing Oya architecture pattern:
- Backend: Two new FastAPI endpoints in the repos router
- Frontend: New modal component triggered from TopBar
- State: Local component state for pending exclusions (no global state needed)

```mermaid
flowchart TB
    subgraph Frontend
        TB[TopBar] --> IPB[Preview Button]
        IPB --> IPM[IndexingPreviewModal]
        IPM --> Search[Search Input]
        IPM --> DirList[Directory List]
        IPM --> FileList[File List]
        IPM --> Actions[Save/Cancel Buttons]
        IPM --> Confirm[Confirmation Dialog]
    end
    
    subgraph Backend
        API[/api/repos/indexable] --> FF[FileFilter]
        API --> DE[Directory Extraction]
        POST[/api/repos/oyaignore] --> OI[.oyaignore Writer]
    end
    
    IPM -->|GET| API
    Actions -->|POST| POST
    FF --> Files[File List]
    DE --> Dirs[Directory List]
```

## Components and Interfaces

### Backend Components

#### GET `/api/repos/indexable` Endpoint

Returns the list of indexable directories and files using the same `FileFilter` class that `GenerationOrchestrator` uses.

```python
# In backend/src/oya/api/routers/repos.py

@router.get("/indexable", response_model=IndexableItems)
async def get_indexable_items(
    settings: Settings = Depends(get_settings),
) -> IndexableItems:
    """Get list of directories and files that will be indexed.
    
    Uses the same FileFilter class as GenerationOrchestrator to ensure
    the preview matches actual generation behavior.
    """
    pass
```

**Response Schema:**
```python
class IndexableItems(BaseModel):
    """Response for indexable items endpoint."""
    directories: list[str]  # Sorted alphabetically
    files: list[str]        # Sorted alphabetically
    total_directories: int
    total_files: int
```

#### POST `/api/repos/oyaignore` Endpoint

Appends new exclusions to `.oyawiki/.oyaignore`.

```python
@router.post("/oyaignore", response_model=OyaignoreUpdateResponse)
async def update_oyaignore(
    request: OyaignoreUpdateRequest,
    settings: Settings = Depends(get_settings),
) -> OyaignoreUpdateResponse:
    """Add exclusions to .oyawiki/.oyaignore."""
    pass
```

**Request/Response Schemas:**
```python
class OyaignoreUpdateRequest(BaseModel):
    """Request to add exclusions to .oyaignore."""
    directories: list[str]  # Will have trailing slash added
    files: list[str]

class OyaignoreUpdateResponse(BaseModel):
    """Response after updating .oyaignore."""
    added_directories: list[str]
    added_files: list[str]
    total_added: int
```

#### Directory Extraction Utility

Extract the directory derivation logic from `GenerationOrchestrator._run_directories` into a reusable function:

```python
# In backend/src/oya/repo/file_filter.py

def extract_directories_from_files(files: list[str]) -> list[str]:
    """Extract unique parent directories from a list of file paths.
    
    This replicates the logic from GenerationOrchestrator._run_directories
    to ensure consistency between preview and generation.
    
    Args:
        files: List of file paths.
        
    Returns:
        Sorted list of unique directory paths.
    """
    directories: set[str] = set()
    for file_path in files:
        parts = file_path.split("/")
        for i in range(1, len(parts)):
            dir_path = "/".join(parts[:i])
            directories.add(dir_path)
    return sorted(directories)
```

### Frontend Components

#### IndexingPreviewModal Component

Main modal component that displays the preview and handles exclusion selection.

```typescript
// frontend/src/components/IndexingPreviewModal.tsx

interface IndexingPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: () => void;  // Called after successful save to refresh state
}

interface IndexableItems {
  directories: string[];
  files: string[];
  total_directories: number;
  total_files: number;
}

interface PendingExclusions {
  directories: Set<string>;
  files: Set<string>;
}
```

**Component State:**
- `indexableItems`: Data from backend
- `pendingExclusions`: User's current selections
- `searchQuery`: Current search filter text
- `isLoading`: Loading state for fetch
- `isSaving`: Loading state for save
- `showConfirmation`: Whether to show save confirmation dialog

#### ConfirmationDialog Component

Reusable confirmation dialog for save action.

```typescript
interface ConfirmationDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}
```

### API Client Extensions

```typescript
// frontend/src/api/client.ts

export interface IndexableItems {
  directories: string[];
  files: string[];
  total_directories: number;
  total_files: number;
}

export interface OyaignoreUpdateRequest {
  directories: string[];
  files: string[];
}

export interface OyaignoreUpdateResponse {
  added_directories: string[];
  added_files: string[];
  total_added: number;
}

export async function getIndexableItems(): Promise<IndexableItems> {
  return fetchJson<IndexableItems>('/api/repos/indexable');
}

export async function updateOyaignore(
  request: OyaignoreUpdateRequest
): Promise<OyaignoreUpdateResponse> {
  return fetchJson<OyaignoreUpdateResponse>('/api/repos/oyaignore', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}
```

## Data Models

### Backend Pydantic Models

```python
# In backend/src/oya/api/schemas.py

class IndexableItems(BaseModel):
    """List of indexable directories and files."""
    directories: list[str]
    files: list[str]
    total_directories: int
    total_files: int

class OyaignoreUpdateRequest(BaseModel):
    """Request to update .oyaignore with new exclusions."""
    directories: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)

class OyaignoreUpdateResponse(BaseModel):
    """Response after updating .oyaignore."""
    added_directories: list[str]
    added_files: list[str]
    total_added: int
```

### Frontend TypeScript Types

```typescript
// In frontend/src/types/index.ts

export interface IndexableItems {
  directories: string[];
  files: string[];
  total_directories: number;
  total_files: number;
}

export interface OyaignoreUpdateRequest {
  directories: string[];
  files: string[];
}

export interface OyaignoreUpdateResponse {
  added_directories: string[];
  added_files: string[];
  total_added: number;
}
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Preview-Generation Consistency

*For any* repository file structure and `.oyaignore` configuration, the list of files returned by the `/api/repos/indexable` endpoint SHALL be identical to the list of files that `GenerationOrchestrator._run_analysis()` would process.

**Validates: Requirements 2.4, 7.7**

### Property 2: Alphabetical Sorting

*For any* list of directories and files returned by the indexable endpoint, both the directories array and files array SHALL be sorted in case-sensitive alphabetical order.

**Validates: Requirements 2.6, 2.7**

### Property 3: Shared Filtering Logic Consistency

*For any* repository state, the `/api/repos/indexable` endpoint SHALL use the exact same `FileFilter` instance configuration as `GenerationOrchestrator._run_analysis()`. This means both MUST:
1. Use the same `FileFilter` class from `oya.repo.file_filter`
2. Pass the same parameters (repo_path, max_file_size_kb, extra_excludes)
3. Call `get_files()` which internally applies all exclusion logic (default excludes, `.oyaignore` patterns, size limits, binary detection)

The endpoint SHALL NOT reimplement any filtering logic. If the existing `FileFilter` class cannot be directly reused, it MUST be refactored to enable sharing before this feature is implemented.

**Validates: Requirements 2.8, 2.9, 7.8, 7.2, 7.3**

### Property 4: Search Filter Correctness

*For any* list of items and any search query string, the filtered results SHALL contain only items where the full path contains the search query as a case-insensitive substring, and SHALL contain all such items.

**Validates: Requirements 2.11**

### Property 5: Count Accuracy After Exclusions

*For any* initial set of directories and files and any set of pending exclusions, the displayed counts SHALL equal the total items minus the excluded items (accounting for files hidden by directory exclusions).

**Validates: Requirements 2.13**

### Property 6: Directory Exclusion Hides Child Files

*For any* directory marked as pending exclusion, all files whose path starts with that directory path followed by "/" SHALL be hidden from the files list display.

**Validates: Requirements 3.2, 3.4**

### Property 7: Directory Toggle Round-Trip

*For any* initial state of the preview modal, checking a directory checkbox and then unchecking it SHALL restore the files list to its original state (files within that directory reappear).

**Validates: Requirements 3.3**

### Property 8: Directory Check Clears Child File Exclusions

*For any* set of pending file exclusions, when a directory is checked, all pending file exclusions for files within that directory SHALL be removed from the pending exclusions set.

**Validates: Requirements 3.5**

### Property 9: Append Preserves Existing Entries

*For any* existing `.oyaignore` content and any new exclusions (directories and files), after saving: (1) all original entries SHALL still be present, (2) new directory entries SHALL have trailing slashes, (3) new entries SHALL be appended at the end.

**Validates: Requirements 5.1, 5.2, 5.3, 8.2, 8.3**

### Property 10: Files Within Excluded Directories Not Saved

*For any* set of pending directory exclusions and pending file exclusions, when saving, files whose paths start with any excluded directory path SHALL NOT be written to `.oyaignore`.

**Validates: Requirements 5.4**

### Property 11: No Duplicate Entries

*For any* existing `.oyaignore` content and any new exclusions, after saving, the `.oyaignore` file SHALL NOT contain any duplicate entries.

**Validates: Requirements 8.5**

## Error Handling

### Backend Error Handling

| Error Condition | HTTP Status | Response |
|----------------|-------------|----------|
| Repository path invalid/inaccessible | 400 | `{"detail": "Repository path is invalid or inaccessible: {path}"}` |
| File enumeration fails | 500 | `{"detail": "Failed to enumerate files: {error}"}` |
| Permission denied writing .oyaignore | 403 | `{"detail": "Permission denied writing to .oyaignore"}` |
| Cannot create .oyawiki directory | 500 | `{"detail": "Failed to create .oyawiki directory: {error}"}` |

### Frontend Error Handling

- Display error toast when API calls fail
- Show retry button for transient errors
- Disable Save button if backend is unreachable
- Show specific error messages from backend responses

## Testing Strategy

### Unit Tests

Unit tests verify specific examples and edge cases:

**Backend:**
- Test `extract_directories_from_files()` with known inputs
- Test `/api/repos/indexable` returns correct structure
- Test `/api/repos/oyaignore` creates file if missing
- Test trailing slash is added to directory patterns
- Test error responses for invalid paths

**Frontend:**
- Test modal opens/closes correctly
- Test search input filters list
- Test checkbox interactions update state
- Test confirmation dialog appears before save
- Test counts update when items are excluded

### Property-Based Tests

Property-based tests verify universal properties across many generated inputs using Hypothesis (Python) for backend tests.

**Configuration:**
- Minimum 100 iterations per property test
- Use Hypothesis for Python backend tests
- Each test tagged with property reference

**Backend Property Tests:**
- Property 1: Generate random file structures, compare indexable endpoint output with FileFilter.get_files()
- Property 2: Generate random file lists, verify sorting
- Property 3: Generate random .oyaignore patterns and file structures, verify exclusions
- Property 9: Generate random existing content and new exclusions, verify append behavior
- Property 10: Generate random directory/file exclusion combinations, verify files within dirs not saved
- Property 11: Generate random existing content with potential duplicates, verify no duplicates after save

**Frontend Property Tests (if applicable):**
- Property 4: Generate random item lists and search queries, verify filter correctness
- Property 5: Generate random exclusion sets, verify count accuracy
- Property 6: Generate random directory structures, verify child files hidden
- Property 7: Generate random toggle sequences, verify round-trip
- Property 8: Generate random file exclusions and directory checks, verify cleanup

