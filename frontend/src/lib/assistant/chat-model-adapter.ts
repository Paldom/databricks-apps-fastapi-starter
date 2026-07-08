import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  TextMessagePart,
  ThreadAssistantMessagePart,
  ToolCallMessagePart,
} from '@assistant-ui/react'
import type {
  ChatStreamEvent,
  ChatStreamRequest,
  ChatStreamMessage,
} from '@/shared/api/generated/models'
import { parseNDJSON } from './ndjson-parser'

/** Strip trailing slashes without regex backtracking (sonar S8786). */
function stripTrailingSlashes(value: string): string {
  let end = value.length
  while (end > 0 && value[end - 1] === '/') end--
  return value.slice(0, end)
}

const API_BASE = stripTrailingSlashes(
  import.meta.env.VITE_API_BASE_URL ?? '/api'
)

/**
 * Best-effort parse of streamed tool-call argument text.
 * Returns {} while the JSON is still partial or is not an object.
 */
function parseArgs(argsText: string): ToolCallMessagePart['args'] {
  try {
    const parsed: unknown = JSON.parse(argsText)
    if (
      parsed !== null &&
      typeof parsed === 'object' &&
      !Array.isArray(parsed)
    ) {
      return parsed as ToolCallMessagePart['args']
    }
  } catch {
    // partial JSON during streaming
  }
  return {}
}

/**
 * Serialize assistant-ui ThreadMessage[] to the wire format.
 * V1: extract text content only. Images/files/tool-calls are dropped.
 */
function serializeMessages(
  messages: ChatModelRunOptions['messages']
): ChatStreamMessage[] {
  return messages.map((msg) => ({
    role: msg.role,
    content: msg.content
      .filter((part): part is TextMessagePart => part.type === 'text')
      .map((part) => part.text)
      .join(''),
  }))
}

export const chatModelAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal, unstable_threadId }) {
    const body: ChatStreamRequest = {
      thread_id: unstable_threadId,
      messages: serializeMessages(messages),
    }

    // Auth is handled server-side via Databricks forwarded headers; the
    // same-origin fetch needs no browser-managed credentials (matches
    // src/shared/api/client.ts).
    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: abortSignal,
    })

    if (!res.ok) {
      const text = await res.text().catch(() => 'Unknown error')
      throw new Error(`Chat stream failed (${res.status}): ${text}`)
    }

    if (!res.body) {
      throw new Error('Chat stream response has no body')
    }

    // Accumulate state across events
    let textContent = ''
    const toolCalls = new Map<string, { toolName: string; argsText: string }>()

    const buildContent = (): ThreadAssistantMessagePart[] => {
      const parts: ThreadAssistantMessagePart[] = []
      if (textContent) {
        parts.push({ type: 'text', text: textContent })
      }
      for (const [toolCallId, { toolName, argsText }] of toolCalls) {
        parts.push({
          type: 'tool-call',
          toolCallId,
          toolName,
          args: parseArgs(argsText),
          argsText,
        })
      }
      return parts
    }

    for await (const event of parseNDJSON<ChatStreamEvent>(
      res.body,
      abortSignal
    )) {
      switch (event.type) {
        case 'text-delta':
          textContent += event.delta
          yield { content: buildContent() }
          break

        case 'tool-call-begin':
          toolCalls.set(event.tool_call_id, {
            toolName: event.tool_name,
            argsText: '',
          })
          yield { content: buildContent() }
          break

        case 'tool-call-delta': {
          const toolCall = toolCalls.get(event.tool_call_id)
          // Deltas for unknown tool calls (no preceding begin) are dropped
          if (toolCall) {
            toolCall.argsText += event.args_delta
            yield { content: buildContent() }
          }
          break
        }

        case 'error':
          throw new Error(event.message)

        case 'done':
          break

        default:
          // Forward-compatible: ignore unknown event types
          break
      }
    }
  },
}
