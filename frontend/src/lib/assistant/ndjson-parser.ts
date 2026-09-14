/**
 * Try to parse a single NDJSON line. Returns the parsed value or undefined.
 */
function tryParseLine<T>(line: string): T | undefined {
  const trimmed = line.trim()
  if (trimmed === '') return undefined
  try {
    return JSON.parse(trimmed) as T
  } catch {
    console.warn('[ndjson] malformed line:', trimmed)
    return undefined
  }
}

/**
 * Yields parsed JSON objects from an NDJSON ReadableStream.
 * Handles lines split across chunk boundaries, skips blank lines,
 * and logs malformed lines without crashing.
 */
export async function* parseNDJSON<T>(
  stream: ReadableStream<Uint8Array>,
  signal?: AbortSignal
): AsyncGenerator<T, void, undefined> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      if (signal?.aborted) return

      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()!

      for (const line of lines) {
        const parsed = tryParseLine<T>(line)
        if (parsed !== undefined) yield parsed
      }
    }

    // Flush remaining buffer
    const parsed = tryParseLine<T>(buffer)
    if (parsed !== undefined) yield parsed
  } finally {
    reader.releaseLock()
  }
}
