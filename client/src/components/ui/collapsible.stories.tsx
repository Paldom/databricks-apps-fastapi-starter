import type { Meta, StoryObj } from '@storybook/react-vite'
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from '@/components/ui/collapsible'

const meta = {
  title: 'UI/Collapsible',
  component: Collapsible,
  tags: ['autodocs'],
} satisfies Meta<typeof Collapsible>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  render: () => (
    <Collapsible defaultOpen>
      <CollapsibleTrigger className="text-sm font-medium">
        Details
      </CollapsibleTrigger>
      <CollapsibleContent className="text-sm text-muted-foreground">
        This is collapsible content.
      </CollapsibleContent>
    </Collapsible>
  ),
}
