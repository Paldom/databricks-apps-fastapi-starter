import { useUIStore } from '@/shared/store/ui'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

export function TestQueryWrapper({
  children,
}: Readonly<{ children: ReactNode }>) {
  const queryClient = createTestQueryClient()
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

export function resetUIStore(
  overrides: Partial<ReturnType<typeof useUIStore.getState>> = {}
) {
  useUIStore.persist?.clearStorage?.()
  useUIStore.setState({
    sidebarCollapsed: false,
    theme: 'light',
    activeProjectId: null,
    activeChatId: null,
    searchDialogOpen: false,
    settingsDialogOpen: false,
    documentSidebarOpen: false,
    ...overrides,
  })
}
