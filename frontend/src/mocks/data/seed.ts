import { faker } from '@faker-js/faker'
import type {
  Project,
  Chat,
  Document,
  UserSettings,
  ChatSearchResult,
  DocumentStatus,
} from '@/shared/api/generated/models'

export function paginateArray<T extends { id: string }>(
  items: T[],
  cursor: string | null | undefined,
  limit: number
): { items: T[]; nextCursor: string | null; hasMore: boolean } {
  const startIndex = cursor
    ? items.findIndex((item) => item.id === cursor) + 1
    : 0
  if (startIndex < 0) {
    return { items: [], nextCursor: null, hasMore: false }
  }
  const slice = items.slice(startIndex, startIndex + limit)
  const hasMore = startIndex + limit < items.length
  const nextCursor = hasMore ? (slice[slice.length - 1]?.id ?? null) : null
  return { items: slice, nextCursor, hasMore }
}

function createChat(projectId: string, daysAgo: number): Chat {
  return {
    id: faker.string.uuid(),
    title: faker.lorem.sentence({ min: 3, max: 7 }).replace(/\.$/, ''),
    projectId,
    createdAt: faker.date.recent({ days: daysAgo + 30 }).toISOString(),
    updatedAt: faker.date.recent({ days: Math.max(daysAgo, 1) }).toISOString(),
  }
}

function createProject(index: number): {
  project: Project
  chats: Chat[]
} {
  const id = faker.string.uuid()
  const chatCount = faker.number.int({ min: 2, max: 6 })
  const chats = Array.from({ length: chatCount }, (_, i) =>
    createChat(id, i * 2)
  )
  return {
    project: {
      id,
      name: faker.commerce.department() + ' ' + faker.word.noun(),
      createdAt: faker.date.recent({ days: 60 + index * 10 }).toISOString(),
      chatCount,
    },
    chats,
  }
}

function createDocument(index: number): Document {
  const extensions = ['pdf', 'docx', 'md', 'txt']
  const mimeTypes: Record<string, string> = {
    pdf: 'application/pdf',
    docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    md: 'text/markdown',
    txt: 'text/plain',
  }
  const ext = extensions[index % extensions.length]
  const statuses: DocumentStatus[] = [
    'ingested',
    'ingested',
    'ingested',
    'pending',
  ]
  return {
    id: faker.string.uuid(),
    name: faker.system.commonFileName(ext),
    size: faker.number.int({ min: 1024, max: 10 * 1024 * 1024 }),
    type: mimeTypes[ext],
    status: statuses[index % statuses.length],
    projectId: null,
    addedAt: faker.date.recent({ days: index + 1 }).toISOString(),
  }
}

class MockDb {
  projects: Project[] = []
  chats: Map<string, Chat[]> = new Map()
  allChats: Chat[] = []
  documents: Document[] = []
  settings: UserSettings = {
    name: 'John Doe',
    email: 'john@example.com',
    notifications: true,
  }

  constructor() {
    this.reset()
  }

  reset() {
    this.projects = []
    this.chats = new Map()
    this.allChats = []
    this.documents = []
    this.settings = {
      name: 'John Doe',
      email: 'john@example.com',
      notifications: true,
    }

    const projectCount = faker.number.int({ min: 5, max: 8 })
    for (let i = 0; i < projectCount; i++) {
      const { project, chats } = createProject(i)
      this.projects.push(project)
      this.chats.set(project.id, chats)
      this.allChats.push(...chats)
    }
    // Sort all chats by updatedAt descending for recent queries
    this.allChats.sort(
      (a, b) =>
        new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
    )

    const docCount = faker.number.int({ min: 6, max: 10 })
    for (let i = 0; i < docCount; i++) {
      this.documents.push(createDocument(i))
    }
  }

  getSearchResults(
    query: string,
    cursor: string | null | undefined,
    limit: number
  ): {
    items: ChatSearchResult[]
    nextCursor: string | null
    hasMore: boolean
  } {
    const q = query.toLowerCase()
    const matched = this.allChats
      .filter((c) => c.title.toLowerCase().includes(q))
      .map((c) => {
        const project = this.projects.find((p) => p.id === c.projectId)
        return {
          ...c,
          projectName: project?.name ?? 'Unknown',
        }
      })
    return paginateArray(matched, cursor, limit)
  }

  getRecentChats(limit: number): {
    items: ChatSearchResult[]
    nextCursor: string | null
    hasMore: boolean
  } {
    const recent = this.allChats.slice(0, limit).map((c) => {
      const project = this.projects.find((p) => p.id === c.projectId)
      return {
        ...c,
        projectName: project?.name ?? 'Unknown',
      }
    })
    return { items: recent, nextCursor: null, hasMore: false }
  }
}

export const db = new MockDb()
