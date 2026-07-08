import { http, HttpResponse } from 'msw'

const encoder = new TextEncoder()

function ndjsonLine(data: Record<string, unknown>): Uint8Array {
  return encoder.encode(JSON.stringify(data) + '\n')
}

/**
 * MSW handler for POST /api/chat/stream.
 * Default: streams a canned NDJSON response.
 * Tests can override via server.use(getChatStreamMockHandler(customFn)).
 */
export function getChatStreamMockHandler(
  overrideFn?: (body: unknown) => ReadableStream<Uint8Array>
) {
  return http.post('*/api/chat/stream', async ({ request }) => {
    const body: unknown = await request.json()

    const messages = (
      body as { messages?: { role?: string; content?: string }[] }
    ).messages
    const lastContent = messages?.[messages.length - 1]?.content ?? ''
    // Say "tool" in a message to see the tool-call rendering path in dev
    const withToolCall = /tool/i.test(lastContent)

    const stream =
      overrideFn?.(body) ??
      new ReadableStream({
        start(controller) {
          if (withToolCall) {
            controller.enqueue(
              ndjsonLine({
                type: 'tool-call-begin',
                tool_call_id: 'call_1',
                tool_name: 'search_documents',
              })
            )
            controller.enqueue(
              ndjsonLine({
                type: 'tool-call-delta',
                tool_call_id: 'call_1',
                args_delta: '{"query":',
              })
            )
            controller.enqueue(
              ndjsonLine({
                type: 'tool-call-delta',
                tool_call_id: 'call_1',
                args_delta: '"mock docs"}',
              })
            )
          }
          const words = ['Hello! ', 'This ', 'is ', 'a ', 'mock ', 'response.']
          for (const w of words) {
            controller.enqueue(ndjsonLine({ type: 'text-delta', delta: w }))
          }
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
}
