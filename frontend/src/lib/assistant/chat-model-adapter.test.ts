import { describe, expect, it, beforeEach, afterEach } from 'vitest'
import { server } from '@/mocks/server'
import { getChatStreamMockHandler } from '@/mocks/chat-stream-handler'
import { http, HttpResponse } from 'msw'
import { createChatModelAdapter } from './chat-model-adapter'
import type {
  ChatModelRunOptions,
  ChatModelRunResult,
} from '@assistant-ui/react'

const chatModelAdapter = createChatModelAdapter('chat-1')

const encoder = new TextEncoder()

function ndjsonLine(data: Record<string, unknown>): Uint8Array {
  return encoder.encode(JSON.stringify(data) + '\n')
}

const baseMetadata = { custom: {} }

function makeUserMessage(text: string, id = 'msg-1') {
  return {
    id,
    role: 'user' as const,
    createdAt: new Date(),
    content: [{ type: 'text' as const, text }],
    attachments: [],
    metadata: baseMetadata,
  }
}

function makeRunOptions(
  overrides: Partial<ChatModelRunOptions> = {}
): ChatModelRunOptions {
  const msg = makeUserMessage('Hello')
  return {
    messages: [msg],
    abortSignal: new AbortController().signal,
    runConfig: {},
    context: {
      useModelConfig: () => ({}),
    },
    config: {
      useModelConfig: () => ({}),
    },
    unstable_getMessage: () => msg,
    ...overrides,
  } as ChatModelRunOptions
}

async function consumeGenerator(
  gen: ReturnType<typeof chatModelAdapter.run>
): Promise<ChatModelRunResult[]> {
  const results: ChatModelRunResult[] = []
  if (Symbol.asyncIterator in Object(gen)) {
    for await (const result of gen as AsyncGenerator<ChatModelRunResult>) {
      results.push(result)
    }
  }
  return results
}

describe('chatModelAdapter', () => {
  beforeEach(() => {
    server.use(getChatStreamMockHandler())
  })

  afterEach(() => {
    globalThis.localStorage.removeItem('authToken')
  })

  it('yields cumulative text content from text-delta events', async () => {
    server.use(
      getChatStreamMockHandler(
        () =>
          new ReadableStream({
            start(controller) {
              controller.enqueue(
                ndjsonLine({ type: 'text-delta', delta: 'Hello' })
              )
              controller.enqueue(
                ndjsonLine({ type: 'text-delta', delta: ' world' })
              )
              controller.enqueue(
                ndjsonLine({ type: 'done', finish_reason: 'stop' })
              )
              controller.close()
            },
          })
      )
    )

    const results = await consumeGenerator(
      chatModelAdapter.run(makeRunOptions())
    )

    expect(results).toHaveLength(3)
    expect(results[0]).toEqual({
      content: [{ type: 'text', text: 'Hello' }],
    })
    expect(results[1]).toEqual({
      content: [{ type: 'text', text: 'Hello world' }],
    })
  })

  it('throws on HTTP error responses', async () => {
    server.use(
      http.post(
        '*/api/chat/stream',
        () => new HttpResponse('Service unavailable', { status: 503 })
      )
    )

    await expect(
      consumeGenerator(chatModelAdapter.run(makeRunOptions()))
    ).rejects.toThrow('Chat stream failed (503)')
  })

  it('throws on in-stream error events', async () => {
    server.use(
      getChatStreamMockHandler(
        () =>
          new ReadableStream({
            start(controller) {
              controller.enqueue(
                ndjsonLine({
                  type: 'error',
                  message: 'Rate limit exceeded',
                  code: 'rate_limit',
                  trace_id: 'trace-error',
                })
              )
              controller.close()
            },
          })
      )
    )

    await expect(
      consumeGenerator(chatModelAdapter.run(makeRunOptions()))
    ).rejects.toThrow('Rate limit exceeded (trace trace-error)')
  })

  it('sends Content-Type header without Authorization (auth is server-side)', async () => {
    let capturedHeaders: Headers | undefined

    server.use(
      http.post('*/api/chat/stream', ({ request }) => {
        capturedHeaders = request.headers

        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(ndjsonLine({ type: 'text-delta', delta: 'ok' }))
            controller.enqueue(
              ndjsonLine({ type: 'done', finish_reason: 'stop' })
            )
            controller.close()
          },
        })

        return new HttpResponse(stream, {
          headers: { 'Content-Type': 'application/x-ndjson' },
        })
      })
    )

    globalThis.localStorage.setItem('authToken', 'test-token-123')
    await consumeGenerator(chatModelAdapter.run(makeRunOptions()))

    expect(capturedHeaders?.get('Content-Type')).toBe('application/json')
    expect(capturedHeaders?.get('Authorization')).toBeNull()
  })

  it('throws when response body is null', async () => {
    server.use(
      http.post('*/api/chat/stream', () => {
        return new HttpResponse(null, {
          status: 200,
          headers: { 'Content-Type': 'application/x-ndjson' },
        })
      })
    )

    await expect(
      consumeGenerator(chatModelAdapter.run(makeRunOptions()))
    ).rejects.toThrow('Chat stream response has no body')
  })

  it('yields tool-call-begin and tool-call-delta events', async () => {
    server.use(
      getChatStreamMockHandler(
        () =>
          new ReadableStream({
            start(controller) {
              controller.enqueue(
                ndjsonLine({
                  type: 'tool-call-begin',
                  tool_call_id: 'tc1',
                  tool_name: 'search',
                })
              )
              controller.enqueue(
                ndjsonLine({
                  type: 'tool-call-delta',
                  tool_call_id: 'tc1',
                  args_delta: '{"q":"hello"}',
                })
              )
              controller.enqueue(
                ndjsonLine({ type: 'done', finish_reason: 'stop' })
              )
              controller.close()
            },
          })
      )
    )

    const results = await consumeGenerator(
      chatModelAdapter.run(makeRunOptions())
    )
    expect(results).toHaveLength(3)
    expect(results[1].content).toEqual([
      {
        type: 'tool-call',
        toolCallId: 'tc1',
        toolName: 'search',
        argsText: '{"q":"hello"}',
        args: { q: 'hello' },
      },
    ])
  })

  it('ignores tool-call-delta for unknown tool_call_id', async () => {
    server.use(
      getChatStreamMockHandler(
        () =>
          new ReadableStream({
            start(controller) {
              controller.enqueue(
                ndjsonLine({
                  type: 'tool-call-delta',
                  tool_call_id: 'unknown',
                  args_delta: 'ignored',
                })
              )
              controller.enqueue(
                ndjsonLine({ type: 'text-delta', delta: 'ok' })
              )
              controller.enqueue(
                ndjsonLine({ type: 'done', finish_reason: 'stop' })
              )
              controller.close()
            },
          })
      )
    )

    const results = await consumeGenerator(
      chatModelAdapter.run(makeRunOptions())
    )
    expect(results).toHaveLength(3)
    expect(results[1]).toEqual({ content: [{ type: 'text', text: 'ok' }] })
  })

  it('ignores unknown event types', async () => {
    server.use(
      getChatStreamMockHandler(
        () =>
          new ReadableStream({
            start(controller) {
              controller.enqueue(
                ndjsonLine({ type: 'some-future-event', data: 'test' })
              )
              controller.enqueue(
                ndjsonLine({ type: 'text-delta', delta: 'Hi' })
              )
              controller.enqueue(
                ndjsonLine({ type: 'done', finish_reason: 'stop' })
              )
              controller.close()
            },
          })
      )
    )

    const results = await consumeGenerator(
      chatModelAdapter.run(makeRunOptions())
    )
    expect(results).toHaveLength(2)
    expect(results[0]).toEqual({ content: [{ type: 'text', text: 'Hi' }] })
  })

  it('sends only supported request fields with serialized text messages', async () => {
    let capturedBody: Record<string, unknown> | undefined

    server.use(
      http.post('*/api/chat/stream', async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>

        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(ndjsonLine({ type: 'text-delta', delta: 'ok' }))
            controller.enqueue(
              ndjsonLine({ type: 'done', finish_reason: 'stop' })
            )
            controller.close()
          },
        })

        return new HttpResponse(stream, {
          headers: { 'Content-Type': 'application/x-ndjson' },
        })
      })
    )

    const options = makeRunOptions({
      unstable_threadId: 'thread-1',
      runConfig: { custom: { temperature: 0.5 } },
      messages: [
        {
          id: 'empty-assistant',
          role: 'assistant',
          createdAt: new Date(),
          content: [
            {
              type: 'tool-call',
              toolCallId: 'previous-tool',
              toolName: 'genie',
              args: {},
              argsText: '{}',
              result: '42',
            },
          ],
          status: { type: 'complete', reason: 'stop' },
          metadata: {
            custom: {},
            unstable_state: null,
            unstable_annotations: [],
            unstable_data: [],
            steps: [],
          },
        },
        {
          id: 'msg-1',
          role: 'user' as const,
          createdAt: new Date(),
          content: [
            { type: 'text' as const, text: 'part one' },
            { type: 'text' as const, text: ' part two' },
          ],
          attachments: [],
          metadata: baseMetadata,
        },
      ],
    })

    await consumeGenerator(chatModelAdapter.run(options))

    expect(capturedBody).toEqual({
      thread_id: 'chat-1',
      messages: [{ role: 'user', content: 'part one part two' }],
    })
  })
})

function mockEvents(events: Record<string, unknown>[]) {
  server.use(
    getChatStreamMockHandler(
      () =>
        new ReadableStream({
          start(controller) {
            events.forEach((event) => controller.enqueue(ndjsonLine(event)))
            controller.close()
          },
        })
    )
  )
}

it('preserves ordered parts, fragmented arguments, results and the final trace', async () => {
  mockEvents([
    { type: 'text-delta', delta: 'Before' },
    { type: 'tool-call-begin', tool_call_id: 't1', tool_name: 'genie' },
    { type: 'tool-call-delta', tool_call_id: 't1', args_delta: '{"q":' },
    { type: 'heartbeat' },
    { type: 'tool-call-delta', tool_call_id: 't1', args_delta: '"sales"}' },
    {
      type: 'tool-result',
      tool_call_id: 't1',
      result: { text: '42', sql: 'SELECT 42' },
      is_error: false,
    },
    { type: 'text-delta', delta: 'After' },
    {
      type: 'done',
      finish_reason: 'stop',
      thread_id: 'chat-1',
      trace_id: 'trace-1',
    },
  ])
  const results = await consumeGenerator(chatModelAdapter.run(makeRunOptions()))
  expect(results).toHaveLength(7)
  expect(results[2].content?.[1]).toMatchObject({ args: {}, argsText: '{"q":' })
  expect(results[results.length - 1]).toEqual({
    content: [
      { type: 'text', text: 'Before' },
      {
        type: 'tool-call',
        toolCallId: 't1',
        toolName: 'genie',
        args: { q: 'sales' },
        argsText: '{"q":"sales"}',
        result: { text: '42', sql: 'SELECT 42' },
        isError: false,
      },
      { type: 'text', text: 'After' },
    ],
    metadata: { custom: { traceId: 'trace-1' } },
  })
})

it('throws if the stream has no terminal event', async () => {
  mockEvents([{ type: 'text-delta', delta: 'Partial' }])
  await expect(
    consumeGenerator(chatModelAdapter.run(makeRunOptions()))
  ).rejects.toThrow('stream ended without a terminal event')
})
