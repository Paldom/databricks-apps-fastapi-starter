import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ThemeProvider } from './theme-provider'
import { resetUIStore } from '@/test/utils'

describe('ThemeProvider', () => {
  it('renders children and applies theme effects', () => {
    resetUIStore({ theme: 'light' })
    render(
      <ThemeProvider>
        <div>Theme content</div>
      </ThemeProvider>
    )

    expect(screen.getByText('Theme content')).toBeInTheDocument()
    expect(document.documentElement.style.colorScheme).toBe('light')
  })
})
