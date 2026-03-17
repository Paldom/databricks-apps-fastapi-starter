import type { Meta, StoryObj } from '@storybook/react-vite'
import { LanguageSwitcher } from '@/components/language-switcher'

const meta = {
  title: 'Components/LanguageSwitcher',
  component: LanguageSwitcher,
  tags: ['autodocs'],
} satisfies Meta<typeof LanguageSwitcher>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => <LanguageSwitcher />,
}
