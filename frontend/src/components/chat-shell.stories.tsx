import type { Meta, StoryObj } from '@storybook/react-vite'
import { ChatShell } from '@/components/chat-shell'

const meta = {
  title: 'App/ChatShell',
  component: ChatShell,
  tags: ['autodocs'],
} satisfies Meta<typeof ChatShell>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => <ChatShell />,
}
