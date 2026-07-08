import { describe, expect, it } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import {
  AssistantRuntimeProvider,
  type AssistantRuntime,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { createTestQueryClient } from '@/test/utils'
import { useChatRuntime } from './use-chat-runtime'

const seedMessages: ThreadMessageLike[] = [
  {
    id: 'msg-a1',
    role: 'user',
    content: [{ type: 'text', text: 'Question from chat A' }],
  },
  {
    id: 'msg-a2',
    role: 'assistant',
    content: [{ type: 'text', text: 'Answer from chat A' }],
  },
]

/**
 * Probe rendered inside AssistantRuntimeProvider: assistant-ui 0.14 only
 * initializes the main thread once the provider mounts the runtime's
 * internal render component, so a bare renderHook never becomes ready.
 */
function renderRuntime(initialChatId: string | null) {
  const queryClient = createTestQueryClient()
  const captured: { current: AssistantRuntime | null } = { current: null }

  function Probe({ chatId }: Readonly<{ chatId: string | null }>) {
    const runtime = useChatRuntime(chatId)
    captured.current = runtime
    return (
      <AssistantRuntimeProvider runtime={runtime}>
        {null}
      </AssistantRuntimeProvider>
    )
  }

  const view = render(
    <QueryClientProvider client={queryClient}>
      <Probe chatId={initialChatId} />
    </QueryClientProvider>
  )
  return {
    runtime: captured,
    setChatId: (chatId: string | null) => {
      view.rerender(
        <QueryClientProvider client={queryClient}>
          <Probe chatId={chatId} />
        </QueryClientProvider>
      )
    },
  }
}

async function seedThread(runtime: { current: AssistantRuntime | null }) {
  await waitFor(() => {
    expect(runtime.current?.thread.getState().isLoading).toBe(false)
  })
  runtime.current?.thread.reset(seedMessages)
  await waitFor(() => {
    expect(runtime.current?.thread.getState().messages).toHaveLength(2)
  })
}

describe('useChatRuntime', () => {
  it('returns a truthy runtime without an active chat', () => {
    const { runtime } = renderRuntime(null)
    expect(runtime.current).toBeTruthy()
    expect(runtime.current?.thread.getState().messages).toHaveLength(0)
  })

  it('starts with an empty thread for a selected chat', async () => {
    const { runtime } = renderRuntime('chat-a')
    await waitFor(() => {
      expect(runtime.current?.thread.getState().isLoading).toBe(false)
    })
    expect(runtime.current?.thread.getState().messages).toHaveLength(0)
  })

  it('resets the thread when switching to another chat', async () => {
    const { runtime, setChatId } = renderRuntime('chat-a')
    await seedThread(runtime)

    setChatId('chat-b')

    await waitFor(() => {
      expect(runtime.current?.thread.getState().messages).toHaveLength(0)
    })
  })

  it('clears the thread when the active chat is deselected', async () => {
    const { runtime, setChatId } = renderRuntime('chat-a')
    await seedThread(runtime)

    setChatId(null)

    await waitFor(() => {
      expect(runtime.current?.thread.getState().messages).toHaveLength(0)
    })
  })

  it('does not reset the thread when the selection is unchanged', async () => {
    const { runtime, setChatId } = renderRuntime('chat-a')
    await seedThread(runtime)

    setChatId('chat-a')

    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(runtime.current?.thread.getState().messages).toHaveLength(2)
  })
})
