import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { DocumentSidebar } from './document-sidebar'
import { resetUIStore, TestQueryWrapper } from '@/test/utils'
import { File as NodeFile } from 'node:buffer'
import { act, fireEvent } from '@testing-library/react'
import { vi, afterEach } from 'vitest'
import { server } from '@/mocks/server'
import { http, HttpResponse } from 'msw'
import { db } from '@/mocks/data/seed'

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

afterEach(() => vi.unstubAllGlobals())

it('uploads the file as multipart and refreshes the documents list', async () => {
  resetUIStore({ documentSidebarOpen: true })
  // Use matching native File/FormData implementations for MSW's Node Request serializer.
  const nativeFormData = await new Response(new URLSearchParams()).formData()
  vi.stubGlobal('FormData', nativeFormData.constructor)
  vi.stubGlobal('File', NodeFile)
  let uploaded: File | undefined
  let listRequests = 0
  server.use(
    http.get('*/api/documents', () => {
      listRequests++
      return HttpResponse.json({
        items: uploaded
          ? [
              {
                id: 'uploaded',
                name: uploaded.name,
                size: uploaded.size,
                type: uploaded.type,
                status: 'pending',
                addedAt: new Date().toISOString(),
              },
            ]
          : [],
        hasMore: false,
        nextCursor: null,
      })
    }),
    http.post('*/api/knowledge/files', async ({ request }) => {
      const data = await request.formData()
      uploaded = data.get('file') as File
      return HttpResponse.json(
        {
          document_id: 'uploaded',
          relative_path: uploaded.name,
          full_path: `/Volumes/test/${uploaded.name}`,
          size_bytes: uploaded.size,
          status: 'pending',
        },
        { status: 201 }
      )
    }),
    http.get('*/api/documents/uploaded/status', () =>
      HttpResponse.json({ id: 'uploaded', status: 'pending' })
    )
  )
  const { container } = render(
    <TestQueryWrapper>
      <DocumentSidebar />
    </TestQueryWrapper>
  )
  await waitFor(() => expect(listRequests).toBe(1))
  fireEvent.change(container.querySelector('input[type="file"]')!, {
    target: {
      files: [
        new NodeFile(['file bytes'], 'notes.pdf', { type: 'application/pdf' }),
      ],
    },
  })
  expect(await screen.findByText('notes.pdf')).toBeInTheDocument()
  expect(await uploaded?.text()).toBe('file bytes')
  expect(listRequests).toBe(2)
  expect(screen.getByText('Pending')).toBeInTheDocument()
})

it('polls pending document status every ten seconds and stops after ingestion', async () => {
  resetUIStore({ documentSidebarOpen: true })
  const pending = { ...db.documents[0], id: 'pending-doc', status: 'pending' }
  let calls = 0
  server.use(
    http.get('*/api/documents', () =>
      HttpResponse.json({ items: [pending], nextCursor: null, hasMore: false })
    ),
    http.get('*/api/documents/pending-doc/status', () => {
      calls++
      return HttpResponse.json({
        id: pending.id,
        status: calls > 1 ? 'ingested' : 'pending',
      })
    })
  )
  // Only fake intervals so MSW and Testing Library can flush requests normally.
  vi.useFakeTimers({
    toFake: ['setInterval', 'clearInterval'],
    shouldAdvanceTime: true,
  })
  try {
    render(
      <TestQueryWrapper>
        <DocumentSidebar />
      </TestQueryWrapper>
    )
    await waitFor(() => expect(calls).toBe(1))
    await act(() => vi.advanceTimersByTimeAsync(9000))
    expect(calls).toBe(1)
    await act(() => vi.advanceTimersByTimeAsync(1000))
    await screen.findByText('Ingested')
    await act(() => vi.advanceTimersByTimeAsync(30_000))
    expect(calls).toBe(2)
  } finally {
    vi.useRealTimers()
  }
})
