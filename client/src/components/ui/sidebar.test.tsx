import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarInset,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
} from './sidebar'

const originalInnerWidth = globalThis.innerWidth

afterEach(() => {
  globalThis.innerWidth = originalInnerWidth
})

describe('ui/sidebar', () => {
  it('renders desktop sidebar structure and menu utilities', async () => {
    const user = userEvent.setup()
    render(
      <SidebarProvider defaultOpen>
        <Sidebar collapsible="none">
          <SidebarHeader>
            <SidebarInput placeholder="Search" />
            <SidebarSeparator />
          </SidebarHeader>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel>Projects</SidebarGroupLabel>
              <SidebarGroupAction>+</SidebarGroupAction>
              <SidebarGroupContent>
                <SidebarMenu>
                  <SidebarMenuItem>
                    <SidebarMenuButton tooltip="Tooltip">
                      Inbox
                    </SidebarMenuButton>
                    <SidebarMenuAction showOnHover>Action</SidebarMenuAction>
                    <SidebarMenuBadge>3</SidebarMenuBadge>
                  </SidebarMenuItem>
                  <SidebarMenuItem>
                    <SidebarMenuButton isActive size="sm" variant="outline">
                      Active
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                  <SidebarMenuSkeleton showIcon />
                </SidebarMenu>
                <SidebarMenuSub>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton size="sm">Sub</SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                  <SidebarMenuSubItem>
                    <SidebarMenuSubButton size="md" isActive>
                      Sub Active
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                </SidebarMenuSub>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
          <SidebarFooter>
            <SidebarTrigger />
            <SidebarRail />
          </SidebarFooter>
        </Sidebar>
        <SidebarInset>Content</SidebarInset>
      </SidebarProvider>
    )

    expect(screen.getByPlaceholderText('Search')).toHaveAttribute(
      'data-slot',
      'sidebar-input'
    )
    expect(screen.getByText('Projects')).toHaveAttribute(
      'data-slot',
      'sidebar-group-label'
    )
    expect(screen.getByText('Inbox')).toHaveAttribute(
      'data-slot',
      'sidebar-menu-button'
    )

    const trigger = document.querySelector('[data-slot="sidebar-trigger"]')
    expect(trigger).toBeTruthy()
    await user.click(trigger as HTMLElement)
  })

  it('toggles sidebar with keyboard shortcut', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()

    render(
      <SidebarProvider open onOpenChange={onOpenChange}>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>
    )

    await user.keyboard('{Control>}b{/Control}')
    expect(onOpenChange).toHaveBeenCalled()
  })

  it('supports controlled open state via onOpenChange', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()

    render(
      <SidebarProvider open onOpenChange={onOpenChange}>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Item</SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
        <SidebarTrigger />
      </SidebarProvider>
    )

    await user.click(screen.getByRole('button', { name: /toggle sidebar/i }))
    expect(onOpenChange).toHaveBeenCalled()
  })

  it('renders the mobile sheet variant on small viewports', async () => {
    globalThis.innerWidth = 500
    const user = userEvent.setup()

    render(
      <SidebarProvider defaultOpen>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton>Mobile item</SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
        <SidebarTrigger />
      </SidebarProvider>
    )

    await user.click(screen.getByRole('button', { name: /toggle sidebar/i }))
    expect(await screen.findByText('Mobile item')).toBeInTheDocument()
  })
})
