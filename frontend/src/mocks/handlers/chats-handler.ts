import { http, HttpResponse } from 'msw'
import { db, paginateArray } from '../data/seed'
import type {
  CreateChatRequest,
  UpdateChatRequest,
} from '@/shared/api/generated/models'
import { faker } from '@faker-js/faker'

export const chatHandlers = [
  http.get('*/api/projects/:projectId/chats', ({ params, request }) => {
    const { projectId } = params as { projectId: string }
    const url = new URL(request.url)
    const cursor = url.searchParams.get('cursor')
    const limit = Number(url.searchParams.get('limit') ?? '20')

    const chats = db.chats.get(projectId) ?? []
    const result = paginateArray(chats, cursor, limit)
    return HttpResponse.json(result)
  }),

  http.post('*/api/projects/:projectId/chats', async ({ params, request }) => {
    const { projectId } = params as { projectId: string }
    const body = (await request.json()) as CreateChatRequest
    const now = new Date().toISOString()
    const newChat = {
      id: faker.string.uuid(),
      title: body.title,
      projectId,
      createdAt: now,
      updatedAt: now,
    }
    const chats = db.chats.get(projectId) ?? []
    chats.unshift(newChat)
    db.chats.set(projectId, chats)
    db.allChats.unshift(newChat)
    // Update project chat count
    const project = db.projects.find((p) => p.id === projectId)
    if (project) project.chatCount++
    return HttpResponse.json(newChat, { status: 201 })
  }),

  http.patch('*/api/chats/:chatId', async ({ params, request }) => {
    const { chatId } = params as { chatId: string }
    const body = (await request.json()) as UpdateChatRequest
    const chat = db.allChats.find((c) => c.id === chatId)
    if (!chat) {
      return new HttpResponse(null, { status: 404 })
    }
    if (body.title != null) {
      chat.title = body.title
      chat.updatedAt = new Date().toISOString()
    }
    // Also update in project-specific map
    const projectChats = db.chats.get(chat.projectId)
    const chatInMap = projectChats?.find((c) => c.id === chatId)
    if (chatInMap && body.title != null) {
      chatInMap.title = body.title
      chatInMap.updatedAt = chat.updatedAt
    }
    return HttpResponse.json(chat)
  }),

  http.delete('*/api/chats/:chatId', ({ params }) => {
    const { chatId } = params as { chatId: string }
    const chat = db.allChats.find((c) => c.id === chatId)
    if (!chat) {
      return new HttpResponse(null, { status: 404 })
    }
    // Remove from allChats
    db.allChats = db.allChats.filter((c) => c.id !== chatId)
    // Remove from project-specific map
    const projectChats = db.chats.get(chat.projectId)
    if (projectChats) {
      db.chats.set(
        chat.projectId,
        projectChats.filter((c) => c.id !== chatId)
      )
    }
    // Update project chat count
    const project = db.projects.find((p) => p.id === chat.projectId)
    if (project) project.chatCount = Math.max(0, project.chatCount - 1)
    return new HttpResponse(null, { status: 204 })
  }),

  http.get('*/api/chats/search', ({ request }) => {
    const url = new URL(request.url)
    const q = url.searchParams.get('q') ?? ''
    const cursor = url.searchParams.get('cursor')
    const limit = Number(url.searchParams.get('limit') ?? '20')

    if (!q.trim()) {
      return HttpResponse.json({
        items: [],
        nextCursor: null,
        hasMore: false,
      })
    }

    const result = db.getSearchResults(q, cursor, limit)
    return HttpResponse.json(result)
  }),

  http.get('*/api/chats/recent', ({ request }) => {
    const url = new URL(request.url)
    const limit = Number(url.searchParams.get('limit') ?? '10')

    const result = db.getRecentChats(limit)
    return HttpResponse.json(result)
  }),
]
