import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { AppRouteError } from '@/components/app-route-error'

function ThrowRouteError(): React.ReactElement {
  throw new Error('Kaboom')
}

describe('AppRouteError', () => {
  it('renders the fallback UI when a route throws', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    const router = createMemoryRouter([
      {
        path: '/',
        element: <ThrowRouteError />,
        errorElement: <AppRouteError />,
      },
    ])

    render(<RouterProvider router={router} />)

    expect(
      await screen.findByRole('heading', { name: /something went wrong/i })
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /try again/i })
    ).toBeInTheDocument()

    consoleError.mockRestore()
  })

  it('renders status text when the route error is a response', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    const router = createMemoryRouter([
      {
        path: '/',
        loader: () => {
          // eslint-disable-next-line @typescript-eslint/only-throw-error -- Response is valid for react-router loaders
          throw new Response('Boom', {
            status: 500,
            statusText: 'Server exploded',
          })
        },
        element: <div />,
        errorElement: <AppRouteError />,
      },
    ])

    render(<RouterProvider router={router} />)

    expect(await screen.findByText(/server exploded/i)).toBeInTheDocument()

    consoleError.mockRestore()
  })
})
