import { act, render } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useThemeEffect } from './use-theme-effect'
import { resetUIStore } from '@/test/utils'
import { useUIStore } from '@/shared/store/ui'

function TestComponent() {
  useThemeEffect()
  return null
}

describe('useThemeEffect', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark')
    document.documentElement.style.colorScheme = ''
  })

  it('sets the light theme on the document', () => {
    resetUIStore({ theme: 'light' })
    render(<TestComponent />)

    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(document.documentElement.style.colorScheme).toBe('light')
  })

  it('sets the dark theme on the document', () => {
    resetUIStore({ theme: 'dark' })
    render(<TestComponent />)

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })

  it('updates the document when the theme changes', () => {
    resetUIStore({ theme: 'light' })
    render(<TestComponent />)

    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(document.documentElement.style.colorScheme).toBe('light')

    act(() => {
      useUIStore.getState().setTheme('dark')
    })

    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })
})
