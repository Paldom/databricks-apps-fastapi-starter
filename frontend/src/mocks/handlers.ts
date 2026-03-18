import { getDashboardMock } from '@/shared/api/generated/dashboard/dashboard.msw'
import { getChatStreamMockHandler } from './chat-stream-handler'
import { projectHandlers } from './handlers/projects-handler'
import { chatHandlers } from './handlers/chats-handler'
import { documentHandlers } from './handlers/documents-handler'
import { http, HttpResponse } from 'msw'
import { db } from './data/seed'

// Settings handlers wired to mutable db.settings
const settingsHandlers = [
  http.get('*/api/settings', () => {
    return HttpResponse.json(db.settings)
  }),
  http.put('*/api/settings', async ({ request }) => {
    const body = (await request.json()) as typeof db.settings
    db.settings = { ...db.settings, ...body }
    return HttpResponse.json(db.settings)
  }),
]

export const handlers = [
  ...getDashboardMock(),
  ...settingsHandlers,
  getChatStreamMockHandler(),
  ...projectHandlers,
  ...chatHandlers,
  ...documentHandlers,
]
