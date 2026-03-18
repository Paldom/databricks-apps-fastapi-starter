import { render } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const handlerRefA: { current?: (lng: string) => void } = {}
const handlerRefB: { current?: (lng: string) => void } = {}
const onA = vi.fn((event: string, cb: (lng: string) => void) => {
  if (event === 'languageChanged') {
    handlerRefA.current = cb
  }
})
const offA = vi.fn()
const onB = vi.fn((event: string, cb: (lng: string) => void) => {
  if (event === 'languageChanged') {
    handlerRefB.current = cb
  }
})
const offB = vi.fn()

let i18nInstance = {
  resolvedLanguage: 'hu',
  dir: vi.fn(() => 'rtl'),
  on: onA,
  off: offA,
}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: i18nInstance,
  }),
}))

import { useLanguageEffect } from './use-language-effect'

function TestComponent() {
  useLanguageEffect()
  return null
}

describe('useLanguageEffect', () => {
  beforeEach(() => {
    i18nInstance = {
      resolvedLanguage: 'hu',
      dir: vi.fn(() => 'rtl'),
      on: onA,
      off: offA,
    }
    vi.clearAllMocks()
  })

  it('applies document language/dir and manages listeners', () => {
    const { unmount } = render(<TestComponent />)

    expect(document.documentElement.lang).toBe('hu')
    expect(document.documentElement.dir).toBe('rtl')
    expect(onA).toHaveBeenCalledWith('languageChanged', expect.any(Function))

    unmount()
    expect(offA).toHaveBeenCalledWith('languageChanged', handlerRefA.current)
  })

  it('falls back to english when resolved language is missing', () => {
    i18nInstance.resolvedLanguage = ''
    render(<TestComponent />)

    expect(document.documentElement.lang).toBe('en')
    i18nInstance.resolvedLanguage = 'hu'
  })

  it('re-registers listeners when the i18n instance changes', () => {
    const { rerender } = render(<TestComponent />)
    expect(onA).toHaveBeenCalledWith('languageChanged', expect.any(Function))

    i18nInstance = {
      resolvedLanguage: 'en',
      dir: vi.fn(() => 'ltr'),
      on: onB,
      off: offB,
    }

    rerender(<TestComponent />)
    expect(offA).toHaveBeenCalledWith('languageChanged', handlerRefA.current)
    expect(onB).toHaveBeenCalledWith('languageChanged', expect.any(Function))
  })
})
