import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from '@/i18n/client'
import { Button } from './ui/button'
import {
  createProject,
  getListProjectsInfiniteQueryKey,
} from '@/shared/api/generated/projects/projects'
import {
  createProjectChat,
  getListProjectChatsQueryKey,
} from '@/shared/api/generated/chats/chats'
import {
  AssistantRuntimeProvider,
  type ThreadMessageLike,
} from '@assistant-ui/react'
import { useUIStore } from '@/shared/store/ui'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable'
import { AppHeader } from './app-header'
import { AppSidebar } from './app-sidebar'
import { ChatSearchDialog } from './chat-search-dialog'
import { SettingsDialog } from './settings-dialog'
import { DocumentSidebar } from './document-sidebar'
import { AssistantThread } from './assistant-thread'
import {
  useChatRuntime,
  useChatHistory,
} from '@/lib/assistant/use-chat-runtime'

export function ChatShell() {
  const { documentSidebarOpen, activeChatId } = useUIStore()
  const [firstTurn, setFirstTurn] = useState<{
    chatId: string
    text: string
  } | null>(null)

  return (
    <SidebarProvider defaultOpen>
      <AppSidebar />
      <SidebarInset className="flex flex-col overflow-hidden">
        <AppHeader />
        <ResizablePanelGroup orientation="horizontal" className="flex-1">
          <ResizablePanel
            defaultSize="70%"
            minSize={documentSidebarOpen ? '30%' : '100%'}
            className="min-w-0"
          >
            {activeChatId ? (
              <PersistedThread
                key={activeChatId}
                chatId={activeChatId}
                firstMessage={
                  firstTurn?.chatId === activeChatId
                    ? firstTurn.text
                    : undefined
                }
                onFirstMessageSent={() => setFirstTurn(null)}
              />
            ) : (
              <NewConversation
                onCreated={(chatId, text) => setFirstTurn({ chatId, text })}
              />
            )}
          </ResizablePanel>
          {documentSidebarOpen && (
            <>
              <ResizableHandle withHandle />
              <ResizablePanel defaultSize="30%" minSize="20%" maxSize="60%">
                <DocumentSidebar />
              </ResizablePanel>
            </>
          )}
        </ResizablePanelGroup>
      </SidebarInset>
      <ChatSearchDialog />
      <SettingsDialog />
    </SidebarProvider>
  )
}

function PersistedThread({
  chatId,
  firstMessage,
  onFirstMessageSent,
}: Readonly<{
  chatId: string
  firstMessage?: string
  onFirstMessageSent: () => void
}>) {
  const { t } = useTranslation()
  const history = useChatHistory(chatId)
  const { refetch: retryHistory } = history
  if (history.isPending || history.isFetching)
    return <output className="block p-4">{t('common.loading')}</output>
  if (history.isError)
    return (
      <div role="alert" className="p-4">
        <p>{t('chat.historyError')}</p>
        <Button onClick={() => void retryHistory()}>{t('common.retry')}</Button>
      </div>
    )
  return (
    <LoadedThread
      key={chatId}
      chatId={chatId}
      initialMessages={history.data}
      firstMessage={firstMessage}
      onFirstMessageSent={onFirstMessageSent}
    />
  )
}

function LoadedThread({
  chatId,
  initialMessages,
  firstMessage,
  onFirstMessageSent,
}: Readonly<{
  chatId: string
  initialMessages: ThreadMessageLike[]
  firstMessage?: string
  onFirstMessageSent: () => void
}>) {
  const runtime = useChatRuntime(chatId, initialMessages)
  const sent = useRef(false)
  useEffect(() => {
    if (!firstMessage || sent.current) return
    sent.current = true
    runtime.thread.append(firstMessage)
    onFirstMessageSent()
  }, [runtime, firstMessage, onFirstMessageSent])
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AssistantThread className="h-full" />
    </AssistantRuntimeProvider>
  )
}

function NewConversation({
  onCreated,
}: Readonly<{ onCreated: (chatId: string, text: string) => void }>) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const queryClient = useQueryClient()
  const creation = useMutation({
    mutationFn: async (message: string) => {
      let projectId = useUIStore.getState().activeProjectId
      if (!projectId) {
        const project = await createProject({ name: t('project.myChats') })
        projectId = project.data.id
        useUIStore.getState().setActiveProjectId(projectId)
      }
      const chat = await createProjectChat(projectId, { title: '' })
      void queryClient.invalidateQueries({
        queryKey: getListProjectsInfiniteQueryKey(),
      })
      void queryClient.invalidateQueries({
        queryKey: getListProjectChatsQueryKey(projectId),
      })
      onCreated(chat.data.id, message)
      useUIStore.getState().setActiveChatId(chat.data.id)
    },
  })
  return (
    <div className="flex h-full flex-col">
      <p className="flex flex-1 items-center justify-center p-4 text-sm text-muted-foreground">
        {t('chat.startConversation')}
      </p>
      {creation.isError && (
        <p role="alert" className="px-4 text-destructive">
          {t('chat.createError')}
        </p>
      )}
      <form
        className="flex items-end gap-2 border-t p-4"
        onSubmit={(event) => {
          event.preventDefault()
          if (text.trim() && !creation.isPending) creation.mutate(text)
        }}
      >
        <textarea
          aria-label={t('chat.message')}
          placeholder={t('chat.placeholder')}
          className="flex-1 resize-none rounded-lg border bg-transparent px-4 py-2 text-sm focus-visible:ring-2 focus-visible:ring-ring"
          value={text}
          disabled={creation.isPending}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (
              event.key === 'Enter' &&
              !event.shiftKey &&
              !event.nativeEvent.isComposing
            ) {
              event.preventDefault()
              event.currentTarget.form?.requestSubmit()
            }
          }}
        />
        <Button type="submit" disabled={creation.isPending || !text.trim()}>
          {t(creation.isPending ? 'common.loading' : 'chat.send')}
        </Button>
      </form>
    </div>
  )
}
