import { useEffect } from 'react'
import { describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { type QueryClient, useQueryClient } from '@tanstack/react-query'
import { QueryClientProviderWithClient } from './query-client-provider'

function CaptureClient({ onClient }: { onClient: (c: QueryClient) => void }) {
  const client = useQueryClient()
  useEffect(() => {
    onClient(client)
  }, [client, onClient])
  return null
}

describe('QueryClientProviderWithClient', () => {
  it('renders children correctly', () => {
    render(
      <QueryClientProviderWithClient>
        <div>Test content</div>
      </QueryClientProviderWithClient>
    )
    expect(screen.getByText('Test content')).toBeInTheDocument()
  })

  it('provides a stable, preconfigured QueryClient instance', async () => {
    const seen: QueryClient[] = []

    const { rerender } = render(
      <QueryClientProviderWithClient>
        <CaptureClient onClient={(c) => seen.push(c)} />
      </QueryClientProviderWithClient>
    )

    rerender(
      <QueryClientProviderWithClient>
        <CaptureClient onClient={(c) => seen.push(c)} />
      </QueryClientProviderWithClient>
    )

    await waitFor(() => {
      expect(seen.length).toBeGreaterThanOrEqual(2)
    })

    expect(seen[0]).toBe(seen[1])

    const defaults = seen[0].getDefaultOptions()
    expect(defaults.queries?.staleTime).toBe(1000 * 60 * 5)
    expect(defaults.queries?.refetchOnWindowFocus).toBe(false)
    expect(defaults.queries?.retry).toBe(2)
    expect(defaults.mutations?.retry).toBe(1)
  })
})
