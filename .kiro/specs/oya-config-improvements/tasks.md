# Implementation Plan: Oya Configuration Improvements

## Overview

This plan implements three improvements: relocating `.oyaignore` to `.oyawiki/`, auto-initializing the workspace on startup, and adding a directory picker for workspace switching. Tasks follow TDD (red/green/refactor) strategy.

## Tasks

- [x] 1. Workspace initializer module (TDD)
  - [x] 1.1 RED: Write failing property test for workspace initialization
    - Create test file `backend/tests/test_workspace.py`
    - Write property test that workspace initialization creates all required directories
    - **Property 1: Workspace initialization creates directory structure**
    - **Validates: Requirements 2.2**
    - Test should fail (module doesn't exist yet)
  - [x] 1.2 GREEN: Implement `initialize_workspace()` to pass the test
    - Create `backend/src/oya/workspace.py`
    - Implement function to create: wiki, notes, meta, index, cache, config directories
    - Handle errors gracefully with logging
    - Return boolean success indicator
    - _Requirements: 2.2, 2.3_
  - [x] 1.3 REFACTOR: Clean up workspace initialization code
    - Review for code clarity and error handling
    - Extract constants if needed

- [x] 2. Startup initialization integration (TDD)
  - [x] 2.1 RED: Write failing unit test for startup initialization
    - Add test to verify lifespan handler calls initialize_workspace
    - Test should fail (lifespan handler not implemented yet)
    - _Requirements: 2.1_
  - [x] 2.2 GREEN: Add lifespan handler to `backend/src/oya/main.py`
    - Import workspace initializer
    - Call `initialize_workspace()` on startup
    - Log success/failure
    - _Requirements: 2.1_
  - [x] 2.3 REFACTOR: Clean up startup code

- [x] 3. Relocate oyaignore file path (TDD)
  - [x] 3.1 RED: Update FileFilter tests for new path
    - Modify existing tests to expect `.oyawiki/.oyaignore` path
    - Tests should fail (implementation still uses old path)
    - _Requirements: 1.1_
  - [x] 3.2 GREEN: Update `backend/src/oya/repo/file_filter.py`
    - Change path from `repo_path / ".oyaignore"` to `repo_path / ".oyawiki" / ".oyaignore"`
    - _Requirements: 1.1, 1.2_
  - [x] 3.3 REFACTOR: Update documentation files
    - Update `README.md` to reference `.oyawiki/.oyaignore`
    - Update `.kiro/steering/structure.md` to reference `.oyawiki/.oyaignore`
    - _Requirements: 1.3_

- [x] 4. Checkpoint - Verify backend initialization works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Path validation utility (TDD)
  - [x] 5.1 RED: Write failing property tests for path validation
    - Create tests for invalid path rejection
    - Create tests for base path security enforcement
    - Create tests for path canonicalization
    - **Property 2: Invalid path rejection**
    - **Property 3: Base path security enforcement**
    - **Property 4: Path canonicalization security**
    - **Validates: Requirements 4.6, 4.7, 4.9, 4.11, 4.12, 4.13**
  - [x] 5.2 GREEN: Implement path validation in `backend/src/oya/api/deps.py`
    - Add `get_workspace_base_path()` function
    - Add `validate_workspace_path()` function with security checks
    - Handle symlink resolution and path canonicalization
    - _Requirements: 4.9, 4.10, 4.12, 4.13_
  - [x] 5.3 REFACTOR: Clean up path validation code

- [x] 6. Workspace switching API (TDD)
  - [x] 6.1 RED: Write failing unit tests for workspace switch endpoint
    - Test successful switch returns 200 with status
    - Test non-existent path returns 400
    - Test file path returns 400
    - Test path outside base returns 403
    - Tests should fail (endpoint doesn't exist yet)
    - _Requirements: 4.6, 4.7, 4.11_
  - [x] 6.2 GREEN: Implement workspace switch endpoint
    - Add `WorkspaceSwitch` and `WorkspaceSwitchResponse` schemas to `backend/src/oya/api/schemas.py`
    - Add POST `/api/repos/workspace` endpoint to `backend/src/oya/api/routers/repos.py`
    - Validate path using path validation utility
    - Clear settings cache and reinitialize
    - Reinitialize database connection
    - Run workspace initialization for new workspace
    - Return new repository status
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.11_
  - [x] 6.3 REFACTOR: Clean up workspace switch implementation

- [x] 7. Checkpoint - Verify backend API works
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Frontend API client (TDD)
  - [x] 8.1 RED: Write failing test for switchWorkspace API function
    - Test that function calls correct endpoint
    - Test should fail (function doesn't exist yet)
    - _Requirements: 3.3_
  - [x] 8.2 GREEN: Implement frontend API client
    - Add `WorkspaceSwitchRequest` and `WorkspaceSwitchResponse` to `frontend/src/types/index.ts`
    - Add `switchWorkspace()` function to `frontend/src/api/client.ts`
    - _Requirements: 3.3, 4.1_
  - [x] 8.3 REFACTOR: Clean up API client code

- [x] 9. DirectoryPicker component (TDD)
  - [x] 9.1 RED: Write failing unit tests for DirectoryPicker
    - Test renders current path
    - Test click shows input
    - Test submit calls onSwitch
    - Test disabled state
    - Tests should fail (component doesn't exist yet)
    - _Requirements: 3.1, 3.2, 3.8, 3.9, 3.10_
  - [x] 9.2 GREEN: Create `frontend/src/components/DirectoryPicker.tsx`
    - Display current workspace path
    - Toggle to edit mode on click
    - Text input for new path
    - Submit on Enter or button click
    - Loading state during switch
    - Error display for failures
    - Disabled state when generation in progress
    - _Requirements: 3.1, 3.2, 3.7, 3.8, 3.9, 3.10_
  - [x] 9.3 REFACTOR: Clean up DirectoryPicker component

- [x] 10. AppContext workspace switching (TDD)
  - [x] 10.1 RED: Write failing unit tests for switchWorkspace action and dirty state
    - Test successful switch updates state
    - Test clears current page
    - Test error handling
    - Test setNoteEditorDirty updates isDirty state
    - Tests should fail (action doesn't exist yet)
    - _Requirements: 3.4, 3.5, 3.6_
  - [x] 10.2 GREEN: Add `switchWorkspace` action and dirty tracking to `frontend/src/context/AppContext.tsx`
    - Add `isDirty` field to NoteEditorState interface
    - Add `SET_NOTE_EDITOR_DIRTY` action type
    - Add `setNoteEditorDirty` function to context
    - Reset isDirty to false when closing note editor
    - Call API to switch workspace
    - Update repo status on success
    - Clear current page state
    - Refresh wiki tree
    - Handle errors
    - _Requirements: 3.3, 3.4, 3.5, 3.6_
  - [x] 10.3 REFACTOR: Clean up AppContext code

- [x] 11. TopBar integration (TDD)
  - [x] 11.1 RED: Write failing unit tests for TopBar with DirectoryPicker
    - Test DirectoryPicker is rendered
    - Test disabled during generation
    - Test confirmation prompt when noteEditor.isDirty is true
    - Tests should fail (integration not done yet)
    - _Requirements: 3.6, 3.10_
  - [x] 11.2 GREEN: Update `frontend/src/components/TopBar.tsx`
    - Import and render DirectoryPicker
    - Pass current path from repoStatus
    - Pass switchWorkspace handler
    - Check job status for disabled state
    - Check noteEditor.isDirty for unsaved changes confirmation
    - Add confirmation dialog for unsaved changes
    - Export DirectoryPicker from `frontend/src/components/index.ts`
    - _Requirements: 3.1, 3.6, 3.10, 3.11_
  - [x] 11.3 REFACTOR: Clean up TopBar integration

- [ ] 12. Final checkpoint - Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- All tasks follow TDD: RED (failing test) → GREEN (make it pass) → REFACTOR (clean up)
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties using hypothesis
- Backend uses Python/FastAPI, frontend uses React/TypeScript
