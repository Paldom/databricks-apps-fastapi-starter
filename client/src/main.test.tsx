import { describe, expect, it, vi, beforeEach } from 'vitest'

const renderMock = vi.fn()
const createRootMock = vi.fn(() => ({ render: renderMock }))

vi.mock('react-dom/client', () => ({
  default: { createRoot: createRootMock },
  createRoot: createRootMock,
}))

vi.mock('@/app/App', () => ({
  App: () => <div data-testid="app" />,
}))

vi.mock('@/mocks/browser', () => ({
  worker: {
    start: vi.fn().mockResolvedValue(undefined),
  },
}))

describe('main entry', () => {
  beforeEach(() => {
    vi.resetModules()
    renderMock.mockClear()
    createRootMock.mockClear()
    document.body.innerHTML = ''
  })

  it('mounts the application', async () => {
    document.body.innerHTML = '<div id="root"></div>'
    await import('./main')

    await vi.waitFor(() => {
      expect(createRootMock).toHaveBeenCalledWith(
        document.getElementById('root')
      )
      expect(renderMock).toHaveBeenCalled()
    })
  })

  it('throws if root element is missing', async () => {
    document.body.innerHTML = ''

    await expect(import('./main')).rejects.toThrow('Root element not found')
  })
})
