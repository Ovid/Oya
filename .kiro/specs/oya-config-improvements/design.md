# Design Document: Oya Configuration Improvements

## Overview

This design addresses three improvements to Oya's configuration and usability:
1. Relocating the `.oyaignore` file from the repository root to `.oyawiki/.oyaignore`
2. Auto-initializing the `.oyawiki/` directory structure on backend startup
3. Adding a directory picker to the TopBar for switching workspaces at runtime

The changes span both backend (Python/FastAPI) and frontend (React/TypeScript) components, with a focus on maintaining security through path validation and providing a smooth user experience.

## Architecture

```mermaid
flowchart TB
    subgraph Frontend
        TopBar[TopBar Component]
        DirectoryPicker[Directory Picker]
        AppContext[App Context]
    end
    
    subgraph Backend
        Main[main.py Startup]
        WorkspaceInit[Workspace Initializer]
        ReposRouter[/api/repos/workspace]
        FileFilter[FileFilter]
        Config[Settings]
    end
    
    subgraph Storage
        OyaWiki[.oyawiki/]
        OyaIgnore[.oyawiki/.oyaignore]
    end
    
    Main -->|on startup| WorkspaceInit
    WorkspaceInit -->|creates| OyaWiki
    TopBar --> DirectoryPicker
    DirectoryPicker -->|POST /api/repos/workspace| ReposRouter
    ReposRouter -->|validates path| Config
    ReposRouter -->|reinitializes| WorkspaceInit
    FileFilter -->|reads| OyaIgnore
    AppContext -->|refreshes on switch| TopBar
```

## Components and Interfaces

### 1. Workspace Initializer (New Module)

A new module `backend/src/oya/workspace.py` that handles workspace initialization.

```python
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def initialize_workspace(workspace_path: Path) -> bool:
    """Initialize the .oyawiki directory structure.
    
    Creates the following structure if it doesn't exist:
    .oyawiki/
    ├── wiki/
    ├── notes/
    ├── meta/
    ├── index/
    ├── cache/
    └── config/
    
    Args:
        workspace_path: Root path of the workspace/repository.
        
    Returns:
        True if initialization succeeded, False otherwise.
    """
    oyawiki_path = workspace_path / ".oyawiki"
    
    subdirs = ["wiki", "notes", "meta", "index", "cache", "config"]
    
    try:
        for subdir in subdirs:
            (oyawiki_path / subdir).mkdir(parents=True, exist_ok=True)
        return True
    except OSError as e:
        logger.error(f"Failed to initialize workspace: {e}")
        return False
```

### 2. FileFilter Modification

Update `backend/src/oya/repo/file_filter.py` to read from `.oyawiki/.oyaignore`:

```python
# Change from:
oyaignore = repo_path / ".oyaignore"

# To:
oyaignore = repo_path / ".oyawiki" / ".oyaignore"
```

### 3. Backend Startup Hook

Modify `backend/src/oya/main.py` to initialize workspace on startup:

```python
from contextlib import asynccontextmanager
from oya.config import load_settings
from oya.workspace import initialize_workspace

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize workspace
    settings = load_settings()
    initialize_workspace(settings.workspace_path)
    yield
    # Shutdown: cleanup if needed

app = FastAPI(
    title="Oya",
    lifespan=lifespan,
    # ...
)
```

### 4. Workspace Switching API

New endpoint in `backend/src/oya/api/routers/repos.py`:

```python
from pydantic import BaseModel

class WorkspaceSwitch(BaseModel):
    path: str

class WorkspaceSwitchResponse(BaseModel):
    status: RepoStatus
    message: str

@router.post("/workspace", response_model=WorkspaceSwitchResponse)
async def switch_workspace(
    request: WorkspaceSwitch,
    settings: Settings = Depends(get_settings),
) -> WorkspaceSwitchResponse:
    """Switch to a different workspace directory."""
    # Implementation details in Data Models section
```

### 5. Path Validation Utility

New utility in `backend/src/oya/api/deps.py` for secure path validation:

```python
from pathlib import Path
import os

def get_workspace_base_path() -> Path:
    """Get the allowed base path for workspaces."""
    base = os.getenv("WORKSPACE_BASE_PATH")
    if base:
        return Path(base).resolve()
    return Path.home()

def validate_workspace_path(path: str, base_path: Path) -> tuple[bool, str, Path | None]:
    """Validate a workspace path is safe and within allowed bounds.
    
    Args:
        path: The requested workspace path.
        base_path: The allowed base path.
        
    Returns:
        Tuple of (is_valid, error_message, resolved_path).
    """
    try:
        requested = Path(path).resolve()
    except (ValueError, OSError) as e:
        return False, f"Invalid path: {e}", None
    
    if not requested.exists():
        return False, "Path does not exist", None
    
    if not requested.is_dir():
        return False, "Path is not a directory", None
    
    # Security: ensure path is under base_path
    try:
        requested.relative_to(base_path)
    except ValueError:
        return False, "Path is outside allowed workspace area", None
    
    return True, "", requested
```

### 6. Frontend Directory Picker Component

New component `frontend/src/components/DirectoryPicker.tsx`:

```typescript
interface DirectoryPickerProps {
  currentPath: string;
  onSwitch: (path: string) => Promise<void>;
  disabled: boolean;
  disabledReason?: string;
}

export function DirectoryPicker({ 
  currentPath, 
  onSwitch, 
  disabled,
  disabledReason 
}: DirectoryPickerProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [inputValue, setInputValue] = useState(currentPath);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Component implementation
}
```

### 7. TopBar Integration

Update `frontend/src/components/TopBar.tsx` to include the directory picker:

```typescript
export function TopBar({ onToggleSidebar, onToggleRightSidebar }: TopBarProps) {
  const { state, switchWorkspace, refreshStatus, refreshTree } = useApp();
  const { repoStatus, currentJob, isLoading, noteEditor } = state;
  
  const isGenerating = currentJob?.status === 'running';
  const hasUnsavedChanges = noteEditor.isDirty; // Track actual dirty state
  
  const handleWorkspaceSwitch = async (path: string) => {
    if (hasUnsavedChanges) {
      const confirmed = window.confirm(
        'You have unsaved changes. Are you sure you want to switch workspaces?'
      );
      if (!confirmed) return;
    }
    await switchWorkspace(path);
  };
  
  // Render with DirectoryPicker
}
```

### 8. AppContext Updates

Add workspace switching and dirty state tracking to `frontend/src/context/AppContext.tsx`:

```typescript
// Update NoteEditorState to track dirty state
interface NoteEditorState {
  isOpen: boolean;
  isDirty: boolean;  // Track unsaved changes
  defaultScope: NoteScope;
  defaultTarget: string;
}

// Add new action type
type Action =
  // ... existing actions
  | { type: 'SET_NOTE_EDITOR_DIRTY'; payload: boolean };

// Update reducer to handle dirty state
case 'SET_NOTE_EDITOR_DIRTY':
  return {
    ...state,
    noteEditor: { ...state.noteEditor, isDirty: action.payload },
  };
case 'CLOSE_NOTE_EDITOR':
  return {
    ...state,
    noteEditor: { ...state.noteEditor, isOpen: false, isDirty: false },
  };

interface AppContextValue {
  // ... existing
  switchWorkspace: (path: string) => Promise<void>;
  setNoteEditorDirty: (isDirty: boolean) => void;
}

const switchWorkspace = async (path: string) => {
  dispatch({ type: 'SET_LOADING', payload: true });
  dispatch({ type: 'SET_ERROR', payload: null });
  
  try {
    const result = await api.switchWorkspace(path);
    dispatch({ type: 'SET_REPO_STATUS', payload: result.status });
    dispatch({ type: 'SET_CURRENT_PAGE', payload: null });
    await refreshTree();
  } catch (err) {
    const message = err instanceof api.ApiError 
      ? err.message 
      : 'Failed to switch workspace';
    dispatch({ type: 'SET_ERROR', payload: message });
    throw err;
  } finally {
    dispatch({ type: 'SET_LOADING', payload: false });
  }
};

const setNoteEditorDirty = (isDirty: boolean) => {
  dispatch({ type: 'SET_NOTE_EDITOR_DIRTY', payload: isDirty });
};
```

### 9. API Client Extension

Add to `frontend/src/api/client.ts`:

```typescript
export interface WorkspaceSwitchRequest {
  path: string;
}

export interface WorkspaceSwitchResponse {
  status: RepoStatus;
  message: string;
}

export async function switchWorkspace(
  path: string
): Promise<WorkspaceSwitchResponse> {
  return fetchJson<WorkspaceSwitchResponse>('/api/repos/workspace', {
    method: 'POST',
    body: JSON.stringify({ path }),
  });
}
```

## Data Models

### Backend Schemas

Add to `backend/src/oya/api/schemas.py`:

```python
class WorkspaceSwitch(BaseModel):
    """Request to switch workspace."""
    path: str = Field(..., description="Absolute path to the new workspace directory")

class WorkspaceSwitchResponse(BaseModel):
    """Response after switching workspace."""
    status: RepoStatus
    message: str
```

### Frontend Types

Add to `frontend/src/types/index.ts`:

```typescript
export interface WorkspaceSwitchRequest {
  path: string;
}

export interface WorkspaceSwitchResponse {
  status: RepoStatus;
  message: string;
}
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Workspace Initialization Creates Directory Structure

*For any* valid workspace path that does not contain a `.oyawiki/` directory, calling `initialize_workspace()` SHALL create the `.oyawiki/` directory with all required subdirectories (wiki, notes, meta, index, cache, config).

**Validates: Requirements 2.2**

### Property 2: Invalid Path Rejection

*For any* path string that either does not exist on the filesystem OR exists but is not a directory, the workspace switch endpoint SHALL return a 400 error response.

**Validates: Requirements 4.6, 4.7**

### Property 3: Base Path Security Enforcement

*For any* path string, after resolving to its canonical form, if the path is not under the configured `WORKSPACE_BASE_PATH` (or user home directory if unconfigured), the workspace switch endpoint SHALL return a 403 error response.

**Validates: Requirements 4.9, 4.11**

### Property 4: Path Canonicalization Security

*For any* path string containing symlinks, `..` segments, or other path traversal patterns, the system SHALL resolve the path to its canonical form before validation. If the canonical path of a symlink target is outside the allowed base path, the system SHALL return a 403 error.

**Validates: Requirements 4.12, 4.13**

## Error Handling

### Backend Error Handling

| Error Condition | HTTP Status | Error Message |
|----------------|-------------|---------------|
| Path does not exist | 400 | "Path does not exist: {path}" |
| Path is not a directory | 400 | "Path is not a directory: {path}" |
| Path outside allowed base | 403 | "Path is outside allowed workspace area" |
| Symlink target outside base | 403 | "Path is outside allowed workspace area" |
| Workspace initialization fails | 500 | "Failed to initialize workspace: {error}" |
| Database reinitialization fails | 500 | "Failed to reinitialize database: {error}" |

### Frontend Error Handling

| Error Condition | User Feedback |
|----------------|---------------|
| API returns 400 | Display error message from API response |
| API returns 403 | Display "Access denied: path is outside allowed area" |
| API returns 500 | Display "Server error. Please try again." |
| Network error | Display "Connection failed. Please check your network." |
| Generation in progress | Disable picker, show "Cannot switch during generation" |

### Graceful Degradation

- If workspace initialization fails on startup, the backend continues operating but logs a warning
- If the `.oyawiki/.oyaignore` file doesn't exist, FileFilter uses only default excludes
- If workspace switch fails, the frontend maintains the current workspace state

## Testing Strategy

### Unit Tests

Unit tests verify specific examples and edge cases:

**Backend Unit Tests:**
- `test_file_filter.py`: Verify FileFilter reads from `.oyawiki/.oyaignore`
- `test_workspace.py`: Test `initialize_workspace()` creates correct structure
- `test_path_validation.py`: Test path validation utility with various inputs
- `test_repos_api.py`: Test workspace switch endpoint responses

**Frontend Unit Tests:**
- `DirectoryPicker.test.tsx`: Test component rendering and interactions
- `TopBar.test.tsx`: Test integration with directory picker
- `AppContext.test.tsx`: Test `switchWorkspace` action

### Property-Based Tests

Property-based tests verify universal properties across many generated inputs. We will use `hypothesis` for Python property-based testing.

**Configuration:**
- Minimum 100 iterations per property test
- Each test references its design document property

**Property Tests:**

1. **Workspace Initialization Property Test**
   - Generate random valid directory paths
   - Verify `.oyawiki/` and all subdirectories are created
   - Tag: `Feature: oya-config-improvements, Property 1: Workspace initialization creates directory structure`

2. **Invalid Path Rejection Property Test**
   - Generate random non-existent paths and file paths
   - Verify 400 response for all invalid inputs
   - Tag: `Feature: oya-config-improvements, Property 2: Invalid path rejection`

3. **Base Path Security Property Test**
   - Generate random paths both inside and outside base path
   - Verify correct acceptance/rejection based on containment
   - Tag: `Feature: oya-config-improvements, Property 3: Base path security enforcement`

4. **Path Canonicalization Property Test**
   - Generate paths with `..` segments, symlinks, and traversal patterns
   - Verify canonical resolution and security enforcement
   - Tag: `Feature: oya-config-improvements, Property 4: Path canonicalization security`

### Integration Tests

- Test full workspace switch flow from frontend to backend
- Test startup initialization with fresh workspace
- Test FileFilter with `.oyawiki/.oyaignore` patterns

### Test Framework Configuration

**Backend (pytest + hypothesis):**
```python
from hypothesis import given, strategies as st, settings

@settings(max_examples=100)
@given(st.text())
def test_property_example(input_data):
    # Property test implementation
    pass
```

**Frontend (vitest):**
```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

describe('DirectoryPicker', () => {
  it('displays current path', () => {
    // Test implementation
  });
});
```
