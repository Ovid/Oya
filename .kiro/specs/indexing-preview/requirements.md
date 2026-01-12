# Requirements Document

## Introduction

This feature adds an "Indexing Preview" UI that allows users to see exactly which directories and files will be indexed before starting wiki generation. Users can selectively exclude directories and files from indexing by checking them off, and these exclusions are persisted to `.oyawiki/.oyaignore` only when the user saves their changes.

## Glossary

- **Indexing_Preview**: A modal UI component that displays all directories and files that would be indexed, allowing users to exclude items before generation.
- **FileFilter**: The backend service that determines which files to include/exclude based on default patterns and `.oyaignore`.
- **Oyaignore**: The file at `.oyawiki/.oyaignore` that contains user-defined exclusion patterns.
- **Exclusion_List**: The set of directories and files the user has selected to exclude in the preview UI.
- **Pending_Exclusions**: Exclusions selected in the UI but not yet saved to `.oyaignore`.

## Requirements

### Requirement 1: Preview Button

**User Story:** As a user, I want a button to preview what will be indexed before starting generation, so that I can review and adjust the scope.

#### Acceptance Criteria

1. WHEN the user is on the main page with no generation in progress, THE Indexing_Preview button SHALL be visible alongside the "Generate Wiki" button
2. WHEN the user clicks the Indexing_Preview button, THE System SHALL open a modal displaying the indexing preview
3. WHILE a generation is in progress, THE Indexing_Preview button SHALL be disabled

### Requirement 2: Directory and File Listing

**User Story:** As a user, I want to see all directories and files that will be indexed, so that I can understand the scope of generation.

#### Acceptance Criteria

1. WHEN the Indexing_Preview modal opens, THE System SHALL fetch the list of indexable directories and files from the backend
2. THE Backend SHALL use the exact same FileFilter class from `oya.repo.file_filter` that GenerationOrchestrator uses during the analysis phase to get the file list
3. THE Backend SHALL derive the directory list from the file list using the exact same logic as GenerationOrchestrator._run_directories (extracting unique parent paths from file paths)
4. THE System SHALL guarantee that the preview list matches exactly what would be indexed during generation
5. WHEN displaying the list, THE System SHALL show directories in a separate section above files
6. WHEN displaying directories, THE System SHALL sort them alphabetically
7. WHEN displaying files, THE System SHALL sort them alphabetically
8. THE System SHALL NOT display directories that are already excluded via `.oyaignore`
9. THE System SHALL NOT display files that are already excluded via `.oyaignore`
10. THE System SHALL provide a search input to filter directories and files by name
11. WHEN the user types in the search input, THE System SHALL filter the displayed list to show only items whose full path contains the search text (case-insensitive)
12. THE System SHALL display the total count of directories and files that will be indexed
13. WHEN items are excluded, THE System SHALL update the counts to reflect the remaining items

### Requirement 3: Directory Exclusion

**User Story:** As a user, I want to exclude entire directories from indexing, so that I can skip irrelevant sections of my codebase.

#### Acceptance Criteria

1. WHEN the user checks a directory checkbox, THE System SHALL mark that directory as pending exclusion
2. WHEN a directory is marked as pending exclusion, THE System SHALL remove all files within that directory from the files list display
3. WHEN a directory is unchecked, THE System SHALL restore files within that directory to the files list display
4. WHEN displaying the files list, THE System SHALL NOT show files that are within any checked directory
5. WHEN a directory is checked, THE System SHALL remove any pending file exclusions within that directory from the exclusion list

### Requirement 4: File Exclusion

**User Story:** As a user, I want to exclude individual files from indexing, so that I can fine-tune what gets documented.

#### Acceptance Criteria

1. WHEN the user checks a file checkbox, THE System SHALL mark that file as pending exclusion
2. WHEN a file is marked as pending exclusion, THE System SHALL visually indicate the exclusion state
3. THE System SHALL allow excluding files that are not within any excluded directory

### Requirement 5: Save Exclusions

**User Story:** As a user, I want to save my exclusion selections, so that they persist for future generations.

#### Acceptance Criteria

1. WHEN the user clicks the "Save" button, THE System SHALL append newly excluded directories to the end of `.oyawiki/.oyaignore` without removing existing entries
2. WHEN saving directory exclusions, THE System SHALL add a trailing slash to directory patterns (e.g., `docs/`)
3. WHEN the user clicks the "Save" button, THE System SHALL append newly excluded files to the end of `.oyawiki/.oyaignore` without removing existing entries
4. WHEN saving file exclusions, THE System SHALL NOT add files that are within an excluded directory (directory exclusion covers them)
5. WHEN the save operation completes successfully, THE System SHALL close the modal
6. IF the `.oyawiki/.oyaignore` file does not exist, THEN THE System SHALL create it before appending exclusions
7. BEFORE saving, THE System SHALL display a summary of exclusions to be added (count of directories and files)
8. THE System SHALL require user confirmation before writing to `.oyaignore`

### Requirement 6: Discard Changes

**User Story:** As a user, I want to discard my exclusion selections without saving, so that I can cancel my changes.

#### Acceptance Criteria

1. WHEN the user clicks the "Cancel" or close button, THE System SHALL close the modal without modifying `.oyaignore`
2. WHEN the user clicks outside the modal, THE System SHALL close the modal without modifying `.oyaignore`
3. WHEN the modal is closed without saving, THE System SHALL discard all pending exclusions

### Requirement 7: Backend Endpoint

**User Story:** As a developer, I want a backend endpoint that returns the indexable items, so that the frontend can display them.

#### Acceptance Criteria

1. THE Backend SHALL provide a GET endpoint at `/api/repos/indexable` that returns directories and files
2. WHEN the endpoint is called, THE Backend SHALL use the exact same FileFilter class from `oya.repo.file_filter` that is used during the analysis phase in GenerationOrchestrator
3. THE Backend SHALL NOT duplicate or reimplement file filtering logic; it MUST reuse the existing FileFilter implementation
4. WHEN the endpoint is called, THE Backend SHALL derive directories from the file list using the same logic as GenerationOrchestrator._run_directories (extracting unique parent paths)
5. THE Backend SHALL NOT duplicate or reimplement directory extraction logic; it SHOULD extract this into a reusable function if needed
6. THE Endpoint response SHALL include separate arrays for directories and files
7. THE Endpoint SHALL return the exact same list of files that would be processed during wiki generation
8. THE Endpoint SHALL NOT return items that are already excluded via `.oyaignore`
9. IF the repository path is invalid or inaccessible, THEN THE Endpoint SHALL return a 400 error with a descriptive message
10. IF file enumeration fails, THEN THE Endpoint SHALL return a 500 error with details

### Requirement 8: Update Oyaignore Endpoint

**User Story:** As a developer, I want a backend endpoint to update `.oyaignore`, so that the frontend can persist exclusions.

#### Acceptance Criteria

1. THE Backend SHALL provide a POST endpoint at `/api/repos/oyaignore` to add exclusions
2. WHEN the endpoint receives directory exclusions, THE Backend SHALL append them to the end of `.oyawiki/.oyaignore` with trailing slashes, preserving existing entries
3. WHEN the endpoint receives file exclusions, THE Backend SHALL append them to the end of `.oyawiki/.oyaignore`, preserving existing entries
4. IF `.oyawiki/.oyaignore` does not exist, THEN THE Backend SHALL create it
5. THE Backend SHALL NOT add duplicate entries to `.oyaignore`
6. WHEN exclusions are added, THE Backend SHALL return the updated list of exclusions
7. IF writing to `.oyaignore` fails due to permissions, THEN THE Endpoint SHALL return a 403 error
8. IF the `.oyawiki` directory cannot be created, THEN THE Endpoint SHALL return a 500 error
