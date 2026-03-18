import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Tooltip, TooltipContent, TooltipTrigger } from './tooltip'

describe('ui/tooltip', () => {
  it('renders tooltip content when open', () => {
    render(
      <Tooltip open>
        <TooltipTrigger>Trigger</TooltipTrigger>
        <TooltipContent sideOffset={8}>Tooltip text</TooltipContent>
      </Tooltip>
    )

    const tooltipContent = document.querySelector(
      '[data-slot="tooltip-content"]'
    )
    expect(tooltipContent).toBeTruthy()
    expect(tooltipContent).toHaveTextContent('Tooltip text')
  })
})
