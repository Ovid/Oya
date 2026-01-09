# Requirements Document

## Introduction

This document specifies requirements for refactoring the wiki generation pipeline to use a bottom-up approach. Currently, the system generates Overview and Architecture pages first, relying heavily on README.md and package manifests. When these don't exist, the LLM must guess architecture from file names and symbol names alone, resulting in poor quality documentation.

The bottom-up approach generates file and directory documentation first, extracts structured summaries from each, synthesizes these into a codebase understanding map, and then uses that synthesis to generate high-quality Architecture and Overview pages—even when no README exists.

## Glossary

- **File_Summary**: A structured data block extracted from file documentation containing purpose, layer classification, key abstractions, and dependencies.
- **Directory_Summary**: A structured data block extracted from directory documentation containing purpose, contained files, and role in the system.
- **Synthesis_Map**: An aggregated data structure combining all File_Summaries and Directory_Summaries into a coherent codebase understanding, including layer groupings, key components, and dependency relationships.
- **Layer**: A classification of code responsibility (e.g., api, domain, infrastructure, utility, config, test).
- **Generation_Pipeline**: The orchestrated sequence of phases that produces wiki documentation.
- **Cascade_Regeneration**: The process where changes to lower-level docs (files) trigger regeneration of higher-level docs (synthesis, architecture, overview).

## Requirements

### Requirement 1: File Summary Extraction

**User Story:** As a wiki generator, I want to extract structured summaries from file documentation, so that I can build a bottom-up understanding of the codebase.

#### Acceptance Criteria

1. WHEN the File_Generator generates documentation for a file, THE File_Generator SHALL include a structured File_Summary block in the output.
2. THE File_Summary SHALL contain a purpose field with a one-sentence description of what the file does.
3. THE File_Summary SHALL contain a layer field classifying the file as one of: api, domain, infrastructure, utility, config, or test.
4. THE File_Summary SHALL contain a key_abstractions field listing the primary classes, functions, or types defined in the file.
5. THE File_Summary SHALL contain an internal_deps field listing paths to other files in the repository that this file depends on.
6. THE File_Summary SHALL contain an external_deps field listing external libraries or packages the file imports.
7. WHEN the LLM fails to produce a valid File_Summary, THE File_Generator SHALL use a fallback summary with purpose set to "Unknown" and layer set to "utility".
8. THE File_Summary SHALL be persisted alongside the file's wiki page metadata in the database.

### Requirement 2: Directory Summary Extraction

**User Story:** As a wiki generator, I want to extract structured summaries from directory documentation, so that I can understand the role of each module in the system.

#### Acceptance Criteria

1. WHEN the Directory_Generator generates documentation for a directory, THE Directory_Generator SHALL include a structured Directory_Summary block in the output.
2. THE Directory_Summary SHALL contain a purpose field with a one-sentence description of what the directory/module is responsible for.
3. THE Directory_Summary SHALL contain a contains field listing the files in the directory.
4. THE Directory_Summary SHALL contain a role_in_system field describing how this directory fits into the overall architecture.
5. WHEN the LLM fails to produce a valid Directory_Summary, THE Directory_Generator SHALL use a fallback summary with purpose set to "Unknown".
6. WHEN generating a Directory_Summary, THE Directory_Generator SHALL receive the File_Summaries of files contained in that directory as input context.
7. THE Directory_Summary SHALL be persisted alongside the directory's wiki page metadata in the database.

### Requirement 3: Synthesis Map Generation

**User Story:** As a wiki generator, I want to synthesize file and directory summaries into a coherent codebase map, so that Architecture and Overview generators have accurate context.

#### Acceptance Criteria

1. WHEN all File_Summaries and Directory_Summaries have been collected, THE Synthesis_Generator SHALL produce a Synthesis_Map.
2. THE Synthesis_Map SHALL group files and directories by their layer classification.
3. THE Synthesis_Map SHALL identify key components across the codebase with their names, files, and roles.
4. THE Synthesis_Map SHALL include a dependency_graph showing relationships between layers or major components.
5. THE Synthesis_Map SHALL be serializable to JSON for storage and retrieval.
6. THE Synthesis_Map SHALL be persisted to `.oyawiki/meta/synthesis.json` after generation.
7. WHEN generating the Synthesis_Map, THE Synthesis_Generator SHALL use the LLM to identify patterns and relationships that aren't explicit in individual summaries.
8. WHEN the combined File_Summaries and Directory_Summaries exceed the LLM context limit, THE Synthesis_Generator SHALL process summaries in batches and merge the results.

### Requirement 4: Reordered Generation Pipeline

**User Story:** As a wiki generator, I want to generate files and directories before architecture and overview, so that high-level documentation is informed by actual code understanding.

#### Acceptance Criteria

1. THE Generation_Pipeline SHALL execute phases in this order: Analysis, Files, Directories, Synthesis, Architecture, Overview, Workflows.
2. WHEN the Files phase completes, THE Generation_Pipeline SHALL pass all File_Summaries to the Synthesis phase.
3. WHEN the Directories phase completes, THE Generation_Pipeline SHALL pass all Directory_Summaries to the Synthesis phase.
4. WHEN the Synthesis phase completes, THE Generation_Pipeline SHALL pass the Synthesis_Map to the Architecture and Overview phases.
5. THE Architecture_Generator SHALL use the Synthesis_Map as its primary context instead of raw symbols.
6. THE Overview_Generator SHALL use the Synthesis_Map as its primary context, with README content as supplementary if available.

### Requirement 5: Architecture Generation with Synthesis

**User Story:** As a developer reading the wiki, I want the Architecture page to accurately reflect the actual code structure, so that I can understand the system design without reading every file.

#### Acceptance Criteria

1. WHEN generating the Architecture page, THE Architecture_Generator SHALL receive the Synthesis_Map as input.
2. THE Architecture_Generator SHALL use layer groupings from the Synthesis_Map to describe system layers.
3. THE Architecture_Generator SHALL use the dependency_graph from the Synthesis_Map to describe component relationships.
4. THE Architecture_Generator SHALL reference key_components from the Synthesis_Map when describing important abstractions.
5. WHEN no README exists, THE Architecture_Generator SHALL still produce accurate architecture documentation based on the Synthesis_Map.

### Requirement 6: Overview Generation with Synthesis

**User Story:** As a developer reading the wiki, I want the Overview page to accurately describe the project even when no README exists, so that I can quickly understand what the codebase does.

#### Acceptance Criteria

1. WHEN generating the Overview page, THE Overview_Generator SHALL receive the Synthesis_Map as input.
2. THE Overview_Generator SHALL derive the project summary from the Synthesis_Map when README is absent.
3. THE Overview_Generator SHALL use layer groupings to describe project structure.
4. WHEN README content exists, THE Overview_Generator SHALL use it as supplementary context alongside the Synthesis_Map.
5. WHEN no README exists, THE Overview_Generator SHALL still produce a meaningful project overview based on the Synthesis_Map.

### Requirement 7: Incremental Regeneration with Cascade

**User Story:** As a wiki generator, I want changes to files to cascade appropriately to higher-level documentation, so that the wiki stays consistent when code changes.

#### Acceptance Criteria

1. WHEN a file's content hash changes, THE Generation_Pipeline SHALL regenerate that file's documentation.
2. WHEN any file's documentation is regenerated, THE Generation_Pipeline SHALL regenerate the Synthesis_Map.
3. WHEN the Synthesis_Map changes, THE Generation_Pipeline SHALL regenerate the Architecture and Overview pages.
4. THE Generation_Pipeline SHALL track a synthesis_hash to detect when the Synthesis_Map has changed.
5. IF no files have changed AND no new notes exist, THEN THE Generation_Pipeline SHALL skip all regeneration.

### Requirement 8: Summary Parsing and Validation

**User Story:** As a wiki generator, I want to reliably parse structured summaries from LLM output, so that the synthesis phase has clean data to work with.

#### Acceptance Criteria

1. THE File_Generator SHALL parse File_Summary blocks from the generated markdown content.
2. THE Directory_Generator SHALL parse Directory_Summary blocks from the generated markdown content.
3. WHEN a summary block is malformed or missing required fields, THE parser SHALL return a fallback summary with sensible defaults.
4. THE parser SHALL support YAML format for summary blocks.
5. THE parser SHALL strip the summary block from the user-facing markdown content (summaries are metadata, not documentation).
