import { beforeEach, describe, expect, it, vi } from 'vitest'

const { requestMock, createMock } = vi.hoisted(() => ({
  requestMock: vi.fn(),
  createMock: vi.fn(),
}))

vi.mock('axios', () => {
  const create = createMock.mockImplementation(() => {
    return {
      defaults: {},
      interceptors: { request: { use: vi.fn() }, response: {} },
      request: requestMock,
    }
  })

  const axios = { create }

  return {
    __esModule: true,
    default: axios,
    create,
  }
})

// Import after mocks
import { customInstance } from './client'

describe('shared/api/client', () => {
  beforeEach(() => {
    requestMock.mockResolvedValue({ data: { ok: true } })
  })

  it('configures axios with base URL and timeout defaults', () => {
    const config = createMock.mock.calls[0]?.[0] as
      { baseURL?: string; timeout?: number } | undefined

    expect(config?.baseURL).toBe('/api')
    expect(config?.timeout).toBe(10000)
  })

  it('delegates to the axios instance and returns wrapped response', async () => {
    requestMock.mockResolvedValue({
      data: { ok: true },
      status: 200,
      headers: { 'content-type': 'application/json' },
    })

    const response = await customInstance<{
      data: { ok: boolean }
      status: number
      headers: Record<string, string>
    }>('/test', {
      method: 'GET',
    })

    expect(requestMock).toHaveBeenCalledWith({
      url: '/test',
      method: 'GET',
      data: undefined,
      headers: undefined,
      signal: undefined,
    })
    expect(response.data).toEqual({ ok: true })
    expect(response.status).toBe(200)
  })
})
