import { useLocalRuntime } from '@assistant-ui/react'
import { chatModelAdapter } from './chat-model-adapter'

/**
 * Creates an AssistantRuntime powered by the custom ChatModelAdapter.
 * The adapter is a module-level singleton so React sees a stable reference.
 */
export function useChatRuntime() {
  return useLocalRuntime(chatModelAdapter)
}
