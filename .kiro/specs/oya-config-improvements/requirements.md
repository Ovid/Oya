# Requirements Document

## Introduction

This feature addresses three improvements to Oya's configuration and usability:
1. Moving the `.oyaignore` file from the repository root into the `.oyawiki/` directory to keep all Oya artifacts in one place
2. Auto-initializing the `.oyawiki/` directory on startup
3. Adding a directory picker to the TopBar so users can switch workspaces and build wikis for different directories

## Glossary

- **Oya**: The wiki generation system for codebases
- **Oyawiki_Directory**: The `.oyawiki/` directory that contains all Oya-generated artifacts
- **Oyaignore_File**: A file containing patterns for files/directories to exclude from wiki generation
- **Workspace**: The root directory of a repository being documented by Oya
- **TopBar**: The fixed header component in the Oya frontend UI
- **FileFilter**: The backend component that filters files based on exclusion patterns

## Requirements

### Requirement 1: Relocate Oyaignore File

**User Story:** As a developer, I want the `.oyaignore` file to be located inside `.oyawiki/`, so that all Oya configuration and artifacts are kept in one directory.

#### Acceptance Criteria

1. WHEN the FileFilter loads exclusion patterns, THE FileFilter SHALL read from `.oyawiki/.oyaignore` instead of `.oyaignore` in the repository root
2. WHEN the Oyaignore_File path is referenced in code, THE System SHALL use the path `.oyawiki/.oyaignore`
3. THE following documentation files SHALL be updated to reference `.oyawiki/.oyaignore`: `README.md`, `.kiro/steering/structure.md`

### Requirement 2: Workspace Initialization

**User Story:** As a developer, I want Oya to automatically initialize the `.oyawiki/` directory structure on first run, so that I can start using Oya without manual setup.

#### Acceptance Criteria

1. THE System SHALL initialize the workspace when the backend application starts
2. WHEN Oya initializes a workspace AND no `.oyawiki/` directory exists, THE System SHALL create the `.oyawiki/` directory
3. WHEN workspace initialization fails, THE System SHALL log an error and continue operating without the `.oyawiki/` directory if possible

### Requirement 3: Directory Picker in TopBar

**User Story:** As a developer, I want to switch to a different directory from the TopBar, so that I can build Oya wikis for different projects without restarting the application.

#### Acceptance Criteria

1. THE TopBar SHALL display a directory picker control that shows the current workspace path
2. WHEN a user clicks the directory picker, THE System SHALL display a text input field for entering an absolute directory path
3. WHEN a user submits a directory path, THE System SHALL call the backend API to switch workspaces
4. WHEN the workspace is switched, THE System SHALL refresh the repository status and wiki tree
5. WHEN the workspace is switched, THE System SHALL clear the current page state
6. IF the user has unsaved changes in the NoteEditor, THE System SHALL prompt for confirmation before switching workspaces
7. IF the selected directory is invalid, THEN THE System SHALL display an error message to the user
8. WHILE a workspace switch is in progress, THE System SHALL display a loading indicator
9. WHILE a workspace switch is in progress, THE System SHALL disable the directory picker input to prevent concurrent switches
10. IF a wiki generation job is in progress, THE System SHALL disable the directory picker and display a message indicating workspace switching is unavailable during generation
11. THE Frontend SHALL check the job status via the existing `/api/jobs/status` endpoint before allowing workspace switches

### Requirement 4: Backend Workspace Switching API

**User Story:** As a frontend developer, I want a backend API to switch workspaces, so that the directory picker can change which repository Oya is documenting.

#### Acceptance Criteria

1. THE Backend SHALL expose a POST endpoint at `/api/repos/workspace` to change the active workspace
2. WHEN a valid directory path is provided, THE Backend SHALL update the workspace configuration
3. WHEN the workspace is changed, THE Backend SHALL reinitialize the database connection for the new workspace
4. WHEN the workspace is changed, THE Backend SHALL clear any cached data from the previous workspace
5. WHEN the workspace is changed, THE Backend SHALL run workspace initialization for the new workspace (per Requirement 2)
6. IF the provided path does not exist, THEN THE Backend SHALL return a 400 error with a descriptive message
7. IF the provided path is not a directory, THEN THE Backend SHALL return a 400 error with a descriptive message
8. THE Backend SHALL return the new repository status after a successful workspace switch
9. THE Backend SHALL validate that the provided path is under the configured `WORKSPACE_BASE_PATH` environment variable
10. IF `WORKSPACE_BASE_PATH` is not configured, THE Backend SHALL default to the user's home directory
11. IF the provided path is outside the allowed base path, THEN THE Backend SHALL return a 403 error with a descriptive message
12. THE Backend SHALL resolve paths to their canonical form (resolving symlinks and `..` segments) before validating against the base path
13. IF the resolved canonical path of a symlink target is outside the allowed base path, THE Backend SHALL return a 403 error
