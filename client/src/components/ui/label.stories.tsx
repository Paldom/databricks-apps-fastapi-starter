import type { Meta, StoryObj } from '@storybook/react-vite'
import { Label } from '@/components/ui/label'

const meta = {
  title: 'UI/Label',
  component: Label,
  tags: ['autodocs'],
} satisfies Meta<typeof Label>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <div className="grid gap-2">
      <Label htmlFor="label-input">Email</Label>
      <input
        id="label-input"
        className="h-10 rounded-md border px-3 py-2 text-sm"
        placeholder="you@example.com"
      />
    </div>
  ),
}
