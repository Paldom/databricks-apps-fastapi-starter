import { http, HttpResponse } from 'msw'
import { db, paginateArray } from '../data/seed'
import type {
  CreateProjectRequest,
  UpdateProjectRequest,
} from '@/shared/api/generated/models'
import { faker } from '@faker-js/faker'

export const projectHandlers = [
  http.get('*/api/projects', ({ request }) => {
    const url = new URL(request.url)
    const cursor = url.searchParams.get('cursor')
    const limit = Number(url.searchParams.get('limit') ?? '20')

    const result = paginateArray(db.projects, cursor, limit)
    return HttpResponse.json(result)
  }),

  http.post('*/api/projects', async ({ request }) => {
    const body = (await request.json()) as CreateProjectRequest
    const newProject = {
      id: faker.string.uuid(),
      name: body.name,
      createdAt: new Date().toISOString(),
      chatCount: 0,
    }
    db.projects.push(newProject)
    db.chats.set(newProject.id, [])
    return HttpResponse.json(newProject, { status: 201 })
  }),

  http.patch('*/api/projects/:projectId', async ({ params, request }) => {
    const { projectId } = params as { projectId: string }
    const body = (await request.json()) as UpdateProjectRequest
    const project = db.projects.find((p) => p.id === projectId)
    if (!project) {
      return new HttpResponse(null, { status: 404 })
    }
    if (body.name != null) {
      project.name = body.name
    }
    return HttpResponse.json(project)
  }),

  http.delete('*/api/projects/:projectId', ({ params }) => {
    const { projectId } = params as { projectId: string }
    const index = db.projects.findIndex((p) => p.id === projectId)
    if (index === -1) {
      return new HttpResponse(null, { status: 404 })
    }
    db.projects.splice(index, 1)
    const chats = db.chats.get(projectId) ?? []
    db.allChats = db.allChats.filter((c) => !chats.some((pc) => pc.id === c.id))
    db.chats.delete(projectId)
    return new HttpResponse(null, { status: 204 })
  }),
]
