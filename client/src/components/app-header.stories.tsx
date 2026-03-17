import type { Meta, StoryObj } from '@storybook/react-vite'
import { AppHeader } from '@/components/app-header'
import { SidebarProvider } from '@/components/ui/sidebar'

const meta = {
  title: 'App/AppHeader',
  component: AppHeader,
  tags: ['autodocs'],
} satisfies Meta<typeof AppHeader>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <SidebarProvider defaultOpen>
      <div className="w-full">
        <AppHeader />
      </div>
    </SidebarProvider>
  ),
}
