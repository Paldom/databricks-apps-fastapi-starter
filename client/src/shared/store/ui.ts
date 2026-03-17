import { create } from 'zustand'
import { devtools, persist, subscribeWithSelector } from 'zustand/middleware'

type Theme = 'light' | 'dark'

type UIState = {
  // Layout
  sidebarCollapsed: boolean
  theme: Theme
  toggleSidebar: () => void
  setTheme: (theme: Theme) => void

  // Active selections
  activeProjectId: string | null
  activeChatId: string | null

  // Dialog/panel visibility
  searchDialogOpen: boolean
  settingsDialogOpen: boolean
  documentSidebarOpen: boolean

  // Setters
  setActiveProjectId: (projectId: string | null) => void
  setActiveChatId: (chatId: string | null) => void
  setSearchDialogOpen: (open: boolean) => void
  setSettingsDialogOpen: (open: boolean) => void
  setDocumentSidebarOpen: (open: boolean) => void
  toggleDocumentSidebar: () => void
}

export const useUIStore = create<UIState>()(
  devtools(
    persist(
      subscribeWithSelector((set) => ({
        // Layout
        sidebarCollapsed: false,
        theme: 'light',
        toggleSidebar: () =>
          set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
        setTheme: (theme) => set({ theme }),

        // Active selections
        activeProjectId: null,
        activeChatId: null,

        // Dialog/panel visibility
        searchDialogOpen: false,
        settingsDialogOpen: false,
        documentSidebarOpen: false,

        // Setters
        setActiveProjectId: (projectId) => set({ activeProjectId: projectId }),
        setActiveChatId: (chatId) => set({ activeChatId: chatId }),
        setSearchDialogOpen: (open) => set({ searchDialogOpen: open }),
        setSettingsDialogOpen: (open) => set({ settingsDialogOpen: open }),
        setDocumentSidebarOpen: (open) => set({ documentSidebarOpen: open }),
        toggleDocumentSidebar: () =>
          set((state) => ({ documentSidebarOpen: !state.documentSidebarOpen })),
      })),
      {
        name: 'ui-store',
        partialize: (state) => ({ theme: state.theme }),
      }
    ),
    { name: 'UIStore' }
  )
)
