import { beforeEach, describe, expect, it, vi } from 'vitest'

interface AxiosConfig {
  headers: Record<string, string | undefined>
  [key: string]: unknown
}

const { requestMock, interceptorRef, createMock } = vi.hoisted(() => ({
  requestMock: vi.fn(),
  interceptorRef: {
    current: undefined as ((config: AxiosConfig) => AxiosConfig) | undefined,
  },
  createMock: vi.fn(),
}))

vi.mock('axios', () => {
  const create = createMock.mockImplementation(() => {
    const interceptors = {
      request: {
        use: (handler: (config: AxiosConfig) => AxiosConfig) => {
          interceptorRef.current = handler
          return handler
        },
      },
      response: {},
    }

    return {
      defaults: {},
      interceptors,
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
    localStorage.clear()
  })

  it('attaches bearer token from localStorage when present', () => {
    localStorage.setItem('authToken', 'token-123')
    const initialConfig: AxiosConfig = { headers: {} }
    const config = interceptorRef.current?.(initialConfig) ?? initialConfig

    expect(config.headers.Authorization).toBe('Bearer token-123')
  })

  it('configures axios with base URL and timeout defaults', () => {
    const config = createMock.mock.calls[0]?.[0] as
      | { baseURL?: string; timeout?: number }
      | undefined

    expect(config?.baseURL).toBe('/api')
    expect(config?.timeout).toBe(10000)
  })

  it('skips localStorage when window is undefined', () => {
    const getItem = vi.spyOn(localStorage, 'getItem')
    const originalWindow = globalThis.window
    // @ts-expect-error - simulate non-browser environment
    globalThis.window = undefined

    const initialConfig: AxiosConfig = { headers: {} }
    interceptorRef.current?.(initialConfig)

    expect(getItem).not.toHaveBeenCalled()

    globalThis.window = originalWindow
    getItem.mockRestore()
  })

  it('leaves headers unchanged when no token exists', () => {
    const initialConfig: AxiosConfig = { headers: {} }
    const config = interceptorRef.current?.(initialConfig) ?? initialConfig

    expect(config.headers.Authorization).toBeUndefined()
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
