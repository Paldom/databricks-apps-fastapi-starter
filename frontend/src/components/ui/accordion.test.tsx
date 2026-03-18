import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from './accordion'

describe('ui/accordion', () => {
  it('toggles content when the trigger is clicked', async () => {
    const user = userEvent.setup()

    render(
      <Accordion type="single" collapsible>
        <AccordionItem value="item-1">
          <AccordionTrigger>Section</AccordionTrigger>
          <AccordionContent>Hidden content</AccordionContent>
        </AccordionItem>
      </Accordion>
    )

    const trigger = screen.getByRole('button', { name: /section/i })
    expect(screen.queryByText('Hidden content')).not.toBeInTheDocument()
    expect(trigger.className).toContain('rounded-md')

    await user.click(trigger)

    expect(await screen.findByText('Hidden content')).toBeInTheDocument()

    const content = screen.getByText('Hidden content')
    expect(content.className).toContain('pb-4')
  })
})
