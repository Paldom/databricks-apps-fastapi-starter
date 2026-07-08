# Assistant UI integration

How the chat experience is wired, from keystroke to streamed markdown. The
library is `@assistant-ui/react` (0.14.x) using **LocalRuntime** with a custom
`ChatModelAdapter` — the backend contract is plain NDJSON over HTTP, no
assistant-ui cloud services involved.

## Data flow

```
ChatShell
  └─ AssistantRuntimeProvider (runtime from useChatRuntime(activeChatId))
       └─ AssistantThread (Thread/Composer/Message primitives)

send message
  → LocalRuntime calls chatModelAdapter.run({ messages, abortSignal, ... })
  → POST {VITE_API_BASE_URL}/chat/stream   (native fetch, NDJSON response)
  → parseNDJSON() yields one JSON event per line
  → adapter accumulates text + tool calls, yields assistant-ui content parts
  → MessagePrimitive.Content renders text via MarkdownText,
    tool calls via ToolFallback
```

## The wire protocol

`POST /chat/stream` (defined in `../backend/openapi.yaml`, tag `chat`) accepts
`{ thread_id, messages: [{ role, content }], run_config }` and responds with
`application/x-ndjson`, one event per line:

| event             | fields                       | adapter behavior                          |
| ----------------- | ---------------------------- | ----------------------------------------- |
| `text-delta`      | `delta`                      | append to text part, yield                |
| `tool-call-begin` | `tool_call_id`, `tool_name`  | open a tool-call part                     |
| `tool-call-delta` | `tool_call_id`, `args_delta` | append `argsText`, re-parse `args`, yield |
| `error`           | `message`                    | throw (LocalRuntime shows the error)      |
| `done`            | `finish_reason`              | end of stream                             |

Unknown event types are ignored (forward compatibility). The event schemas are
part of the OpenAPI spec, so `ChatStreamEvent` types are generated — but the
**client** for this endpoint is hand-written: react-query cannot represent an
NDJSON stream, which is why the `chat` tag is excluded in `orval.config.ts`.

## Key files

- `src/lib/assistant/chat-model-adapter.ts` — the `ChatModelAdapter`. An async
  generator: serializes thread messages to the wire format, fetches same-origin
  (auth is handled server-side via Databricks forwarded headers, like the axios
  client), iterates `parseNDJSON`, and yields the full accumulated content
  array on every event (text part first, then tool-call parts in arrival
  order — assistant-ui replaces message content wholesale per yield).
- `src/lib/assistant/ndjson-parser.ts` — `ReadableStream → AsyncGenerator<T>`.
  Handles lines split across chunks, blank lines, malformed lines (warn +
  skip), abort signals, and cancels the reader on early exit so the HTTP
  connection is released.
- `src/lib/assistant/use-chat-runtime.ts` — `useChatRuntime(activeChatId)`.
  Wraps `useLocalRuntime(chatModelAdapter)`. Conversation history is kept
  server-side (LangGraph memory keyed by thread id) and there is no
  message-listing endpoint, so when the active chat changes the visible thread
  is reset via `runtime.thread.reset()`. A 0.14 gotcha handled here: the
  thread runtime throws on `reset()` until it finishes async initialization
  (we defer via `subscribe` + `isLoading`).
- `src/components/assistant-thread.tsx` — the UI: Thread viewport, composer,
  empty state, all i18n'd. Assistant messages render with
  `components={{ Text: MarkdownText, tools: { Fallback: ToolFallback } }}`.
- `src/components/assistant-ui/markdown-text.tsx` — GFM markdown
  (`@assistant-ui/react-markdown` + `remark-gfm`) with styled code blocks and
  a copy button.
- `src/components/assistant-ui/tool-fallback.tsx` — compact rendering for any
  tool call the app has no dedicated UI for.

## Mocking

With `VITE_ENABLE_MOCKS=true`, `src/mocks/chat-stream-handler.ts` fakes the
stream (include the word "tool" in your message to see the tool-call path).
Streamed messages are NOT persisted into the mock db — the wire `thread_id`
is assistant-ui's internal id with no mapping to a mock chat id.

## Swapping in a real backend

Set `VITE_API_BASE_URL`, serve the endpoints in `../backend/openapi.yaml`, and
emit the NDJSON events above from your `/chat/stream`. Nothing in the UI layer
changes. If your backend uses SSE or a different event shape, adapt
`chat-model-adapter.ts` (and the spec) — the parser only assumes
one-JSON-object-per-line.
