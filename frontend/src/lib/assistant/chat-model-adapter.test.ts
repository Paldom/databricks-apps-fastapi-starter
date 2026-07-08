import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { server } from '@/mocks/server'
import { getChatStreamMockHandler } from '@/mocks/chat-stream-handler'
import { http, HttpResponse } from 'msw'
import { chatModelAdapter } from './chat-model-adapter'
import type {
  ChatModelRunOptions,
  ChatModelRunResult,
} from '@assistant-ui/react'

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
    config: {},
    runConfig: {},
    context: {},
    unstable_getMessage: () => msg,
    ...overrides,
  }
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
    vi.unstubAllEnvs()
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

    expect(results).toHaveLength(2)
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
                ndjsonLine({ type: 'error', message: 'Rate limit exceeded' })
              )
              controller.close()
            },
          })
      )
    )

    await expect(
      consumeGenerator(chatModelAdapter.run(makeRunOptions()))
    ).rejects.toThrow('Rate limit exceeded')
  })

  it('sends a JSON request without browser-managed auth headers', async () => {
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

    await consumeGenerator(chatModelAdapter.run(makeRunOptions()))

    expect(capturedHeaders?.get('Content-Type')).toBe('application/json')
    // Auth comes from Databricks forwarded headers server-side.
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

  it('yields tool-call parts with accumulated args from tool-call events', async () => {
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
                  args_delta: '{"q":',
                })
              )
              controller.enqueue(
                ndjsonLine({
                  type: 'tool-call-delta',
                  tool_call_id: 'tc1',
                  args_delta: '"hello"}',
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
    expect(results[0]).toEqual({
      content: [
        {
          type: 'tool-call',
          toolCallId: 'tc1',
          toolName: 'search',
          args: {},
          argsText: '',
        },
      ],
    })
    // Partial JSON: argsText accumulates, args stays {} until parseable
    expect(results[1]).toEqual({
      content: [
        {
          type: 'tool-call',
          toolCallId: 'tc1',
          toolName: 'search',
          args: {},
          argsText: '{"q":',
        },
      ],
    })
    expect(results[2]).toEqual({
      content: [
        {
          type: 'tool-call',
          toolCallId: 'tc1',
          toolName: 'search',
          args: { q: 'hello' },
          argsText: '{"q":"hello"}',
        },
      ],
    })
  })

  it('yields text and tool-call parts together, dropping deltas for unknown tool calls', async () => {
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
                ndjsonLine({
                  type: 'tool-call-begin',
                  tool_call_id: 'tc1',
                  tool_name: 'lookup',
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

    // The orphan delta yields nothing; begin and text-delta yield once each
    expect(results).toHaveLength(2)
    expect(results[1]).toEqual({
      content: [
        { type: 'text', text: 'ok' },
        {
          type: 'tool-call',
          toolCallId: 'tc1',
          toolName: 'lookup',
          args: {},
          argsText: '',
        },
      ],
    })
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
    expect(results).toHaveLength(1)
    expect(results[0]).toEqual({ content: [{ type: 'text', text: 'Hi' }] })
  })

  it.each([
    ['/', '/chat/stream'],
    ['/api/', '/api/chat/stream'],
  ])(
    'strips trailing slashes from API base %s when building the URL',
    async (base, expectedPath) => {
      vi.stubEnv('VITE_API_BASE_URL', base)
      vi.resetModules()
      const { chatModelAdapter: adapter } = await import('./chat-model-adapter')

      let capturedUrl: string | undefined
      server.use(
        http.post('*/chat/stream', ({ request }) => {
          capturedUrl = request.url

          const stream = new ReadableStream({
            start(controller) {
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

      await consumeGenerator(adapter.run(makeRunOptions()))

      expect(capturedUrl).toBeDefined()
      expect(new URL(capturedUrl!).pathname).toBe(expectedPath)
    }
  )

  it('serializes only text parts from messages', async () => {
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
      messages: [
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

    expect(capturedBody?.messages).toEqual([
      { role: 'user', content: 'part one part two' },
    ])
  })
})
