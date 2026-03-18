import type { Meta, StoryObj } from '@storybook/react-vite'
import { AppSidebar } from '@/components/app-sidebar'
import { SidebarProvider } from '@/components/ui/sidebar'

const meta = {
  title: 'App/AppSidebar',
  component: AppSidebar,
  tags: ['autodocs'],
} satisfies Meta<typeof AppSidebar>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <SidebarProvider defaultOpen>
      <div className="h-[480px] w-[280px]">
        <AppSidebar />
      </div>
    </SidebarProvider>
  ),
}
