import { http, HttpResponse } from 'msw'
import type { ChatStreamRequest } from '@/shared/api/generated/models'
import { db } from './data/seed'

const encoder = new TextEncoder()

function ndjsonLine(data: Record<string, unknown>): Uint8Array {
  return encoder.encode(JSON.stringify(data) + '\n')
}

export function getChatStreamMockHandler(
  overrideFn?: (body: unknown) => ReadableStream<Uint8Array>
) {
  return http.post('*/api/chat/stream', async ({ request }) => {
    const body = (await request.json()) as ChatStreamRequest
    if (!body.thread_id || typeof body.thread_id !== 'string') {
      return HttpResponse.json(
        { detail: 'thread_id is required' },
        { status: 422 }
      )
    }
    const chat = db.allChats.find((chat) => chat.id === body.thread_id)
    if (!overrideFn && !chat) return new HttpResponse(null, { status: 404 })
    const text = 'Hello! This is a mock response.'
    const result = '[1] Example source snippet.'
    const parts = [
      {
        type: 'tool-call',
        toolCallId: 'source-1',
        toolName: 'knowledge_assistant',
        args: { query: 'example' },
        argsText: '{"query":"example"}',
        result,
        isError: false,
      },
      { type: 'text', text },
    ]
    const stream =
      overrideFn?.(body) ??
      new ReadableStream({
        start(controller) {
          const emit = (event: Record<string, unknown>) =>
            controller.enqueue(ndjsonLine(event))
          emit({ type: 'heartbeat' })
          emit({
            type: 'tool-call-begin',
            tool_call_id: 'source-1',
            tool_name: 'knowledge_assistant',
          })
          emit({
            type: 'tool-call-delta',
            tool_call_id: 'source-1',
            args_delta: '{"query":"example"}',
          })
          emit({
            type: 'tool-result',
            tool_call_id: 'source-1',
            result,
            is_error: false,
          })
          emit({ type: 'text-delta', delta: text })
          const user = [...body.messages]
            .reverse()
            .find((message) => message.role === 'user')
          const createdAt = new Date().toISOString()
          if (user) {
            const messages = db.messages.get(body.thread_id) ?? []
            messages.push({
              id: crypto.randomUUID(),
              role: 'user',
              content: user.content,
              parts: [],
              createdAt,
            })
            messages.push({
              id: crypto.randomUUID(),
              role: 'assistant',
              content: text,
              parts,
              traceId: 'mock-trace',
              createdAt,
            })
            db.messages.set(body.thread_id, messages)
            if (chat && !chat.title) chat.title = user.content.slice(0, 60)
          }
          emit({
            type: 'done',
            finish_reason: 'stop',
            thread_id: body.thread_id,
            trace_id: 'mock-trace',
          })
          controller.close()
        },
      })
    return new HttpResponse(stream, {
      headers: { 'Content-Type': 'application/x-ndjson' },
    })
  })
}
