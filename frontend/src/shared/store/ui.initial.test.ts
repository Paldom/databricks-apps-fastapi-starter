import { describe, expect, it } from 'vitest'
import { useUIStore } from './ui'

describe('useUIStore initial state', () => {
  it('matches the expected defaults', () => {
    const state = useUIStore.getState()

    expect(state.sidebarCollapsed).toBe(false)
    expect(state.theme).toBe('light')
    expect(state.searchDialogOpen).toBe(false)
    expect(state.settingsDialogOpen).toBe(false)
    expect(state.documentSidebarOpen).toBe(false)

    expect(state.activeProjectId).toBeNull()
    expect(state.activeChatId).toBeNull()
  })
})
