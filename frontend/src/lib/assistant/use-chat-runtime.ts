import { useEffect, useRef } from 'react'
import { useLocalRuntime, type AssistantRuntime } from '@assistant-ui/react'
import { chatModelAdapter } from './chat-model-adapter'

/**
 * Creates an AssistantRuntime powered by the custom ChatModelAdapter.
 * The adapter is a module-level singleton so React sees a stable reference.
 *
 * Conversation history is kept server-side (LangGraph memory keyed by
 * thread id) and the backend exposes no message-listing endpoint, so
 * switching chats resets the visible thread instead of hydrating past
 * messages; the server continues the conversation from its own memory.
 */
export function useChatRuntime(activeChatId: string | null): AssistantRuntime {
  const runtime = useLocalRuntime(chatModelAdapter)

  const activeChatIdRef = useRef<string | null>(null)

  useEffect(() => {
    // Skip the initial mount (nothing to clear); only reset when the
    // selection actually changes.
    if (activeChatIdRef.current === activeChatId) return
    let apply: (() => void) | undefined = () => {
      activeChatIdRef.current = activeChatId
      runtime.thread.reset()
    }

    // The main thread initializes asynchronously; calling reset on the
    // placeholder throws. Defer until it is ready — the unsubscribe cleanup
    // acts as the cancelled flag if the selection changes meanwhile.
    if (!runtime.thread.getState().isLoading) {
      apply()
      return
    }
    const unsubscribe = runtime.thread.subscribe(() => {
      if (runtime.thread.getState().isLoading) return
      unsubscribe()
      apply?.()
      apply = undefined
    })
    return unsubscribe
  }, [activeChatId, runtime])

  return runtime
}
