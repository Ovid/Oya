import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import fc from 'fast-check'
import { IndexingPreviewModal } from './IndexingPreviewModal'
import * as api from '../api/client'

// Mock the API module
vi.mock('../api/client', () => ({
  getIndexableItems: vi.fn(),
  updateOyaignore: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

describe('IndexingPreviewModal Property Tests', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onGenerate: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Ensure DOM is cleaned up between property test iterations
    cleanup()
  })

  /**
   * Property 4: Search Filter Correctness
   * For any list of items and any search query string, the filtered results SHALL contain
   * only items where the full path contains the search query as a case-insensitive substring,
   * and SHALL contain all such items.
   *
   * **Validates: Requirements 2.11**
   */
  describe('Property 4: Search Filter Correctness', () => {
    // Helper function to filter items (mirrors the component logic exactly)
    const filterItems = (items: string[], query: string): string[] => {
      const trimmedQuery = query.trim()
      if (!trimmedQuery) return items
      const lowerQuery = trimmedQuery.toLowerCase()
      return items.filter((item) => item.toLowerCase().includes(lowerQuery))
    }

    it('filtered results contain only items matching the query (case-insensitive)', async () => {
      await fc.assert(
        fc.asyncProperty(
          // Generate random list of file/directory paths
          fc.array(fc.stringMatching(/^[a-zA-Z0-9_\-./]+$/), { minLength: 1, maxLength: 20 }),
          // Generate random search query (alphanumeric only to avoid edge cases)
          fc.stringMatching(/^[a-zA-Z0-9]*$/),
          async (items, query) => {
            // Filter items using the same logic as the component
            const filtered = filterItems(items, query)

            // Property: All filtered items must contain the query (case-insensitive)
            const lowerQuery = query.toLowerCase().trim()
            if (lowerQuery) {
              for (const item of filtered) {
                expect(item.toLowerCase()).toContain(lowerQuery)
              }
            }

            // Property: All items that match must be in the filtered results
            for (const item of items) {
              if (!lowerQuery || item.toLowerCase().includes(lowerQuery)) {
                expect(filtered).toContain(item)
              }
            }
          }
        ),
        { numRuns: 100 }
      )
    })

    it('search filter in component matches expected behavior', async () => {
      // Test with a specific set of items
      const mockDirectories = ['src', 'src/components', 'tests', 'docs']
      const mockFiles = ['README.md', 'src/index.ts', 'src/components/App.tsx', 'tests/test.ts']
      const mockItems = {
        included: { directories: mockDirectories, files: mockFiles },
        excluded_by_oyaignore: { directories: [], files: [] },
        excluded_by_rule: { directories: [], files: [] },
      }

      vi.mocked(api.getIndexableItems).mockResolvedValue(mockItems)

      await fc.assert(
        fc.asyncProperty(fc.stringMatching(/^[a-zA-Z0-9]*$/), async (query) => {
          const { unmount } = render(<IndexingPreviewModal {...defaultProps} />)

          await waitFor(() => {
            expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
          })

          const searchInput = screen.getByPlaceholderText(/search/i)

          if (query) {
            await userEvent.type(searchInput, query)
          }

          // Calculate expected filtered items
          const lowerQuery = query.toLowerCase()
          const expectedDirs = mockDirectories.filter(
            (d) => !lowerQuery || d.toLowerCase().includes(lowerQuery)
          )
          const expectedFiles = mockFiles.filter(
            (f) => !lowerQuery || f.toLowerCase().includes(lowerQuery)
          )

          // Verify directories
          for (const dir of mockDirectories) {
            const shouldBeVisible = expectedDirs.includes(dir)
            if (shouldBeVisible) {
              expect(screen.queryByText(dir)).toBeInTheDocument()
            } else {
              expect(screen.queryByText(dir)).not.toBeInTheDocument()
            }
          }

          // Verify files
          for (const file of mockFiles) {
            const shouldBeVisible = expectedFiles.includes(file)
            if (shouldBeVisible) {
              expect(screen.queryByText(file)).toBeInTheDocument()
            } else {
              expect(screen.queryByText(file)).not.toBeInTheDocument()
            }
          }

          unmount()
        }),
        { numRuns: 20 } // Fewer runs for UI tests due to performance
      )
    })
  })

  /**
   * Property 6: Directory Exclusion Hides Child Files
   * For any directory marked as pending exclusion, all files whose path starts with
   * that directory path followed by "/" SHALL be hidden from the files list display.
   *
   * **Validates: Requirements 3.2, 3.4**
   */
  describe('Property 6: Directory Exclusion Hides Child Files', () => {
    // Helper function to check if a file is within a directory
    const isFileInDirectory = (file: string, dir: string): boolean => {
      return file.startsWith(dir + '/')
    }

    it('all files within excluded directory are hidden', async () => {
      await fc.assert(
        fc.asyncProperty(
          // Generate random directory names
          fc.array(fc.stringMatching(/^[a-z][a-z0-9]*$/), { minLength: 1, maxLength: 5 }),
          // Generate random file names within those directories
          fc.array(fc.stringMatching(/^[a-z][a-z0-9]*\.[a-z]+$/), { minLength: 1, maxLength: 10 }),
          async (dirNames, fileNames) => {
            // Create directories
            const directories = dirNames.map((name, i) =>
              i === 0 ? name : `${dirNames[0]}/${name}`
            )

            // Create files within directories
            const files = fileNames.map(
              (name, i) => `${directories[i % directories.length]}/${name}`
            )

            // Add some root-level files
            const rootFiles = fileNames.slice(0, 2).map((name) => name)
            const allFiles = [...files, ...rootFiles]

            const mockItems = {
              included: { directories, files: allFiles },
              excluded_by_oyaignore: { directories: [], files: [] },
              excluded_by_rule: { directories: [], files: [] },
            }

            vi.mocked(api.getIndexableItems).mockResolvedValue(mockItems)

            const { unmount } = render(<IndexingPreviewModal {...defaultProps} />)

            await waitFor(() => {
              expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
            })

            // Exclude the first directory
            const excludedDir = directories[0]
            const dirRow = screen.getByText(excludedDir).closest('div')
            const checkbox = dirRow?.querySelector('input[type="checkbox"]')

            if (checkbox) {
              await userEvent.click(checkbox)

              // Verify all files within the excluded directory are hidden
              for (const file of allFiles) {
                if (isFileInDirectory(file, excludedDir)) {
                  expect(screen.queryByText(file)).not.toBeInTheDocument()
                }
              }

              // Verify root-level files are still visible
              for (const file of rootFiles) {
                if (!isFileInDirectory(file, excludedDir)) {
                  expect(screen.queryByText(file)).toBeInTheDocument()
                }
              }
            }

            unmount()
          }
        ),
        { numRuns: 20 }
      )
    })
  })

  /**
   * Property 7: Directory Toggle Round-Trip
   * For any initial state of the preview modal, checking a directory checkbox and then
   * unchecking it SHALL restore the files list to its original state (files within that
   * directory reappear).
   *
   * **Validates: Requirements 3.3**
   */
  describe('Property 7: Directory Toggle Round-Trip', () => {
    it('check then uncheck restores files to original state', async () => {
      await fc.assert(
        fc.asyncProperty(
          // Generate random directory names
          fc.array(fc.stringMatching(/^[a-z][a-z0-9]*$/), { minLength: 1, maxLength: 3 }),
          // Generate random file names
          fc.array(fc.stringMatching(/^[a-z][a-z0-9]*\.[a-z]+$/), { minLength: 1, maxLength: 5 }),
          async (dirNames, fileNames) => {
            // Create directories
            const directories = dirNames.map((name, i) =>
              i === 0 ? name : `${dirNames[0]}/${name}`
            )

            // Create files within directories
            const files = fileNames.map(
              (name, i) => `${directories[i % directories.length]}/${name}`
            )

            const mockItems = {
              included: { directories, files },
              excluded_by_oyaignore: { directories: [], files: [] },
              excluded_by_rule: { directories: [], files: [] },
            }

            vi.mocked(api.getIndexableItems).mockResolvedValue(mockItems)

            const { unmount } = render(<IndexingPreviewModal {...defaultProps} />)

            await waitFor(() => {
              expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
            })

            // Record initial state - which files are visible
            const initialVisibleFiles = files.filter((file) => screen.queryByText(file) !== null)

            // Toggle the first directory (check then uncheck)
            const excludedDir = directories[0]
            const dirRow = screen.getByText(excludedDir).closest('div')
            const checkbox = dirRow?.querySelector('input[type="checkbox"]')

            if (checkbox) {
              // Check the directory
              await userEvent.click(checkbox)

              // Uncheck the directory
              await userEvent.click(checkbox)

              // Verify files are restored to original state
              const finalVisibleFiles = files.filter((file) => screen.queryByText(file) !== null)

              expect(finalVisibleFiles).toEqual(initialVisibleFiles)
            }

            unmount()
          }
        ),
        { numRuns: 20 }
      )
    })
  })

  /**
   * Property 8: Directory Check Clears Child File Exclusions
   * When a directory is checked (excluded), any pending file exclusions within that
   * directory SHALL be removed from the pending exclusions set.
   *
   * **Validates: Requirements 3.5**
   */
  describe('Property 8: Directory Check Clears Child File Exclusions', () => {
    it('checking directory clears pending file exclusions within it', async () => {
      await fc.assert(
        fc.asyncProperty(
          // Generate unique random directory names
          fc.uniqueArray(fc.stringMatching(/^[a-z][a-z0-9]*$/), { minLength: 1, maxLength: 3 }),
          // Generate unique random file names
          fc.uniqueArray(fc.stringMatching(/^[a-z][a-z0-9]*\.[a-z]+$/), {
            minLength: 2,
            maxLength: 5,
          }),
          async (dirNames, fileNames) => {
            // Create directories
            const directories = dirNames.map((name, i) =>
              i === 0 ? name : `${dirNames[0]}/${name}`
            )

            // Create unique files within directories
            const files = [
              ...new Set(
                fileNames.map((name, i) => `${directories[i % directories.length]}/${name}`)
              ),
            ]

            const mockItems = {
              included: { directories, files },
              excluded_by_oyaignore: { directories: [], files: [] },
              excluded_by_rule: { directories: [], files: [] },
            }

            vi.mocked(api.getIndexableItems).mockResolvedValue(mockItems)

            // Use try-finally to ensure cleanup happens even on failure
            try {
              const { unmount } = render(<IndexingPreviewModal {...defaultProps} />)

              try {
                await waitFor(() => {
                  expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
                })

                // Exclude a file within the first directory
                const targetDir = directories[0]
                const filesInDir = files.filter((f) => f.startsWith(targetDir + '/'))

                if (filesInDir.length > 0) {
                  const fileToExclude = filesInDir[0]
                  const fileRow = screen.getByText(fileToExclude).closest('div')
                  const fileCheckbox = fileRow?.querySelector('input[type="checkbox"]')

                  if (fileCheckbox) {
                    // Exclude the file (clicking unchecks it, marking it for exclusion)
                    await userEvent.click(fileCheckbox)
                    expect(fileCheckbox).not.toBeChecked()

                    // Now exclude the parent directory
                    const dirRow = screen.getByText(targetDir).closest('div')
                    const dirCheckbox = dirRow?.querySelector('input[type="checkbox"]')

                    if (dirCheckbox) {
                      await userEvent.click(dirCheckbox)

                      // Uncheck the directory to restore files
                      await userEvent.click(dirCheckbox)

                      // The file exclusion should have been cleared (file is back to included state)
                      const restoredFileRow = screen.getByText(fileToExclude).closest('div')
                      const restoredFileCheckbox =
                        restoredFileRow?.querySelector('input[type="checkbox"]')
                      expect(restoredFileCheckbox).toBeChecked()
                    }
                  }
                }
              } finally {
                unmount()
              }
            } finally {
              cleanup()
            }
          }
        ),
        { numRuns: 10 }
      )
    }, 30000) // Increased timeout for heavy UI property tests
  })

  /**
   * Property 5: Count Accuracy After Exclusions
   * For any set of directories and files with any combination of exclusions,
   * the displayed counts SHALL equal the total items minus excluded items,
   * accounting for files hidden by directory exclusions.
   *
   * **Validates: Requirements 2.13**
   */
  describe('Property 5: Count Accuracy After Exclusions', () => {
    it('displayed counts equal total minus excluded items', async () => {
      await fc.assert(
        fc.asyncProperty(
          // Generate unique random directory names
          fc.uniqueArray(fc.stringMatching(/^[a-z][a-z0-9]*$/), { minLength: 1, maxLength: 3 }),
          // Generate unique random file names
          fc.uniqueArray(fc.stringMatching(/^[a-z][a-z0-9]*\.[a-z]+$/), {
            minLength: 1,
            maxLength: 5,
          }),
          // Random index for directory to exclude (or -1 for none)
          fc.integer({ min: -1, max: 2 }),
          // Random index for file to exclude (or -1 for none)
          fc.integer({ min: -1, max: 4 }),
          async (dirNames, fileNames, dirExcludeIdx, fileExcludeIdx) => {
            // Create directories
            const directories = dirNames.map((name, i) =>
              i === 0 ? name : `${dirNames[0]}/${name}`
            )

            // Create unique files within directories
            const files = [
              ...new Set(
                fileNames.map((name, i) => `${directories[i % directories.length]}/${name}`)
              ),
            ]

            const mockItems = {
              included: { directories, files },
              excluded_by_oyaignore: { directories: [], files: [] },
              excluded_by_rule: { directories: [], files: [] },
            }

            vi.mocked(api.getIndexableItems).mockResolvedValue(mockItems)

            const { unmount } = render(<IndexingPreviewModal {...defaultProps} />)

            await waitFor(() => {
              expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
            })

            // Track expected counts
            let expectedDirCount = directories.length
            let expectedFileCount = files.length
            const excludedDirs = new Set<string>()
            const excludedFiles = new Set<string>()

            // Optionally exclude a directory
            if (dirExcludeIdx >= 0 && dirExcludeIdx < directories.length) {
              const dirToExclude = directories[dirExcludeIdx]
              const dirRow = screen.getByText(dirToExclude).closest('div')
              const dirCheckbox = dirRow?.querySelector('input[type="checkbox"]')

              if (dirCheckbox) {
                await userEvent.click(dirCheckbox)
                excludedDirs.add(dirToExclude)

                // Count excluded directories (including children)
                expectedDirCount = directories.filter((d) => {
                  if (excludedDirs.has(d)) return false
                  for (const ed of excludedDirs) {
                    if (d.startsWith(ed + '/')) return false
                  }
                  return true
                }).length

                // Count excluded files (including those in excluded dirs)
                expectedFileCount = files.filter((f) => {
                  for (const ed of excludedDirs) {
                    if (f.startsWith(ed + '/')) return false
                  }
                  return true
                }).length
              }
            }

            // Optionally exclude a file (only if not already hidden by dir exclusion)
            if (fileExcludeIdx >= 0 && fileExcludeIdx < files.length) {
              const fileToExclude = files[fileExcludeIdx]

              // Check if file is visible (not hidden by dir exclusion)
              const fileElement = screen.queryByText(fileToExclude)
              if (fileElement) {
                const fileRow = fileElement.closest('div')
                const fileCheckbox = fileRow?.querySelector('input[type="checkbox"]')

                if (fileCheckbox) {
                  await userEvent.click(fileCheckbox)
                  excludedFiles.add(fileToExclude)
                  expectedFileCount -= 1
                }
              }
            }

            // Verify counts match expected
            const dirCountText =
              expectedDirCount === 1 ? '1 directory' : `${expectedDirCount} directories`
            const fileCountText = expectedFileCount === 1 ? '1 file' : `${expectedFileCount} files`

            expect(screen.getByText(new RegExp(dirCountText, 'i'))).toBeInTheDocument()
            expect(screen.getByText(new RegExp(fileCountText, 'i'))).toBeInTheDocument()

            unmount()
          }
        ),
        { numRuns: 10 }
      )
    }, 30000) // Increased timeout for heavy UI property tests
  })
})
