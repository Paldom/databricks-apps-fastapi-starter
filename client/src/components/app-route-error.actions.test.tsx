import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

const navigateMock = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual =
    await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigateMock,
    useRouteError: () => new Error('Boom'),
    isRouteErrorResponse: () => false,
  }
})

import { AppRouteError } from './app-route-error'

describe('AppRouteError navigation actions', () => {
  it('invokes navigation handlers on action buttons', async () => {
    const user = userEvent.setup()
    render(<AppRouteError />)

    await user.click(screen.getByRole('button', { name: /try again/i }))
    expect(navigateMock).toHaveBeenCalledWith(0)

    await user.click(screen.getByRole('button', { name: /go back home/i }))
    expect(navigateMock).toHaveBeenCalledWith('/', { replace: true })
  })
})
