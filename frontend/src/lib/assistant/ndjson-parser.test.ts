import { describe, expect, it, vi } from 'vitest'
import { parseNDJSON } from './ndjson-parser'

const encoder = new TextEncoder()

function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  let i = 0
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i]))
        i++
      } else {
        controller.close()
      }
    },
  })
}

async function collect<T>(gen: AsyncGenerator<T>): Promise<T[]> {
  const results: T[] = []
  for await (const item of gen) {
    results.push(item)
  }
  return results
}

describe('parseNDJSON', () => {
  it('parses multiple complete lines in a single chunk', async () => {
    const stream = makeStream(['{"type":"a"}\n{"type":"b"}\n'])
    const results = await collect(parseNDJSON(stream))
    expect(results).toEqual([{ type: 'a' }, { type: 'b' }])
  })

  it('handles lines split across chunks', async () => {
    const stream = makeStream(['{"type":"he', 'llo"}\n{"type":"world"}\n'])
    const results = await collect(parseNDJSON(stream))
    expect(results).toEqual([{ type: 'hello' }, { type: 'world' }])
  })

  it('skips blank lines', async () => {
    const stream = makeStream(['{"type":"a"}\n\n\n{"type":"b"}\n'])
    const results = await collect(parseNDJSON(stream))
    expect(results).toEqual([{ type: 'a' }, { type: 'b' }])
  })

  it('logs and skips malformed lines', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const stream = makeStream(['{"type":"a"}\nnot-json\n{"type":"b"}\n'])
    const results = await collect(parseNDJSON(stream))
    expect(results).toEqual([{ type: 'a' }, { type: 'b' }])
    expect(warn).toHaveBeenCalledWith('[ndjson] malformed line:', 'not-json')
    warn.mockRestore()
  })

  it('flushes remaining buffer without trailing newline', async () => {
    const stream = makeStream(['{"type":"last"}'])
    const results = await collect(parseNDJSON(stream))
    expect(results).toEqual([{ type: 'last' }])
  })

  it('stops iteration when signal is aborted', async () => {
    const controller = new AbortController()
    let pullCount = 0
    const stream = new ReadableStream<Uint8Array>({
      pull(ctrl) {
        pullCount++
        if (pullCount === 1) {
          ctrl.enqueue(encoder.encode('{"n":1}\n'))
        } else {
          controller.abort()
          ctrl.enqueue(encoder.encode('{"n":2}\n'))
        }
      },
    })

    const results = await collect(parseNDJSON(stream, controller.signal))
    expect(results).toEqual([{ n: 1 }])
  })

  it('handles an empty stream', async () => {
    const stream = makeStream([])
    const results = await collect(parseNDJSON(stream))
    expect(results).toEqual([])
  })
})
