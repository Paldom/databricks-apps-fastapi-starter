import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Skeleton } from './skeleton'

describe('ui/skeleton', () => {
  it('renders skeleton element', () => {
    render(<Skeleton data-testid="skeleton" />)
    expect(screen.getByTestId('skeleton')).toHaveAttribute(
      'data-slot',
      'skeleton'
    )
  })
})
