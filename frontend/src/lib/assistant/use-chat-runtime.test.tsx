import { describe, expect, it } from 'vitest'
import { renderHook } from '@testing-library/react'
import { TestQueryWrapper } from '@/test/utils'
import { useChatRuntime } from './use-chat-runtime'
import { loadChatHistory, mapChatMessage } from './use-chat-runtime'
import { server } from '@/mocks/server'
import { http, HttpResponse } from 'msw'

describe('useChatRuntime', () => {
  it('returns a truthy runtime', () => {
    const { result } = renderHook(() => useChatRuntime('chat-1'), {
      wrapper: TestQueryWrapper,
    })
    expect(result.current).toBeTruthy()
  })
})

const storedMessage = {
  id: 'm1',
  role: 'assistant',
  content: 'Answer',
  createdAt: '2026-01-01T00:00:00Z',
  traceId: 'trace-1',
  parts: [
    {
      type: 'tool-call',
      toolCallId: 'tool-1',
      toolName: 'genie',
      args: { query: 'sales' },
      argsText: '{"query":"sales"}',
      result: { text: '42' },
      isError: false,
    },
    { type: 'text', text: 'Answer' },
  ],
}

it('maps assistant parts verbatim, user text and trace metadata', () => {
  const mapped = mapChatMessage(storedMessage)
  expect(mapped.content).toBe(storedMessage.parts)
  expect(mapped).toMatchObject({
    id: 'm1',
    role: 'assistant',
    metadata: { custom: { traceId: 'trace-1' } },
    createdAt: new Date(storedMessage.createdAt),
  })
  expect(mapChatMessage({ ...storedMessage, role: 'user' }).content).toEqual([
    { type: 'text', text: 'Answer' },
  ])
  expect(mapChatMessage({ ...storedMessage, parts: [] }).content).toEqual([
    { type: 'text', text: 'Answer' },
  ])
})

it('loads all history pages in order with the requested page size', async () => {
  const cursors: (string | null)[] = []
  server.use(
    http.get('*/api/chats/c1/messages', ({ request }) => {
      const url = new URL(request.url)
      expect(url.searchParams.get('limit')).toBe('200')
      const cursor = url.searchParams.get('cursor')
      cursors.push(cursor)
      return HttpResponse.json({
        items: [{ ...storedMessage, id: cursor ? 'm2' : 'm1' }],
        nextCursor: cursor ? null : 'm1',
        hasMore: !cursor,
      })
    })
  )
  const messages = await loadChatHistory('c1')
  expect(cursors).toEqual([null, 'm1'])
  expect(messages.map((message) => message.id)).toEqual(['m1', 'm2'])
})
