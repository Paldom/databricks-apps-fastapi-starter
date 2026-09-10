import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  TextMessagePart,
} from '@assistant-ui/react'
import type {
  ChatStreamEvent,
  ChatStreamRequest,
  ChatStreamMessage,
} from '@/shared/api/generated/models'
import { parseNDJSON } from './ndjson-parser'
import { getAuthHeaders } from './get-auth-headers'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

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

    const res = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: getAuthHeaders(),
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

    for await (const event of parseNDJSON<ChatStreamEvent>(
      res.body,
      abortSignal
    )) {
      switch (event.type) {
        case 'text-delta':
          textContent += event.delta
          yield { content: [{ type: 'text' as const, text: textContent }] }
          break

        case 'tool-call-begin':
          toolCalls.set(event.tool_call_id, {
            toolName: event.tool_name,
            argsText: '',
          })
          break

        case 'tool-call-delta': {
          const tc = toolCalls.get(event.tool_call_id)
          if (tc) tc.argsText += event.args_delta
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
