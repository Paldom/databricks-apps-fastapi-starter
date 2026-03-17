import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { App } from './app'
import { resetUIStore } from '@/test/utils'

describe('App', () => {
  beforeEach(() => {
    resetUIStore()
  })

  it('renders assistant thread empty state by default', async () => {
    render(<App />)

    await waitFor(() => {
      expect(
        screen.getByText('Start a conversation by typing a message below.')
      ).toBeInTheDocument()
    })
  })

  it('renders the app title in the breadcrumb when no chat is active', async () => {
    render(<App />)

    await waitFor(() => {
      const breadcrumb = screen.getByLabelText('breadcrumb')
      expect(breadcrumb).toBeInTheDocument()
    })
  })
})
