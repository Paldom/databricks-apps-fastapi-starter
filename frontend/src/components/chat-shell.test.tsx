import { MemoryRouter } from 'react-router-dom'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { ChatShell } from './chat-shell'
import { resetUIStore, TestQueryWrapper } from '@/test/utils'

describe('ChatShell', () => {
  beforeEach(() => {
    resetUIStore()
  })

  it('renders the assistant thread', () => {
    render(
      <TestQueryWrapper>
        <MemoryRouter>
          <ChatShell />
        </MemoryRouter>
      </TestQueryWrapper>
    )

    expect(
      screen.getByText('Start a conversation by typing a message below.')
    ).toBeInTheDocument()
  })

  it('renders the document sidebar when open', () => {
    resetUIStore({ documentSidebarOpen: true })

    const { container } = render(
      <TestQueryWrapper>
        <MemoryRouter>
          <ChatShell />
        </MemoryRouter>
      </TestQueryWrapper>
    )

    expect(screen.getByText('Documents')).toBeInTheDocument()
    expect(container.querySelector('[data-separator]')).toBeTruthy()
  })
})
