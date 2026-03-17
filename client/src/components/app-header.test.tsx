import { MemoryRouter } from 'react-router-dom'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppHeader } from './app-header'
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

function renderHeader() {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <RuntimeWrapper>
          <SidebarProvider defaultOpen>
            <AppHeader />
          </SidebarProvider>
        </RuntimeWrapper>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

function setupProjectAndChat() {
  server.use(
    http.get('*/api/projects', () => {
      return HttpResponse.json({
        items: [
          {
            id: 'proj-1',
            name: 'My Project',
            createdAt: '2024-01-01T00:00:00Z',
            chatCount: 1,
          },
        ],
        nextCursor: null,
        hasMore: false,
      })
    }),
    http.get('*/api/projects/proj-1/chats', () => {
      return HttpResponse.json({
        items: [
          {
            id: 'chat-1',
            title: 'Test Chat',
            projectId: 'proj-1',
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
        title: body.title ?? 'Test Chat',
        projectId: 'proj-1',
        createdAt: '2024-01-01T00:00:00Z',
        updatedAt: new Date().toISOString(),
      })
    }),
    http.post('*/api/projects/proj-1/chats', () => {
      return HttpResponse.json(
        {
          id: 'chat-2',
          title: 'Test Chat (copy)',
          projectId: 'proj-1',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        },
        { status: 201 }
      )
    }),
    http.delete('*/api/chats/:chatId', () => {
      return new HttpResponse(null, { status: 204 })
    })
  )
  resetUIStore({ activeProjectId: 'proj-1', activeChatId: 'chat-1' })
}

describe('AppHeader', () => {
  beforeEach(() => {
    resetUIStore()
  })

  it('shows the app title when no active chat is selected', () => {
    resetUIStore({ activeChatId: null })
    renderHeader()

    expect(screen.getByText('Chat App')).toBeInTheDocument()
  })

  it('toggles the document sidebar from the add document button', async () => {
    const user = userEvent.setup()
    renderHeader()

    const button = screen.getByRole('button', { name: /add document/i })
    expect(useUIStore.getState().documentSidebarOpen).toBe(false)

    await user.click(button)

    expect(useUIStore.getState().documentSidebarOpen).toBe(true)
  })

  it('shows breadcrumb with project name and chat title', async () => {
    setupProjectAndChat()
    renderHeader()

    await waitFor(() => {
      expect(screen.getByText('My Project')).toBeInTheDocument()
    })
    expect(screen.getByText('Test Chat')).toBeInTheDocument()
  })

  it('starts and cancels rename via dropdown menu', async () => {
    setupProjectAndChat()
    const user = userEvent.setup()
    renderHeader()

    await waitFor(() => {
      expect(screen.getByText('Test Chat')).toBeInTheDocument()
    })

    // Open dropdown menu
    await user.click(screen.getByRole('button', { name: /open menu/i }))
    await user.click(await screen.findByText('Rename'))

    // Rename input should appear with current title
    const input = screen.getByDisplayValue('Test Chat')
    expect(input).toBeInTheDocument()

    // Cancel via Escape key on the input
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(screen.queryByDisplayValue('Test Chat')).not.toBeInTheDocument()
    expect(screen.getByText('Test Chat')).toBeInTheDocument()
  })

  it('saves rename via Enter key', async () => {
    setupProjectAndChat()
    const user = userEvent.setup()
    renderHeader()

    await waitFor(() => {
      expect(screen.getByText('Test Chat')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /open menu/i }))
    await user.click(await screen.findByText('Rename'))

    const input = screen.getByDisplayValue('Test Chat')
    await user.clear(input)
    await user.type(input, 'Renamed Chat')
    fireEvent.keyDown(input, { key: 'Enter' })

    // Should exit rename mode after mutation completes
    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    })
  })

  it('saves rename via check button', async () => {
    setupProjectAndChat()
    const user = userEvent.setup()
    renderHeader()

    await waitFor(() => {
      expect(screen.getByText('Test Chat')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /open menu/i }))
    await user.click(await screen.findByText('Rename'))

    // Click the save (check) button - it's the first icon button inside the rename form
    const input = screen.getByDisplayValue('Test Chat')
    await user.clear(input)
    await user.type(input, 'New Name')

    // Find the check/save button (first small icon button after input)
    const renameForm = input.closest('div')!
    const buttons = renameForm.querySelectorAll('button')
    await user.click(buttons[0]) // save button

    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    })
  })

  it('cancels rename via X button', async () => {
    setupProjectAndChat()
    const user = userEvent.setup()
    renderHeader()

    await waitFor(() => {
      expect(screen.getByText('Test Chat')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /open menu/i }))
    await user.click(await screen.findByText('Rename'))

    const input = screen.getByDisplayValue('Test Chat')
    const renameForm = input.closest('div')!
    const buttons = renameForm.querySelectorAll('button')
    await user.click(buttons[1]) // cancel button

    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('dismisses rename if value is empty', async () => {
    setupProjectAndChat()
    const user = userEvent.setup()
    renderHeader()

    await waitFor(() => {
      expect(screen.getByText('Test Chat')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /open menu/i }))
    await user.click(await screen.findByText('Rename'))

    const input = screen.getByDisplayValue('Test Chat')
    await user.clear(input)
    fireEvent.keyDown(input, { key: 'Enter' })

    // Should exit rename mode without saving
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('duplicates a chat from dropdown menu', async () => {
    setupProjectAndChat()
    const user = userEvent.setup()
    renderHeader()

    await waitFor(() => {
      expect(screen.getByText('Test Chat')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /open menu/i }))
    await user.click(await screen.findByText('Duplicate'))

    // Mutation fires; just verify it doesn't throw
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /open menu/i })).toBeEnabled()
    })
  })

  it('deletes a chat from dropdown menu with confirmation', async () => {
    setupProjectAndChat()
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(globalThis, 'confirm').mockReturnValue(true)
    renderHeader()

    await waitFor(() => {
      expect(screen.getByText('Test Chat')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /open menu/i }))
    await user.click(await screen.findByText('Delete'))

    expect(confirmSpy).toHaveBeenCalled()
    confirmSpy.mockRestore()
  })

  it('does not delete when user cancels confirmation', async () => {
    setupProjectAndChat()
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(globalThis, 'confirm').mockReturnValue(false)
    renderHeader()

    await waitFor(() => {
      expect(screen.getByText('Test Chat')).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /open menu/i }))
    await user.click(await screen.findByText('Delete'))

    expect(confirmSpy).toHaveBeenCalled()
    // Chat should still be visible
    expect(screen.getByText('Test Chat')).toBeInTheDocument()
    confirmSpy.mockRestore()
  })
})
