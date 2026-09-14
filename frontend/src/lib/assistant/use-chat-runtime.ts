import { useMemo } from 'react'
import { useLocalRuntime, type ThreadMessageLike } from '@assistant-ui/react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  listChatMessages,
  getListChatMessagesQueryKey,
} from '@/shared/api/generated/chats/chats'
import type { ChatMessage } from '@/shared/api/generated/models'
import { createChatModelAdapter } from './chat-model-adapter'

export function mapChatMessage(message: ChatMessage): ThreadMessageLike {
  if (
    message.role !== 'user' &&
    message.role !== 'assistant' &&
    message.role !== 'system'
  ) {
    throw new Error(`Unsupported message role: ${message.role}`)
  }
  return {
    id: message.id,
    role: message.role,
    createdAt: new Date(message.createdAt),
    // The API's parts schema is an open object; the wire contract is assistant-ui content.
    content:
      message.role === 'assistant' && message.parts.length
        ? (message.parts as unknown as ThreadMessageLike['content'])
        : [{ type: 'text', text: message.content }],
    metadata: { custom: { traceId: message.traceId } },
  }
}

export async function loadChatHistory(chatId: string, signal?: AbortSignal) {
  const messages: ThreadMessageLike[] = []
  let cursor: string | undefined
  do {
    const { data } = await listChatMessages(
      chatId,
      { limit: 200, cursor },
      { signal }
    )
    messages.push(...data.items.map(mapChatMessage))
    cursor = data.hasMore ? (data.nextCursor ?? undefined) : undefined
  } while (cursor)
  return messages
}

export function useChatHistory(chatId: string) {
  return useQuery({
    queryKey: [...getListChatMessagesQueryKey(chatId), 'all'],
    queryFn: ({ signal }) => loadChatHistory(chatId, signal),
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: 'always',
  })
}

export function useChatRuntime(
  chatId: string,
  initialMessages: ThreadMessageLike[] = []
) {
  const queryClient = useQueryClient()
  const adapter = useMemo(
    () =>
      createChatModelAdapter(chatId, () => {
        void queryClient.invalidateQueries({
          predicate: ({ queryKey }) =>
            typeof queryKey[0] === 'string' &&
            (/^\/projects\/[^/]+\/chats$/.test(queryKey[0]) ||
              queryKey[0] === '/chats/recent' ||
              queryKey[0] === '/chats/search'),
        })
        void queryClient.invalidateQueries({
          queryKey: getListChatMessagesQueryKey(chatId),
          refetchType: 'none',
        })
      }),
    [chatId, queryClient]
  )
  return useLocalRuntime(adapter, { initialMessages })
}
