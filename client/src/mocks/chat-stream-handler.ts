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

    const stream =
      overrideFn?.(body) ??
      new ReadableStream({
        start(controller) {
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
