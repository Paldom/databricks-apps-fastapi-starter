import * as React from 'react'
import {
  Check,
  ChevronDown,
  ChevronUp,
  FolderPlus,
  Loader2,
  LogOut,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Search,
  Settings,
  SquarePen,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useTranslation } from '@/i18n/client'
import { useUIStore } from '@/shared/store/ui'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Link } from 'react-router-dom'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import {
  useListProjectsInfinite,
  useCreateProject,
  useUpdateProject,
  useDeleteProject,
  getListProjectsInfiniteQueryKey,
} from '@/shared/api/generated/projects/projects'
import {
  useListProjectChats,
  useCreateProjectChat,
  useUpdateChat,
  getListProjectChatsQueryKey,
} from '@/shared/api/generated/chats/chats'
import { useGetUserSettings } from '@/shared/api/generated/settings/settings'
import { useQueryClient } from '@tanstack/react-query'
import { useAui } from '@assistant-ui/react'

function getInitials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase() ?? '')
    .join('')
}

function ProjectChatList({ projectId }: Readonly<{ projectId: string }>) {
  const { activeChatId, setActiveChatId } = useUIStore()
  const queryClient = useQueryClient()
  const { data, isLoading } = useListProjectChats(projectId)

  const [editingChatId, setEditingChatId] = React.useState<string | null>(null)
  const [editingTitle, setEditingTitle] = React.useState('')

  const updateChatMutation = useUpdateChat({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getListProjectChatsQueryKey(projectId),
        })
      },
    },
  })

  const handleStartEdit = (chatId: string, currentTitle: string) => {
    setEditingChatId(chatId)
    setEditingTitle(currentTitle)
  }

  const handleSaveEdit = () => {
    if (editingChatId && editingTitle.trim()) {
      updateChatMutation.mutate({
        chatId: editingChatId,
        data: { title: editingTitle.trim() },
      })
    }
    setEditingChatId(null)
    setEditingTitle('')
  }

  const handleCancelEdit = () => {
    setEditingChatId(null)
    setEditingTitle('')
  }

  if (isLoading) {
    return (
      <SidebarMenu>
        {[1, 2].map((i) => (
          <SidebarMenuItem key={i}>
            <div className="px-2 py-1.5">
              <Skeleton className="h-5 w-full" />
            </div>
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    )
  }

  const chats = data?.data.items ?? []

  return (
    <SidebarMenu>
      {chats.map((chat) => (
        <SidebarMenuItem key={chat.id}>
          {editingChatId === chat.id ? (
            <div className="flex h-8 items-center gap-1 pl-8 pr-0">
              <Input
                value={editingTitle}
                onChange={(e) => setEditingTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveEdit()
                  if (e.key === 'Escape') handleCancelEdit()
                }}
                className="h-6 flex-1 text-xs"
                autoFocus
              />
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5 shrink-0"
                onClick={handleSaveEdit}
              >
                <Check className="h-3 w-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5 shrink-0"
                onClick={handleCancelEdit}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ) : (
            <SidebarMenuButton
              isActive={chat.id === activeChatId}
              onClick={() => setActiveChatId(chat.id)}
              onDoubleClick={() => handleStartEdit(chat.id, chat.title)}
            >
              <MessageSquare className="h-4 w-4" />
              <span className="truncate">{chat.title}</span>
            </SidebarMenuButton>
          )}
        </SidebarMenuItem>
      ))}
    </SidebarMenu>
  )
}

export function AppSidebar() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const aui = useAui()
  const {
    setActiveChatId,
    setActiveProjectId,
    setSearchDialogOpen,
    setSettingsDialogOpen,
  } = useUIStore()

  // Server state
  const projectsQuery = useListProjectsInfinite(undefined, {
    query: {
      initialPageParam: undefined,
      getNextPageParam: (lastPage) =>
        lastPage.data.hasMore ? lastPage.data.nextCursor : undefined,
    },
  })
  const settingsQuery = useGetUserSettings()

  const projects = React.useMemo(
    () => projectsQuery.data?.pages.flatMap((page) => page.data.items) ?? [],
    [projectsQuery.data?.pages]
  )

  // Auto-select first project/chat when data loads and nothing is selected
  const { activeProjectId } = useUIStore()
  React.useEffect(() => {
    if (projects.length > 0 && !activeProjectId) {
      setActiveProjectId(projects[0].id)
    }
  }, [projects, activeProjectId, setActiveProjectId])

  // Mutations with optimistic updates
  const createProjectMutation = useCreateProject({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getListProjectsInfiniteQueryKey(),
        })
      },
    },
  })

  const updateProjectMutation = useUpdateProject({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getListProjectsInfiniteQueryKey(),
        })
      },
    },
  })

  const deleteProjectMutation = useDeleteProject({
    mutation: {
      onSuccess: () => {
        void queryClient.invalidateQueries({
          queryKey: getListProjectsInfiniteQueryKey(),
        })
      },
    },
  })

  const createChatMutation = useCreateProjectChat({
    mutation: {
      onSuccess: (response, variables) => {
        void queryClient.invalidateQueries({
          queryKey: getListProjectChatsQueryKey(variables.projectId),
        })
        void queryClient.invalidateQueries({
          queryKey: getListProjectsInfiniteQueryKey(),
        })
        setActiveChatId(response.data.id)
        aui.threads().switchToNewThread()
      },
    },
  })

  // Edit state
  const [editingProjectId, setEditingProjectId] = React.useState<string | null>(
    null
  )
  const [editingName, setEditingName] = React.useState('')

  const handleStartEdit = (projectId: string, currentName: string) => {
    setEditingProjectId(projectId)
    setEditingName(currentName)
  }

  const handleSaveEdit = () => {
    if (editingProjectId && editingName.trim()) {
      updateProjectMutation.mutate({
        projectId: editingProjectId,
        data: { name: editingName.trim() },
      })
    }
    setEditingProjectId(null)
    setEditingName('')
  }

  const handleCancelEdit = () => {
    setEditingProjectId(null)
    setEditingName('')
  }

  const handleCreateProject = () => {
    createProjectMutation.mutate({ data: { name: 'New project' } })
  }

  const handleDeleteProject = (projectId: string) => {
    if (projects.length <= 1) return
    deleteProjectMutation.mutate({ projectId })
  }

  const userName = settingsQuery.data?.data.name ?? ''
  const userEmail = settingsQuery.data?.data.email ?? ''

  return (
    <Sidebar collapsible="offcanvas">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <Link to="/">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <img
                    src="/logo.svg"
                    alt={t('app.logoAlt')}
                    className="size-4 invert"
                  />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">
                    {t('app.name')}
                  </span>
                  <span className="truncate text-xs">{t('app.edition')}</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={handleCreateProject}
              disabled={createProjectMutation.isPending}
            >
              {createProjectMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FolderPlus />
              )}
              <span>{t('project.addProject')}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>

          <SidebarMenuItem>
            <SidebarMenuButton onClick={() => setSearchDialogOpen(true)}>
              <Search />
              <span>{t('chat.searchChats')}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {projectsQuery.isLoading && (
          <>
            {[1, 2, 3].map((i) => (
              <SidebarGroup key={i}>
                <SidebarGroupLabel>
                  <Skeleton className="h-4 w-24" />
                </SidebarGroupLabel>
              </SidebarGroup>
            ))}
          </>
        )}

        {projects.map((project) => (
          <Collapsible
            key={project.id}
            defaultOpen
            className="group/collapsible"
          >
            <SidebarGroup>
              {/* Project Header Row */}
              <SidebarGroupLabel className="h-8 pr-0">
                <div className="flex w-full items-center gap-1">
                  {/* Chevron trigger */}
                  <CollapsibleTrigger className="flex items-center">
                    <ChevronDown className="h-3 w-3 shrink-0 transition-transform group-data-[state=open]/collapsible:rotate-180" />
                  </CollapsibleTrigger>

                  {editingProjectId === project.id ? (
                    /* Edit mode */
                    <div className="flex flex-1 items-center gap-1">
                      <Input
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveEdit()
                          if (e.key === 'Escape') handleCancelEdit()
                        }}
                        className="h-6 flex-1 text-xs"
                        autoFocus
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5 shrink-0"
                        onClick={handleSaveEdit}
                      >
                        <Check className="h-3 w-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5 shrink-0"
                        onClick={handleCancelEdit}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    /* Normal mode */
                    <>
                      {/* Project name */}
                      <span className="flex-1 truncate">{project.name}</span>

                      {/* Context menu */}
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-5 w-5 shrink-0 opacity-0 group-hover/collapsible:opacity-100"
                          >
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="start">
                          <DropdownMenuItem
                            onClick={() =>
                              handleStartEdit(project.id, project.name)
                            }
                          >
                            <Pencil className="mr-2 h-4 w-4" />
                            {t('project.editName')}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => handleDeleteProject(project.id)}
                            disabled={projects.length <= 1}
                          >
                            <X className="mr-2 h-4 w-4" />
                            {t('project.remove')}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>

                      {/* Add new chat button */}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-5 w-5 shrink-0 opacity-0 group-hover/collapsible:opacity-100"
                        disabled={createChatMutation.isPending}
                        onClick={() => {
                          setActiveProjectId(project.id)
                          createChatMutation.mutate({
                            projectId: project.id,
                            data: { title: 'New chat' },
                          })
                        }}
                      >
                        <SquarePen className="h-4 w-4" />
                      </Button>
                    </>
                  )}
                </div>
              </SidebarGroupLabel>

              {/* Chat List */}
              <CollapsibleContent>
                <SidebarGroupContent>
                  <ProjectChatList projectId={project.id} />
                </SidebarGroupContent>
              </CollapsibleContent>
            </SidebarGroup>
          </Collapsible>
        ))}

        {projectsQuery.hasNextPage && (
          <SidebarGroup>
            <Button
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={() => void projectsQuery.fetchNextPage()}
              disabled={projectsQuery.isFetchingNextPage}
            >
              {projectsQuery.isFetchingNextPage
                ? t('common.loading')
                : t('common.loadMore')}
            </Button>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton>
                  <Avatar className="h-6 w-6">
                    <AvatarFallback>
                      {settingsQuery.isLoading ? '...' : getInitials(userName)}
                    </AvatarFallback>
                  </Avatar>

                  {settingsQuery.isLoading ? (
                    <span className="flex min-w-0 flex-col gap-1">
                      <Skeleton className="h-3.5 w-20" />
                      <Skeleton className="h-3 w-28" />
                    </span>
                  ) : (
                    <span className="flex min-w-0 flex-col text-left leading-tight">
                      <span className="truncate text-sm font-medium">
                        {userName}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {userEmail}
                      </span>
                    </span>
                  )}

                  <ChevronUp className="ml-auto" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>

              <DropdownMenuContent
                side="top"
                align="start"
                className="w-[--radix-popper-anchor-width]"
              >
                <DropdownMenuItem onClick={() => setSettingsDialogOpen(true)}>
                  <Settings className="mr-2 h-4 w-4" />
                  {t('user.settings')}
                </DropdownMenuItem>

                <DropdownMenuSeparator />

                <DropdownMenuItem>
                  <LogOut className="mr-2 h-4 w-4" />
                  {t('user.logOut')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  )
}
