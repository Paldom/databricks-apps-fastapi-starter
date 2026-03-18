import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AppProviders } from './app-provider'
import { lazy } from 'react'

describe('AppProviders', () => {
  it('renders children correctly', () => {
    render(
      <AppProviders>
        <div>Test content</div>
      </AppProviders>
    )
    expect(screen.getByText('Test content')).toBeInTheDocument()
  })

  it('shows the loading fallback while children suspend', () => {
    const LazyChild = lazy(() => new Promise<never>(() => undefined))

    render(
      <AppProviders>
        <LazyChild />
      </AppProviders>
    )

    expect(screen.getByText('Loading application...')).toBeInTheDocument()
  })
})
