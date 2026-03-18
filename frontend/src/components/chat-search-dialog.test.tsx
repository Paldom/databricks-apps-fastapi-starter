import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { ChatSearchDialog } from './chat-search-dialog'
import { resetUIStore, createTestQueryClient } from '@/test/utils'
import { useUIStore } from '@/shared/store/ui'
import { QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/mocks/server'
import { http, HttpResponse } from 'msw'

function renderDialog() {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <ChatSearchDialog />
    </QueryClientProvider>
  )
}

describe('ChatSearchDialog', () => {
  beforeEach(() => {
    resetUIStore()
  })

  it('opens with the keyboard shortcut', () => {
    renderDialog()

    fireEvent.keyDown(document, { key: 'k', metaKey: true })
    expect(useUIStore.getState().searchDialogOpen).toBe(true)
  })

  it('toggles closed with the keyboard shortcut', () => {
    resetUIStore({ searchDialogOpen: true })
    renderDialog()

    fireEvent.keyDown(document, { key: 'k', metaKey: true })
    expect(useUIStore.getState().searchDialogOpen).toBe(false)
  })

  it('shows recent chats when opened with no query', async () => {
    resetUIStore({ searchDialogOpen: true })
    renderDialog()

    await waitFor(() => {
      expect(screen.getByText('Recent chats')).toBeInTheDocument()
    })
  })

  it('shows search results when user types a query', async () => {
    server.use(
      http.get('*/api/chats/search', ({ request }) => {
        const url = new URL(request.url)
        const q = url.searchParams.get('q') ?? ''
        return HttpResponse.json({
          items: [
            {
              id: 'found-1',
              title: `Result for ${q}`,
              projectId: 'p1',
              projectName: 'TestProject',
              createdAt: '2024-01-01T00:00:00Z',
              updatedAt: '2024-01-01T00:00:00Z',
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      })
    )

    const user = userEvent.setup()
    resetUIStore({ searchDialogOpen: true })
    renderDialog()

    const input = screen.getByPlaceholderText('Search chats...')
    await user.type(input, 'test')

    await waitFor(() => {
      expect(screen.getByText('TestProject')).toBeInTheDocument()
      expect(screen.getByText('Result for test')).toBeInTheDocument()
    })
  })

  it('shows empty state when search returns no results', async () => {
    server.use(
      http.get('*/api/chats/search', () => {
        return HttpResponse.json({
          items: [],
          nextCursor: null,
          hasMore: false,
        })
      })
    )

    const user = userEvent.setup()
    resetUIStore({ searchDialogOpen: true })
    renderDialog()

    const input = screen.getByPlaceholderText('Search chats...')
    await user.type(input, 'nonexistent')

    await waitFor(() => {
      expect(screen.getByText('No chats found.')).toBeInTheDocument()
    })
  })

  it('selects a search result and closes the dialog', async () => {
    server.use(
      http.get('*/api/chats/search', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'chat-x',
              title: 'Test Chat',
              projectId: 'proj-x',
              projectName: 'Project X',
              createdAt: '2024-01-01T00:00:00Z',
              updatedAt: '2024-01-01T00:00:00Z',
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      })
    )

    const user = userEvent.setup()
    resetUIStore({ searchDialogOpen: true })
    renderDialog()

    const input = screen.getByPlaceholderText('Search chats...')
    await user.type(input, 'test')

    await waitFor(() => {
      expect(screen.getByText('Test Chat')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Test Chat'))

    const state = useUIStore.getState()
    expect(state.activeChatId).toBe('chat-x')
    expect(state.activeProjectId).toBe('proj-x')
    expect(state.searchDialogOpen).toBe(false)
  })

  it('shows load more when hasMore is true', async () => {
    server.use(
      http.get('*/api/chats/search', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'c1',
              title: 'First result',
              projectId: 'p1',
              projectName: 'P1',
              createdAt: '2024-01-01T00:00:00Z',
              updatedAt: '2024-01-01T00:00:00Z',
            },
          ],
          nextCursor: 'c1',
          hasMore: true,
        })
      })
    )

    const user = userEvent.setup()
    resetUIStore({ searchDialogOpen: true })
    renderDialog()

    const input = screen.getByPlaceholderText('Search chats...')
    await user.type(input, 'test')

    await waitFor(() => {
      expect(screen.getByText('Load more')).toBeInTheDocument()
    })
  })

  it('shows empty state when recent chats is empty and no query', async () => {
    server.use(
      http.get('*/api/chats/recent', () => {
        return HttpResponse.json({
          items: [],
          nextCursor: null,
          hasMore: false,
        })
      })
    )

    resetUIStore({ searchDialogOpen: true })
    renderDialog()

    await waitFor(() => {
      expect(screen.getByText('No chats found.')).toBeInTheDocument()
    })
  })
})
