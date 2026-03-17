import type { Meta, StoryObj } from '@storybook/react-vite'
import { useEffect } from 'react'
import { ChatSearchDialog } from '@/components/chat-search-dialog'
import { useUIStore } from '@/shared/store/ui'

function OpenChatSearchDialog() {
  useEffect(() => {
    useUIStore.setState({ searchDialogOpen: true })
    return () => {
      useUIStore.setState({ searchDialogOpen: false })
    }
  }, [])
  return <ChatSearchDialog />
}

const meta = {
  title: 'App/ChatSearchDialog',
  component: ChatSearchDialog,
  tags: ['autodocs'],
} satisfies Meta<typeof ChatSearchDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => <OpenChatSearchDialog />,
}
