import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'

/**
 * A vertically stacked set of interactive headings that each reveal a section
 * of content.
 */
const meta = {
  title: 'ui/Accordion',
  component: Accordion,
  tags: ['autodocs'],
  argTypes: {
    type: {
      control: 'radio',
      description: 'Type of accordion behavior',
      options: ['single', 'multiple'],
    },
    collapsible: {
      control: 'boolean',
      description: 'Can an open accordion be collapsed using the trigger',
      if: { arg: 'type', eq: 'single' },
    },
    disabled: {
      control: 'boolean',
    },
  },
  args: {
    type: 'single',
    collapsible: true,
    disabled: false,
  },
  render: (args) => (
    <Accordion {...args}>
      <AccordionItem value="item-1">
        <AccordionTrigger>Is it accessible?</AccordionTrigger>
        <AccordionContent>
          Yes. It adheres to the WAI-ARIA design pattern.
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="item-2">
        <AccordionTrigger>Is it styled?</AccordionTrigger>
        <AccordionContent>
          Yes. It comes with default styles that matches the other components'
          aesthetic.
        </AccordionContent>
      </AccordionItem>
      <AccordionItem value="item-3">
        <AccordionTrigger>Is it animated?</AccordionTrigger>
        <AccordionContent>
          Yes. It's animated by default, but you can disable it if you prefer.
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  ),
} satisfies Meta<typeof Accordion>

export default meta

type Story = StoryObj<typeof meta>

/**
 * The default behavior of the accordion allows only one item to be open.
 */
export const Default: Story = {}

export const ShouldOnlyOpenOneWhenSingleType: Story = {
  name: 'when accordions are clicked, should open only one item at a time',
  args: {
    type: 'single' as const,
  },
  tags: ['!dev', '!autodocs'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const accordions = canvas.getAllByRole('button')

    // Open the tabs one at a time
    for (const trigger of accordions) {
      await userEvent.click(trigger)
      await waitFor(() => expect(canvas.getAllByRole('region')).toHaveLength(1))
    }

    // Close the last opened tab
    await userEvent.click(accordions[accordions.length - 1])
    await waitFor(() => expect(canvas.queryByRole('region')).toBeNull())
  },
}

export const ShouldOpenAllWhenMultipleType: Story = {
  name: 'when accordions are clicked, should open all items one at a time',
  args: {
    type: 'multiple',
  },
  tags: ['!dev', '!autodocs'],
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const accordions = canvas.getAllByRole('button')

    // Open all tabs one at a time
    for (let i = 0; i < accordions.length; i++) {
      await userEvent.click(accordions[i])
      await waitFor(() =>
        expect(canvas.getAllByRole('region')).toHaveLength(i + 1)
      )
    }

    // Close all tabs one at a time
    for (let i = accordions.length - 1; i > 0; i--) {
      await userEvent.click(accordions[i])
      await waitFor(() => expect(canvas.getAllByRole('region')).toHaveLength(i))
    }

    // Close the last opened tab
    await userEvent.click(accordions[0])
    await waitFor(() => expect(canvas.queryByRole('region')).toBeNull())
  },
}
