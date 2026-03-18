import * as React from 'react'
import { Loader2, MessageSquare } from 'lucide-react'
import { useTranslation } from '@/i18n/client'
import { useUIStore } from '@/shared/store/ui'
import { useDebouncedValue } from '@/hooks/use-debounced-value'
import {
  useSearchChatsInfinite,
  useGetRecentChats,
} from '@/shared/api/generated/chats/chats'
import type { ChatSearchResult } from '@/shared/api/generated/models'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'

function groupByProject(
  items: ChatSearchResult[]
): Map<string, ChatSearchResult[]> {
  const groups = new Map<string, ChatSearchResult[]>()
  for (const item of items) {
    const key = item.projectName
    const group = groups.get(key) ?? []
    group.push(item)
    groups.set(key, group)
  }
  return groups
}

export function ChatSearchDialog() {
  const { t } = useTranslation()
  const {
    searchDialogOpen,
    setSearchDialogOpen,
    setActiveChatId,
    setActiveProjectId,
  } = useUIStore()

  const [searchTerm, setSearchTerm] = React.useState('')
  const debouncedTerm = useDebouncedValue(searchTerm, 300)
  const hasQuery = debouncedTerm.trim().length > 0

  // Recent chats — shown when no search term
  const recentChatsQuery = useGetRecentChats(
    { limit: 10 },
    { query: { enabled: searchDialogOpen && !hasQuery } }
  )

  // Search query — enabled only when there is a debounced term
  const searchQuery = useSearchChatsInfinite(
    { q: debouncedTerm, limit: 20 },
    {
      query: {
        enabled: searchDialogOpen && hasQuery,
        initialPageParam: undefined,
        getNextPageParam: (lastPage) =>
          lastPage.data.hasMore ? lastPage.data.nextCursor : undefined,
      },
    }
  )

  // Reset search term when dialog closes
  React.useEffect(() => {
    if (!searchDialogOpen) {
      setSearchTerm('')
    }
  }, [searchDialogOpen])

  // Keyboard shortcut: Ctrl/Cmd + K
  React.useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setSearchDialogOpen(!searchDialogOpen)
      }
    }
    document.addEventListener('keydown', down)
    return () => document.removeEventListener('keydown', down)
  }, [searchDialogOpen, setSearchDialogOpen])

  const handleSelectChat = (chatId: string, projectId: string) => {
    setActiveChatId(chatId)
    setActiveProjectId(projectId)
    setSearchDialogOpen(false)
  }

  const handleLoadMore = () => {
    if (searchQuery.hasNextPage && !searchQuery.isFetchingNextPage) {
      void searchQuery.fetchNextPage()
    }
  }

  // Flatten search results across pages
  const searchResults = React.useMemo(() => {
    if (!searchQuery.data?.pages) return []
    return searchQuery.data.pages.flatMap((page) => page.data.items)
  }, [searchQuery.data?.pages])

  const recentResults = recentChatsQuery.data?.data.items ?? []

  const groupedResults = React.useMemo(
    () =>
      searchResults.length > 0
        ? Array.from(groupByProject(searchResults).entries())
        : [],
    [searchResults]
  )

  const isLoading = hasQuery
    ? searchQuery.isLoading
    : recentChatsQuery.isLoading

  return (
    <CommandDialog
      open={searchDialogOpen}
      onOpenChange={setSearchDialogOpen}
      shouldFilter={false}
    >
      <CommandInput
        placeholder={t('chat.searchPlaceholder')}
        value={searchTerm}
        onValueChange={setSearchTerm}
      />
      <CommandList>
        {isLoading && (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {!isLoading && hasQuery && searchResults.length === 0 && (
          <CommandEmpty>{t('chat.noResults')}</CommandEmpty>
        )}

        {!isLoading &&
          hasQuery &&
          groupedResults.map(([projectName, chats]) => (
            <CommandGroup key={projectName} heading={projectName}>
              {chats.map((chat) => (
                <CommandItem
                  key={chat.id}
                  value={chat.id}
                  onSelect={() => handleSelectChat(chat.id, chat.projectId)}
                >
                  <MessageSquare className="mr-2 h-4 w-4" />
                  <span className="truncate">{chat.title}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          ))}

        {!isLoading && hasQuery && searchQuery.hasNextPage && (
          <CommandItem
            onSelect={handleLoadMore}
            className="justify-center text-muted-foreground"
          >
            {searchQuery.isFetchingNextPage ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : null}
            {t('common.loadMore')}
          </CommandItem>
        )}

        {!isLoading && !hasQuery && recentResults.length > 0 && (
          <CommandGroup heading={t('chat.recentChats')}>
            {recentResults.map((chat) => (
              <CommandItem
                key={chat.id}
                value={chat.id}
                onSelect={() => handleSelectChat(chat.id, chat.projectId)}
              >
                <MessageSquare className="mr-2 h-4 w-4" />
                <span className="truncate">{chat.title}</span>
                <span className="ml-auto text-xs text-muted-foreground">
                  {chat.projectName}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}

        {!isLoading && !hasQuery && recentResults.length === 0 && (
          <CommandEmpty>{t('chat.noResults')}</CommandEmpty>
        )}

        {searchQuery.isError && (
          <div className="py-4 text-center text-sm text-destructive">
            {t('common.error')}
          </div>
        )}
      </CommandList>
    </CommandDialog>
  )
}
