import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Button, buttonVariants } from './button'

describe('ui/button', () => {
  it('renders a clickable button with default variant and size', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()

    render(<Button onClick={onClick}>Click me</Button>)

    const button = screen.getByRole('button', { name: /click me/i })
    expect(button).toHaveAttribute('data-variant', 'default')
    expect(button).toHaveAttribute('data-size', 'default')

    await user.click(button)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('supports rendering as a child element', () => {
    render(
      <Button asChild>
        <a href="/docs">Docs</a>
      </Button>
    )

    const link = screen.getByRole('link', { name: /docs/i })
    expect(link).toHaveAttribute('href', '/docs')
  })

  it('merges custom class names through buttonVariants', () => {
    const className = buttonVariants({
      variant: 'secondary',
      size: 'lg',
      className: 'extra-class',
    })
    expect(className).toContain('extra-class')
    expect(className).toContain('bg-secondary')
    expect(className).toContain('h-10')
  })

  it('applies variant, size and custom class on the rendered element', () => {
    render(
      <Button variant="secondary" size="lg" className="custom-class">
        Styled
      </Button>
    )

    const button = screen.getByRole('button', { name: /styled/i })
    const className = button.className
    expect(className).toContain('custom-class')
    expect(className).toContain('bg-secondary')
    expect(className).toContain('h-10')
  })
})
