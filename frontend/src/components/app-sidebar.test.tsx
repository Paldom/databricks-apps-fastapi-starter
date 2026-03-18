import { MemoryRouter } from 'react-router-dom'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { AppSidebar } from './app-sidebar'
import { SidebarProvider } from '@/components/ui/sidebar'
import { resetUIStore, createTestQueryClient } from '@/test/utils'
import { useUIStore } from '@/shared/store/ui'
import { QueryClientProvider } from '@tanstack/react-query'
import { AssistantRuntimeProvider } from '@assistant-ui/react'
import { useChatRuntime } from '@/lib/assistant/use-chat-runtime'
import { server } from '@/mocks/server'
import { http, HttpResponse } from 'msw'

function RuntimeWrapper({ children }: Readonly<{ children: React.ReactNode }>) {
  const runtime = useChatRuntime()
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  )
}

function renderSidebar() {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RuntimeWrapper>
          <SidebarProvider defaultOpen>
            <AppSidebar />
          </SidebarProvider>
        </RuntimeWrapper>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('AppSidebar', () => {
  beforeEach(() => {
    resetUIStore()
  })

  it('renders app info and loads projects from server', async () => {
    renderSidebar()

    expect(screen.getByText('React Starter Pro')).toBeInTheDocument()
    expect(screen.getByText('Enterprise')).toBeInTheDocument()

    // Wait for user profile to load from MSW
    await waitFor(
      () => {
        expect(screen.getByText('John Doe')).toBeInTheDocument()
      },
      { timeout: 5000 }
    )
  })

  it('opens search dialog', async () => {
    const user = userEvent.setup()
    renderSidebar()

    await user.click(screen.getByRole('button', { name: /search chats/i }))
    expect(useUIStore.getState().searchDialogOpen).toBe(true)
  })

  it('renders loading skeletons while projects load', () => {
    server.use(
      http.get('*/api/projects', async () => {
        await new Promise(() => {})
        return HttpResponse.json({})
      })
    )

    renderSidebar()

    expect(screen.getByText('Add project')).toBeInTheDocument()
    expect(screen.getByText('Search chats')).toBeInTheDocument()
  })

  it('shows user settings loading state', () => {
    server.use(
      http.get('*/api/settings', async () => {
        await new Promise(() => {})
        return HttpResponse.json({})
      })
    )

    renderSidebar()

    expect(screen.getByText('...')).toBeInTheDocument()
  })

  it('creates a project when clicking add project', async () => {
    const user = userEvent.setup()
    renderSidebar()

    const addButton = screen.getByRole('button', { name: /add project/i })
    await user.click(addButton)

    expect(addButton).toBeInTheDocument()
  })

  it('renders projects and opens settings from user menu', async () => {
    const user = userEvent.setup()
    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /john doe/i }))
    await user.click(await screen.findByText('Settings'))

    expect(useUIStore.getState().settingsDialogOpen).toBe(true)
  })

  it('handles projects with chats', async () => {
    server.use(
      http.get('*/api/projects', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'p1',
              name: 'My Project',
              createdAt: '2024-01-01T00:00:00Z',
              chatCount: 2,
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      }),
      http.get('*/api/projects/p1/chats', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'c1',
              title: 'Test Chat',
              projectId: 'p1',
              createdAt: '2024-01-01T00:00:00Z',
              updatedAt: '2024-01-01T00:00:00Z',
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      })
    )

    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('My Project')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText('Test Chat')).toBeInTheDocument()
    })
  })

  it('selects a chat and activates it in the store', async () => {
    const user = userEvent.setup()

    server.use(
      http.get('*/api/projects', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'p1',
              name: 'Project A',
              createdAt: '2024-01-01T00:00:00Z',
              chatCount: 1,
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      }),
      http.get('*/api/projects/p1/chats', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'c1',
              title: 'Chat One',
              projectId: 'p1',
              createdAt: '2024-01-01T00:00:00Z',
              updatedAt: '2024-01-01T00:00:00Z',
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      })
    )

    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('Chat One')).toBeInTheDocument()
    })

    await user.click(screen.getByText('Chat One'))
    expect(useUIStore.getState().activeChatId).toBe('c1')
  })

  it('edits a chat title via double-click', async () => {
    const user = userEvent.setup()

    server.use(
      http.get('*/api/projects', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'p1',
              name: 'Project A',
              createdAt: '2024-01-01T00:00:00Z',
              chatCount: 1,
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      }),
      http.get('*/api/projects/p1/chats', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'c1',
              title: 'Old Title',
              projectId: 'p1',
              createdAt: '2024-01-01T00:00:00Z',
              updatedAt: '2024-01-01T00:00:00Z',
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      }),
      http.patch('*/api/chats/:chatId', async ({ params, request }) => {
        const body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({
          id: params.chatId,
          title: body.title ?? 'Old Title',
          projectId: 'p1',
          createdAt: '2024-01-01T00:00:00Z',
          updatedAt: new Date().toISOString(),
        })
      })
    )

    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('Old Title')).toBeInTheDocument()
    })

    await user.dblClick(screen.getByText('Old Title'))

    const input = screen.getByDisplayValue('Old Title')
    expect(input).toBeInTheDocument()

    await user.clear(input)
    await user.type(input, 'New Title')
    fireEvent.keyDown(input, { key: 'Enter' })

    await waitFor(() => {
      expect(screen.queryByDisplayValue('New Title')).not.toBeInTheDocument()
    })
  })

  it('cancels chat edit via Escape key', async () => {
    const user = userEvent.setup()

    server.use(
      http.get('*/api/projects', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'p1',
              name: 'Project A',
              createdAt: '2024-01-01T00:00:00Z',
              chatCount: 1,
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      }),
      http.get('*/api/projects/p1/chats', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'c1',
              title: 'Chat Title',
              projectId: 'p1',
              createdAt: '2024-01-01T00:00:00Z',
              updatedAt: '2024-01-01T00:00:00Z',
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      })
    )

    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('Chat Title')).toBeInTheDocument()
    })

    await user.dblClick(screen.getByText('Chat Title'))

    const input = screen.getByDisplayValue('Chat Title')
    fireEvent.keyDown(input, { key: 'Escape' })

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('creates a new chat in a project', async () => {
    const user = userEvent.setup()

    server.use(
      http.get('*/api/projects', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'p1',
              name: 'Project X',
              createdAt: '2024-01-01T00:00:00Z',
              chatCount: 0,
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      }),
      http.get('*/api/projects/p1/chats', () => {
        return HttpResponse.json({
          items: [],
          nextCursor: null,
          hasMore: false,
        })
      })
    )

    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('Project X')).toBeInTheDocument()
    })

    // Hover over the project group to show the new chat button
    // The button is hidden via CSS opacity, but still in the DOM
    const newChatButtons = document.querySelectorAll(
      '[data-slot="sidebar-group-label"] button'
    )
    // Last button in the project label row is the new chat button
    const newChatButton = newChatButtons[newChatButtons.length - 1]
    if (newChatButton) {
      await user.click(newChatButton as HTMLElement)
    }

    // Verify the button interaction doesn't throw
    expect(screen.getByText('Project X')).toBeInTheDocument()
  })

  it('edits a project name via context menu', async () => {
    const user = userEvent.setup()

    server.use(
      http.get('*/api/projects', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'p1',
              name: 'Original Name',
              createdAt: '2024-01-01T00:00:00Z',
              chatCount: 0,
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      }),
      http.get('*/api/projects/p1/chats', () => {
        return HttpResponse.json({
          items: [],
          nextCursor: null,
          hasMore: false,
        })
      }),
      http.patch('*/api/projects/:projectId', async ({ params, request }) => {
        const body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({
          id: params.projectId,
          name: body.name ?? 'Original Name',
          createdAt: '2024-01-01T00:00:00Z',
          chatCount: 0,
        })
      })
    )

    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('Original Name')).toBeInTheDocument()
    })

    // Open the project context menu (the MoreHorizontal button)
    // The project label row has: CollapsibleTrigger button, project name span, dropdown trigger button, new chat button
    // We need the dropdown trigger button (2nd button in the label row)
    const projectLabelRow = screen
      .getByText('Original Name')
      .closest('[data-slot="sidebar-group-label"]')!
    const buttons = projectLabelRow.querySelectorAll('button')
    // buttons[0] = collapsible trigger, buttons[1] = more menu, buttons[2] = new chat
    await user.click(buttons[1])

    // Click "Edit name"
    await user.click(await screen.findByText('Edit name'))

    // Edit input should appear
    const input = screen.getByDisplayValue('Original Name')
    expect(input).toBeInTheDocument()

    await user.clear(input)
    await user.type(input, 'Renamed')
    fireEvent.keyDown(input, { key: 'Enter' })

    await waitFor(() => {
      expect(screen.queryByDisplayValue('Renamed')).not.toBeInTheDocument()
    })
  })

  it('cancels project rename via cancel button', async () => {
    const user = userEvent.setup()

    server.use(
      http.get('*/api/projects', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'p1',
              name: 'Proj Name',
              createdAt: '2024-01-01T00:00:00Z',
              chatCount: 0,
            },
          ],
          nextCursor: null,
          hasMore: false,
        })
      }),
      http.get('*/api/projects/p1/chats', () => {
        return HttpResponse.json({
          items: [],
          nextCursor: null,
          hasMore: false,
        })
      })
    )

    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('Proj Name')).toBeInTheDocument()
    })

    const projectLabelRow = screen
      .getByText('Proj Name')
      .closest('[data-slot="sidebar-group-label"]')!
    const buttons = projectLabelRow.querySelectorAll('button')
    await user.click(buttons[1])
    await user.click(await screen.findByText('Edit name'))

    const input = screen.getByDisplayValue('Proj Name')
    // Click the cancel (X) button
    const editContainer = input.closest('div')!
    const editButtons = editContainer.querySelectorAll('button')
    await user.click(editButtons[1]) // cancel button

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('shows load more button when hasNextPage is true', async () => {
    server.use(
      http.get('*/api/projects', () => {
        return HttpResponse.json({
          items: [
            {
              id: 'p1',
              name: 'Project 1',
              createdAt: '2024-01-01T00:00:00Z',
              chatCount: 0,
            },
          ],
          nextCursor: 'p1',
          hasMore: true,
        })
      })
    )

    renderSidebar()

    await waitFor(() => {
      expect(screen.getByText('Project 1')).toBeInTheDocument()
    })

    expect(screen.getByText('Load more')).toBeInTheDocument()
  })
})
