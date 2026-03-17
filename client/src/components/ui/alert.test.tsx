import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Alert, AlertDescription, AlertTitle } from './alert'

describe('ui/alert', () => {
  it('renders title and description with alert role', () => {
    render(
      <Alert>
        <AlertTitle>Heads up</AlertTitle>
        <AlertDescription>Something happened</AlertDescription>
      </Alert>
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()
    const title = screen.getByText('Heads up')
    const description = screen.getByText('Something happened')
    expect(title).toHaveAttribute('data-slot', 'alert-title')
    expect(description).toHaveAttribute('data-slot', 'alert-description')
    expect(description.className).toContain('text-muted-foreground')
  })
})
