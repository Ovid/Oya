# Implementation Plan: Bottom-Up Wiki Generation

## Overview

This plan implements the bottom-up wiki generation pipeline using TDD (red-green-refactor). Each feature follows the cycle: write a failing test first (red), implement minimal code to pass (green), then refactor at checkpoints.

## Tasks

- [x] 1. FileSummary data model (TDD)
  - [x] 1.1 RED: Write property test for FileSummary completeness
    - Create `backend/tests/test_summaries.py`
    - Test that any valid FileSummary has all required fields
    - Test that layer is one of: api, domain, infrastructure, utility, config, test
    - **Property 1: File_Summary Completeness**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6**
  - [x] 1.2 GREEN: Create FileSummary dataclass
    - Add `backend/src/oya/generation/summaries.py`
    - Define FileSummary with fields: file_path, purpose, layer, key_abstractions, internal_deps, external_deps
    - Add validation for layer field
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 2. DirectorySummary data model (TDD)
  - [x] 2.1 RED: Write property test for DirectorySummary completeness
    - Test that any valid DirectorySummary has all required fields
    - **Property 4: Directory_Summary Completeness**
    - **Validates: Requirements 2.2, 2.3, 2.4**
  - [x] 2.2 GREEN: Create DirectorySummary dataclass
    - Define DirectorySummary with fields: directory_path, purpose, contains, role_in_system
    - _Requirements: 2.2, 2.3, 2.4_

- [x] 3. SummaryParser YAML extraction (TDD)
  - [x] 3.1 RED: Write property test for YAML parsing and stripping
    - Test that valid YAML blocks are extracted and stripped from markdown
    - **Property 14: YAML Parsing and Stripping**
    - **Validates: Requirements 8.1, 8.4, 8.5**
  - [x] 3.2 GREEN: Implement parse_file_summary method
    - Parse YAML block delimited by `---` from markdown
    - Extract FileSummary fields from YAML
    - Return tuple of (clean_markdown, FileSummary)
    - _Requirements: 8.1, 8.4_
  - [x] 3.3 GREEN: Implement parse_directory_summary method
    - Parse YAML block for directory summaries
    - Return tuple of (clean_markdown, DirectorySummary)
    - _Requirements: 8.2_

- [x] 4. SummaryParser fallback behavior (TDD)
  - [x] 4.1 RED: Write property test for FileSummary fallback on parse failure
    - Test that malformed YAML returns fallback with purpose="Unknown", layer="utility"
    - **Property 2: File_Summary Fallback on Parse Failure**
    - **Validates: Requirements 1.7, 8.3**
  - [x] 4.2 RED: Write property test for DirectorySummary fallback on parse failure
    - Test that malformed YAML returns fallback with purpose="Unknown"
    - **Property 5: Directory_Summary Fallback on Parse Failure**
    - **Validates: Requirements 2.5**
  - [x] 4.3 GREEN: Implement fallback behavior for malformed YAML
    - Return fallback FileSummary on parse failure
    - Return fallback DirectorySummary on parse failure
    - _Requirements: 1.7, 2.5, 8.3_

- [x] 5. Checkpoint - REFACTOR data models and parser
  - Ensure all tests pass
  - Refactor for clarity and consistency
  - Ask the user if questions arise

- [x] 6. SynthesisMap data model (TDD)
  - [x] 6.1 RED: Write property test for SynthesisMap JSON round-trip
    - Test that serializing and deserializing produces equivalent object
    - **Property 8: Synthesis_Map JSON Round-Trip**
    - **Validates: Requirements 3.5**
  - [x] 6.2 GREEN: Create SynthesisMap, LayerInfo, ComponentInfo dataclasses
    - Add to `backend/src/oya/generation/summaries.py`
    - Define SynthesisMap with: layers, key_components, dependency_graph, project_summary
    - Define LayerInfo with: name, purpose, directories, files
    - Define ComponentInfo with: name, file, role, layer
    - _Requirements: 3.2, 3.3, 3.4_
  - [x] 6.3 GREEN: Implement JSON serialization for SynthesisMap
    - Add to_json() and from_json() methods
    - _Requirements: 3.5_

- [x] 7. Summary persistence (TDD)
  - [x] 7.1 RED: Write property test for FileSummary persistence round-trip
    - Test that persisting and retrieving produces equivalent FileSummary
    - **Property 3: File_Summary Persistence Round-Trip**
    - **Validates: Requirements 1.8**
  - [x] 7.2 RED: Write property test for DirectorySummary persistence round-trip
    - Test that persisting and retrieving produces equivalent DirectorySummary
    - **Property 6: Directory_Summary Persistence Round-Trip**
    - **Validates: Requirements 2.7**
  - [x] 7.3 GREEN: Update _save_page to persist FileSummary in metadata
    - Serialize FileSummary to JSON in metadata column
    - _Requirements: 1.8_
  - [x] 7.4 GREEN: Update _save_page to persist DirectorySummary in metadata
    - Serialize DirectorySummary to JSON in metadata column
    - _Requirements: 2.7_

- [x] 8. Checkpoint - REFACTOR persistence layer
  - Ensure all tests pass
  - Refactor for clarity and consistency
  - Ask the user if questions arise

- [x] 9. FileGenerator summary extraction (TDD)
  - [x] 9.1 RED: Write unit test for FileGenerator summary extraction
    - Test that generate() returns valid FileSummary
    - _Requirements: 1.1_
  - [x] 9.2 GREEN: Update file prompt template to request YAML summary block
    - Modify FILE_TEMPLATE in prompts.py to include summary extraction instructions
    - _Requirements: 1.1_
  - [x] 9.3 GREEN: Update FileGenerator.generate() to parse and return FileSummary
    - Call SummaryParser.parse_file_summary() on LLM output
    - Return tuple of (GeneratedPage, FileSummary)
    - _Requirements: 1.1, 8.1_

- [x] 10. DirectoryGenerator with FileSummaries (TDD)
  - [x] 10.1 RED: Write unit test for DirectoryGenerator with FileSummary context
    - Test that generate() uses FileSummaries and returns valid DirectorySummary
    - _Requirements: 2.1, 2.6_
  - [x] 10.2 GREEN: Update directory prompt template to include FileSummary context
    - Modify DIRECTORY_TEMPLATE to accept and format FileSummaries
    - _Requirements: 2.6_
  - [x] 10.3 GREEN: Update DirectoryGenerator.generate() signature and implementation
    - Accept file_summaries parameter
    - Include FileSummary context in prompt
    - Parse and return DirectorySummary
    - _Requirements: 2.1, 2.6_

- [x] 11. Checkpoint - REFACTOR generators
  - Ensure all tests pass
  - Refactor for clarity and consistency
  - Ask the user if questions arise

- [x] 12. SynthesisGenerator layer grouping (TDD)
  - [x] 12.1 RED: Write property test for layer grouping completeness
    - Test that all files appear in exactly one layer
    - **Property 7: Synthesis_Map Layer Grouping Completeness**
    - **Validates: Requirements 3.2**
  - [x] 12.2 GREEN: Create SynthesisGenerator class
    - Add `backend/src/oya/generation/synthesis.py`
    - Implement generate() method accepting FileSummaries and DirectorySummaries
    - _Requirements: 3.1_
  - [x] 12.3 GREEN: Implement layer grouping logic
    - Group files by layer classification
    - Populate LayerInfo for each layer
    - _Requirements: 3.2_

- [x] 13. SynthesisGenerator batching (TDD)
  - [x] 13.1 RED: Write property test for batching
    - Test that large inputs are processed in batches without exceeding limits
    - **Property 9: Synthesis Batching for Large Inputs**
    - **Validates: Requirements 3.8**
  - [x] 13.2 GREEN: Implement synthesis prompt template
    - Add SYNTHESIS_TEMPLATE to prompts.py
    - Request key_components, dependency_graph, project_summary from LLM
    - _Requirements: 3.3, 3.4, 3.7_
  - [x] 13.3 GREEN: Implement batch processing for large inputs
    - Split summaries into batches when exceeding context limit
    - Merge batch results into single SynthesisMap
    - _Requirements: 3.8_
  - [x] 13.4 GREEN: Implement SynthesisMap persistence to synthesis.json
    - Save to `.oyawiki/meta/synthesis.json`
    - _Requirements: 3.6_

- [x] 14. Checkpoint - REFACTOR synthesis generator
  - Ensure all tests pass
  - Refactor for clarity and consistency
  - Ask the user if questions arise

- [x] 15. ArchitectureGenerator with SynthesisMap (TDD)
  - [x] 15.1 RED: Write unit test for ArchitectureGenerator with SynthesisMap
    - Test generation succeeds with SynthesisMap, no README
    - _Requirements: 5.1, 5.5_
  - [x] 15.2 GREEN: Update architecture prompt template
    - Modify ARCHITECTURE_TEMPLATE to accept SynthesisMap
    - Include layers, key_components, dependency_graph in prompt
    - _Requirements: 5.2, 5.3, 5.4_
  - [x] 15.3 GREEN: Update ArchitectureGenerator.generate() signature
    - Accept synthesis_map parameter instead of key_symbols
    - _Requirements: 5.1_

- [x] 16. OverviewGenerator with SynthesisMap (TDD)
  - [x] 16.1 RED: Write unit test for OverviewGenerator with SynthesisMap
    - Test generation succeeds with SynthesisMap, no README
    - _Requirements: 6.1, 6.5_
  - [x] 16.2 GREEN: Update overview prompt template
    - Modify OVERVIEW_TEMPLATE to accept SynthesisMap as primary context
    - Keep README as supplementary
    - _Requirements: 6.2, 6.3, 6.4_
  - [x] 16.3 GREEN: Update OverviewGenerator.generate() signature
    - Accept synthesis_map parameter
    - _Requirements: 6.1_

- [x] 17. Checkpoint - REFACTOR high-level generators
  - Ensure all tests pass
  - Refactor for clarity and consistency
  - Ask the user if questions arise

- [x] 18. GenerationOrchestrator pipeline refactor (TDD)
  - [x] 18.1 RED: Write unit test for pipeline phase order
    - Test that phases execute in order: Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows
    - _Requirements: 4.1_
  - [x] 18.2 RED: Write unit test for File_Summaries passed to Synthesis
    - Test that _run_files returns FileSummaries and they reach _run_synthesis
    - _Requirements: 4.2_
  - [x] 18.3 RED: Write unit test for Directory_Summaries passed to Synthesis
    - Test that _run_directories returns DirectorySummaries and they reach _run_synthesis
    - _Requirements: 4.3_
  - [x] 18.4 RED: Write unit test for Synthesis_Map passed to Architecture and Overview
    - Test that _run_synthesis output reaches _run_architecture and _run_overview
    - _Requirements: 4.4, 4.5, 4.6_
  - [x] 18.5 GREEN: Add SYNTHESIS phase to GenerationPhase enum
    - _Requirements: 4.1_
  - [x] 18.6 GREEN: Reorder run() method phases
    - New order: Analysis → Files → Directories → Synthesis → Architecture → Overview → Workflows
    - _Requirements: 4.1_
  - [x] 18.7 GREEN: Update _run_files to collect and return FileSummaries
    - Return tuple of (pages, file_hashes, file_summaries)
    - _Requirements: 4.2_
  - [x] 18.8 GREEN: Update _run_directories to accept FileSummaries and return DirectorySummaries
    - Pass FileSummaries to DirectoryGenerator
    - Return tuple of (pages, directory_summaries)
    - _Requirements: 4.3_
  - [x] 18.9 GREEN: Add _run_synthesis method
    - Call SynthesisGenerator with collected summaries
    - Save SynthesisMap to synthesis.json
    - _Requirements: 3.1, 3.6_
  - [x] 18.10 GREEN: Update _run_architecture to use SynthesisMap
    - Pass SynthesisMap instead of raw symbols
    - _Requirements: 4.4, 4.5_
  - [x] 18.11 GREEN: Update _run_overview to use SynthesisMap
    - Pass SynthesisMap as primary context
    - _Requirements: 4.4, 4.6_

- [x] 19. Checkpoint - REFACTOR orchestrator
  - Ensure all tests pass
  - Refactor for clarity and consistency
  - Ask the user if questions arise

- [x] 20. Cascade regeneration - file changes (TDD)
  - [x] 20.1 RED: Write property test for file change cascade
    - Test that changed file content triggers regeneration
    - **Property 10: Cascade - File Change Triggers Regeneration**
    - **Validates: Requirements 7.1**
  - [x] 20.2 GREEN: Verify cascade behavior for file changes
    - Already exists, verify behavior works correctly
    - _Requirements: 7.1_

- [x] 21. Cascade regeneration - synthesis (TDD)
  - [x] 21.1 RED: Write property test for synthesis cascade
    - Test that file regeneration triggers synthesis regeneration
    - **Property 11: Cascade - File Regeneration Triggers Synthesis**
    - **Validates: Requirements 7.2**
  - [x] 21.2 GREEN: Implement cascade: file regeneration triggers synthesis
    - If any file was regenerated, regenerate SynthesisMap
    - _Requirements: 7.2_
  - [x] 21.3 GREEN: Track synthesis_hash for change detection
    - Compute hash of SynthesisMap after generation
    - Store in synthesis.json
    - _Requirements: 7.4_

- [x] 22. Cascade regeneration - high-level docs (TDD)
  - [x] 22.1 RED: Write property test for arch/overview cascade
    - Test that synthesis change triggers Architecture and Overview regeneration
    - **Property 12: Cascade - Synthesis Change Triggers High-Level Docs**
    - **Validates: Requirements 7.3**
  - [x] 22.2 GREEN: Implement cascade: synthesis change triggers arch/overview
    - Compare new synthesis_hash to stored hash
    - Regenerate Architecture and Overview if changed
    - _Requirements: 7.3_

- [x] 23. No-change skip optimization (TDD)
  - [x] 23.1 RED: Write property test for no-change skip
    - Test that no changes and no new notes skips all regeneration
    - **Property 13: No-Change Skip**
    - **Validates: Requirements 7.5**
  - [x] 23.2 GREEN: Implement no-change skip
    - Skip all regeneration if no files changed and no new notes
    - _Requirements: 7.5_

- [x] 24. Final checkpoint - REFACTOR cascade logic
  - Ensure all tests pass
  - Refactor for clarity and consistency
  - Ask the user if questions arise

- [x] 25. Integration testing
  - [x] 25.1 Write integration test for full pipeline with no README
    - Verify generation succeeds and produces valid Architecture/Overview
    - _Requirements: 5.5, 6.5_
  - [x] 25.2 Write integration test for cascade behavior
    - Modify a file, run generation, verify cascade
    - _Requirements: 7.1, 7.2, 7.3_

## Notes

- All tasks are required for comprehensive coverage
- Each task references specific requirements for traceability
- TDD cycle: RED (failing test) → GREEN (minimal implementation) → REFACTOR (at checkpoints)
- Property tests validate universal correctness properties using hypothesis
- Unit tests validate specific examples and edge cases
- Checkpoints are refactoring opportunities - clean up code while tests are green
