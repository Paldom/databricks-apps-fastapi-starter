import { MemoryRouter } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { ChatShell } from './chat-shell'
import { resetUIStore, TestQueryWrapper } from '@/test/utils'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, waitFor } from '@testing-library/react'
import { useUIStore } from '@/shared/store/ui'
import { server } from '@/mocks/server'
import { db } from '@/mocks/data/seed'
import { http, HttpResponse } from 'msw'

describe('ChatShell', () => {
  beforeEach(() => {
    resetUIStore()
  })

  it('renders the assistant thread', () => {
    render(
      <TestQueryWrapper>
        <MemoryRouter>
          <ChatShell />
        </MemoryRouter>
      </TestQueryWrapper>
    )

    expect(
      screen.getByText('Start a conversation by typing a message below.')
    ).toBeInTheDocument()
  })

  it('renders the document sidebar when open', () => {
    resetUIStore({ documentSidebarOpen: true })

    const { container } = render(
      <TestQueryWrapper>
        <MemoryRouter>
          <ChatShell />
        </MemoryRouter>
      </TestQueryWrapper>
    )

    expect(screen.getByText('Documents')).toBeInTheDocument()
    expect(container.querySelector('[data-separator]')).toBeTruthy()
  })
})

it('creates My chats before sending the first message, then restores the stored turn on return', async () => {
  resetUIStore()
  db.reset()
  db.projects = []
  // Keep cached history when switching away, as the production QueryClient does.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ChatShell />
      </MemoryRouter>
    </QueryClientProvider>
  )
  fireEvent.change(screen.getByRole('textbox', { name: 'Message' }), {
    target: { value: 'First question' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
  await screen.findByText('Hello! This is a mock response.')
  expect(db.projects[0].name).toBe('My chats')
  const chatId = useUIStore.getState().activeChatId!
  expect(db.messages.get(chatId)).toHaveLength(2)
  expect(db.allChats.find((chat) => chat.id === chatId)?.title).toBe(
    'First question'
  )
  await waitFor(() =>
    expect(screen.getAllByText('First question').length).toBeGreaterThan(1)
  )
  act(() => useUIStore.getState().setActiveChatId(null))
  await screen.findByText('Start a conversation by typing a message below.')
  act(() => useUIStore.getState().setActiveChatId(chatId))
  await screen.findByText('Hello! This is a mock response.')
  expect(screen.getByText('[1] Example source snippet.')).toBeInTheDocument()
  expect(db.messages.get(chatId)).toHaveLength(2)
})

it('blocks the composer when history fails to load', async () => {
  resetUIStore({ activeChatId: 'missing-chat' })
  server.use(
    http.get(
      '*/api/chats/missing-chat/messages',
      () => new HttpResponse(null, { status: 404 })
    )
  )
  render(
    <TestQueryWrapper>
      <MemoryRouter>
        <ChatShell />
      </MemoryRouter>
    </TestQueryWrapper>
  )
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Could not load this conversation.'
  )
  expect(
    screen.queryByRole('textbox', { name: 'Message' })
  ).not.toBeInTheDocument()
})
