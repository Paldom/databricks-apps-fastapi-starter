import { beforeEach, describe, expect, it } from 'vitest'
import { useUIStore } from './ui'
import { resetUIStore } from '@/test/utils'

describe('useUIStore', () => {
  beforeEach(() => {
    resetUIStore()
  })

  it('has default state', () => {
    const state = useUIStore.getState()
    expect(state.sidebarCollapsed).toBe(false)
    expect(state.theme).toBe('light')
  })

  it('toggles sidebar', () => {
    const { toggleSidebar } = useUIStore.getState()
    toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(true)
    toggleSidebar()
    expect(useUIStore.getState().sidebarCollapsed).toBe(false)
  })

  it('sets theme', () => {
    const { setTheme } = useUIStore.getState()
    setTheme('dark')
    expect(useUIStore.getState().theme).toBe('dark')
    setTheme('light')
    expect(useUIStore.getState().theme).toBe('light')
  })

  it('toggles the document sidebar state', () => {
    const { setDocumentSidebarOpen, toggleDocumentSidebar } =
      useUIStore.getState()

    setDocumentSidebarOpen(true)
    expect(useUIStore.getState().documentSidebarOpen).toBe(true)

    toggleDocumentSidebar()
    expect(useUIStore.getState().documentSidebarOpen).toBe(false)
  })

  it('sets the active project id', () => {
    const { setActiveProjectId } = useUIStore.getState()
    setActiveProjectId('some-project')
    expect(useUIStore.getState().activeProjectId).toBe('some-project')
  })

  it('sets the active chat id', () => {
    const { setActiveChatId } = useUIStore.getState()
    setActiveChatId('some-chat')
    expect(useUIStore.getState().activeChatId).toBe('some-chat')
  })

  it('toggles search dialog', () => {
    const { setSearchDialogOpen } = useUIStore.getState()
    setSearchDialogOpen(true)
    expect(useUIStore.getState().searchDialogOpen).toBe(true)
    setSearchDialogOpen(false)
    expect(useUIStore.getState().searchDialogOpen).toBe(false)
  })

  it('toggles settings dialog', () => {
    const { setSettingsDialogOpen } = useUIStore.getState()
    setSettingsDialogOpen(true)
    expect(useUIStore.getState().settingsDialogOpen).toBe(true)
    setSettingsDialogOpen(false)
    expect(useUIStore.getState().settingsDialogOpen).toBe(false)
  })
})
