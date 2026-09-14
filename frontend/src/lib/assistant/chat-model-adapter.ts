import type {
  ChatModelAdapter,
  ChatModelRunOptions,
  TextMessagePart,
  ToolCallMessagePart,
} from '@assistant-ui/react'
import type {
  ChatStreamEvent,
  ChatStreamRequest,
  ChatStreamMessage,
} from '@/shared/api/generated/models'
import { parseNDJSON } from './ndjson-parser'
import { getAuthHeaders } from './get-auth-headers'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

type ContentPart = TextMessagePart | ToolCallMessagePart

/** The backend keeps the transcript; only the new user message travels. */
function serializeMessages(
  messages: ChatModelRunOptions['messages']
): ChatStreamMessage[] {
  const last = [...messages].reverse().find((msg) => msg.role === 'user')
  if (!last) return []
  return [
    {
      role: 'user',
      content: last.content
        .filter((part): part is TextMessagePart => part.type === 'text')
        .map((part) => part.text)
        .join(''),
    },
  ]
}

export function createChatModelAdapter(
  chatId: string,
  onDone?: () => void
): ChatModelAdapter {
  return {
    async *run({ messages, abortSignal }) {
      const body: ChatStreamRequest = {
        thread_id: chatId,
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
      if (!res.body) throw new Error('Chat stream response has no body')

      let parts: ContentPart[] = []
      for await (const event of parseNDJSON<ChatStreamEvent>(
        res.body,
        abortSignal
      )) {
        switch (event.type) {
          case 'heartbeat':
            continue
          case 'text-delta': {
            const last = parts[parts.length - 1]
            if (last?.type === 'text') {
              parts = [
                ...parts.slice(0, -1),
                { ...last, text: last.text + event.delta },
              ]
            } else {
              parts = [...parts, { type: 'text', text: event.delta }]
            }
            break
          }
          case 'tool-call-begin':
            parts = [
              ...parts,
              {
                type: 'tool-call',
                toolCallId: event.tool_call_id,
                toolName: event.tool_name,
                args: {},
                argsText: '',
              },
            ]
            break
          case 'tool-call-delta':
            parts = parts.map((part) => {
              if (
                part.type !== 'tool-call' ||
                part.toolCallId !== event.tool_call_id
              )
                return part
              const argsText = part.argsText + event.args_delta
              let args = part.args
              try {
                const parsed: unknown = JSON.parse(argsText)
                if (
                  parsed !== null &&
                  typeof parsed === 'object' &&
                  !Array.isArray(parsed)
                ) {
                  args = parsed as ToolCallMessagePart['args']
                }
              } catch {
                // Arguments arrive in fragments; retain the last complete object.
              }
              return { ...part, argsText, args }
            })
            break
          case 'tool-result':
            parts = parts.map((part) =>
              part.type === 'tool-call' &&
              part.toolCallId === event.tool_call_id
                ? { ...part, result: event.result, isError: event.is_error }
                : part
            )
            break
          case 'error':
            throw new Error(`${event.message} (trace ${event.trace_id})`)
          case 'done':
            onDone?.()
            yield {
              content: [...parts],
              metadata: { custom: { traceId: event.trace_id } },
            }
            return
          default:
            continue
        }
        yield { content: [...parts] }
      }
      throw new Error('stream ended without a terminal event')
    },
  }
}
