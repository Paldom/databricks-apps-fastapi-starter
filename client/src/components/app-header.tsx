import { Check, FilePlus2, MoreHorizontal, Share2, X } from 'lucide-react'
import { useTranslation } from '@/i18n/client'
import { useUIStore } from '@/shared/store/ui'
import { LanguageSwitcher } from '@/components/language-switcher'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'
import {
  useListProjectsInfinite,
  getListProjectsInfiniteQueryKey,
} from '@/shared/api/generated/projects/projects'
import {
  useListProjectChats,
  useUpdateChat,
  useCreateProjectChat,
  useDeleteChat,
  getListProjectChatsQueryKey,
} from '@/shared/api/generated/chats/chats'
import { useQueryClient } from '@tanstack/react-query'
import { useAui } from '@assistant-ui/react'
import * as React from 'react'

export function AppHeader() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const aui = useAui()
  const {
    activeProjectId,
    activeChatId,
    setActiveChatId,
    toggleDocumentSidebar,
    documentSidebarOpen,
  } = useUIStore()

  const [isRenaming, setIsRenaming] = React.useState(false)
  const [renameValue, setRenameValue] = React.useState('')

  // Get projects to find the active project name
  const projectsQuery = useListProjectsInfinite(undefined, {
    query: {
      initialPageParam: undefined,
      getNextPageParam: (lastPage) =>
        lastPage.data.hasMore ? lastPage.data.nextCursor : undefined,
    },
  })

  const projects = React.useMemo(
    () => projectsQuery.data?.pages.flatMap((page) => page.data.items) ?? [],
    [projectsQuery.data?.pages]
  )

  const activeProject = projects.find((p) => p.id === activeProjectId)

  // Get chats for the active project to find the active chat title
  const chatsQuery = useListProjectChats(activeProjectId ?? '', undefined, {
    query: { enabled: !!activeProjectId },
  })
  const chats = chatsQuery.data?.data.items ?? []
  const activeChat = chats.find((c) => c.id === activeChatId)

  const updateChatMutation = useUpdateChat({
    mutation: {
      onSuccess: () => {
        setIsRenaming(false)
        if (activeProjectId) {
          void queryClient.invalidateQueries({
            queryKey: getListProjectChatsQueryKey(activeProjectId),
          })
        }
      },
    },
  })

  const createChatMutation = useCreateProjectChat({
    mutation: {
      onSuccess: (response) => {
        setActiveChatId(response.data.id)
        aui.threads().switchToNewThread()
        if (activeProjectId) {
          void queryClient.invalidateQueries({
            queryKey: getListProjectChatsQueryKey(activeProjectId),
          })
          void queryClient.invalidateQueries({
            queryKey: getListProjectsInfiniteQueryKey(),
          })
        }
      },
    },
  })

  const deleteChatMutation = useDeleteChat({
    mutation: {
      onSuccess: () => {
        setActiveChatId(null)
        aui.threads().switchToNewThread()
        if (activeProjectId) {
          void queryClient.invalidateQueries({
            queryKey: getListProjectChatsQueryKey(activeProjectId),
          })
          void queryClient.invalidateQueries({
            queryKey: getListProjectsInfiniteQueryKey(),
          })
        }
      },
    },
  })

  const handleStartRename = () => {
    if (!activeChat) return
    setRenameValue(activeChat.title)
    setIsRenaming(true)
  }

  const handleSaveRename = () => {
    if (!activeChatId || !renameValue.trim()) {
      setIsRenaming(false)
      return
    }
    updateChatMutation.mutate({
      chatId: activeChatId,
      data: { title: renameValue.trim() },
    })
  }

  const handleCancelRename = () => {
    setIsRenaming(false)
    setRenameValue('')
  }

  const handleDuplicate = () => {
    if (!activeChat || !activeProjectId) return
    createChatMutation.mutate({
      projectId: activeProjectId,
      data: { title: `${activeChat.title} (copy)` },
    })
  }

  const handleDelete = () => {
    if (!activeChat || !activeChatId) return
    if (globalThis.confirm(t('chat.confirmDelete'))) {
      deleteChatMutation.mutate({ chatId: activeChatId })
    }
  }

  return (
    <header className="flex h-14 items-center justify-between border-b px-4">
      <div className="flex items-center gap-2">
        <SidebarTrigger />
        <Separator orientation="vertical" className="h-6" />
        <Breadcrumb>
          <BreadcrumbList>
            {activeProject && activeChat ? (
              <>
                <BreadcrumbItem>{activeProject.name}</BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  {isRenaming ? (
                    <div className="flex items-center gap-1">
                      <Input
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveRename()
                          if (e.key === 'Escape') handleCancelRename()
                        }}
                        className="h-6 w-48 text-sm"
                        autoFocus
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5 shrink-0"
                        onClick={handleSaveRename}
                      >
                        <Check className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5 shrink-0"
                        onClick={handleCancelRename}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    <BreadcrumbPage className="max-w-[28ch] truncate">
                      {activeChat.title}
                    </BreadcrumbPage>
                  )}
                </BreadcrumbItem>
              </>
            ) : (
              <BreadcrumbItem>
                <BreadcrumbPage>{t('app.title')}</BreadcrumbPage>
              </BreadcrumbItem>
            )}
          </BreadcrumbList>
        </Breadcrumb>
      </div>

      <div className="flex items-center gap-2">
        <LanguageSwitcher />

        <Button
          variant={documentSidebarOpen ? 'secondary' : 'outline'}
          size="sm"
          onClick={toggleDocumentSidebar}
        >
          <FilePlus2 className="mr-2 h-4 w-4" />
          {t('document.addDocument')}
        </Button>

        <Button variant="outline" size="sm">
          <Share2 className="mr-2 h-4 w-4" />
          {t('chat.share')}
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon">
              <MoreHorizontal className="h-4 w-4" />
              <span className="sr-only">{t('common.openMenu')}</span>
            </Button>
          </DropdownMenuTrigger>

          <DropdownMenuContent align="end">
            <DropdownMenuItem
              disabled={!activeChat}
              onClick={handleStartRename}
            >
              {t('chat.rename')}
            </DropdownMenuItem>
            <DropdownMenuItem
              disabled={!activeChat || createChatMutation.isPending}
              onClick={handleDuplicate}
            >
              {t('chat.duplicate')}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-destructive"
              disabled={!activeChat || deleteChatMutation.isPending}
              onClick={handleDelete}
            >
              {t('chat.delete')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
