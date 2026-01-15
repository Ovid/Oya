import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { switchWorkspace, ApiError } from './client'

/**
 * Tests for switchWorkspace API function.
 *
 * Feature: oya-config-improvements
 * Validates: Requirements 3.3 - WHEN a user submits a directory path,
 * THE System SHALL call the backend API to switch workspaces
 */

describe('switchWorkspace', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    // Reset fetch mock before each test
    global.fetch = vi.fn()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('should call POST /api/repos/workspace with the provided path', async () => {
    const mockResponse = {
      status: {
        path: '/new/workspace',
        head_commit: 'abc123',
        head_message: 'Initial commit',
        branch: 'main',
        initialized: true,
        last_generation: null,
        generation_status: null,
      },
      message: 'Workspace switched successfully',
    }

    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    })

    const result = await switchWorkspace('/new/workspace')

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/repos/workspace'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
        body: JSON.stringify({ path: '/new/workspace' }),
      })
    )

    expect(result).toEqual(mockResponse)
  })

  it('should throw ApiError when the request fails', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 400,
      text: async () => 'Path does not exist',
      statusText: 'Bad Request',
    })

    await expect(switchWorkspace('/nonexistent/path')).rejects.toThrow(ApiError)
  })

  it('should throw ApiError with 403 status for paths outside allowed area', async () => {
    ;(global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 403,
      text: async () => 'Path is outside allowed workspace area',
      statusText: 'Forbidden',
    })

    try {
      await switchWorkspace('/etc/passwd')
      expect.fail('Should have thrown an error')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(403)
    }
  })
})
