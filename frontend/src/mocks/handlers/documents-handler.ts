import { http, HttpResponse } from 'msw'
import { db, paginateArray } from '../data/seed'
import type { Document, DocumentStatus } from '@/shared/api/generated/models'
import { faker } from '@faker-js/faker'

export const documentHandlers = [
  http.get('*/api/documents', ({ request }) => {
    const url = new URL(request.url)
    const cursor = url.searchParams.get('cursor')
    const limit = Number(url.searchParams.get('limit') ?? '20')
    const status = url.searchParams.get('status') as DocumentStatus | null
    const projectId = url.searchParams.get('projectId')

    let filtered = db.documents
    if (status) {
      filtered = filtered.filter((d) => d.status === status)
    }
    if (projectId) {
      filtered = filtered.filter((d) => d.projectId === projectId)
    }

    const result = paginateArray(filtered, cursor, limit)
    return HttpResponse.json(result)
  }),

  http.post('*/api/documents', async ({ request }) => {
    const formData = await request.formData()
    const file = formData.get('file') as File | null
    const projectId = (formData.get('projectId') as string) || null

    if (!file) {
      return HttpResponse.json({ message: 'file is required' }, { status: 400 })
    }

    const newDoc: Document = {
      id: faker.string.uuid(),
      name: file.name,
      size: file.size,
      type: file.type || 'application/octet-stream',
      status: 'pending',
      projectId,
      addedAt: new Date().toISOString(),
    }
    db.documents.push(newDoc)

    // Simulate ingestion: transition to 'ingested' after 2-5 seconds
    const docId = newDoc.id
    setTimeout(
      () => {
        const doc = db.documents.find((d) => d.id === docId)
        if (doc && doc.status === 'pending') {
          doc.status = 'ingested'
        }
      },
      2000 + Math.random() * 3000
    )

    return HttpResponse.json(newDoc, { status: 201 })
  }),

  http.delete('*/api/documents/:documentId', ({ params }) => {
    const { documentId } = params as { documentId: string }
    const index = db.documents.findIndex((d) => d.id === documentId)
    if (index === -1) {
      return new HttpResponse(null, { status: 404 })
    }
    db.documents.splice(index, 1)
    return new HttpResponse(null, { status: 204 })
  }),

  http.get('*/api/documents/:documentId/status', ({ params }) => {
    const { documentId } = params as { documentId: string }
    const doc = db.documents.find((d) => d.id === documentId)
    if (!doc) {
      return new HttpResponse(null, { status: 404 })
    }
    return HttpResponse.json({ id: doc.id, status: doc.status })
  }),
]
