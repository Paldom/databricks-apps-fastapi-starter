import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { DocumentSidebar } from './document-sidebar'
import { resetUIStore, TestQueryWrapper } from '@/test/utils'

describe('DocumentSidebar', () => {
  beforeEach(() => {
    resetUIStore({ documentSidebarOpen: true })
  })

  it('renders the document list from the server', async () => {
    render(
      <TestQueryWrapper>
        <DocumentSidebar />
      </TestQueryWrapper>
    )

    expect(screen.getByText('Documents')).toBeInTheDocument()

    // Wait for documents to load from MSW
    await waitFor(() => {
      expect(screen.getByText(/Added documents/)).toBeInTheDocument()
    })

    // Document status is exposed as an accessible text alternative
    expect(
      screen.getAllByText(/^(Ready|Processing\.\.\.|Error)$/).length
    ).toBeGreaterThan(0)
  })

  it('shows upload section', () => {
    render(
      <TestQueryWrapper>
        <DocumentSidebar />
      </TestQueryWrapper>
    )

    expect(screen.getByText('Upload new')).toBeInTheDocument()
  })
})
