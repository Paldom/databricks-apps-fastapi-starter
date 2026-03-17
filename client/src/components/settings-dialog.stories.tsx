import type { Meta, StoryObj } from '@storybook/react-vite'
import { useEffect } from 'react'
import { SettingsDialog } from '@/components/settings-dialog'
import { useUIStore } from '@/shared/store/ui'

function OpenSettingsDialog() {
  useEffect(() => {
    useUIStore.setState({ settingsDialogOpen: true })
    return () => {
      useUIStore.setState({ settingsDialogOpen: false })
    }
  }, [])
  return <SettingsDialog />
}

const meta = {
  title: 'App/SettingsDialog',
  component: SettingsDialog,
  tags: ['autodocs'],
} satisfies Meta<typeof SettingsDialog>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => <OpenSettingsDialog />,
}
