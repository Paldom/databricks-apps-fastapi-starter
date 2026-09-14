import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import i18n from 'i18next'
import { useTranslation } from './client'
import type { Locale } from './config'

function LanguageProbe({ lng }: { lng?: Locale }) {
  const { i18n: instance } = useTranslation(lng)
  return <span>{instance.resolvedLanguage}</span>
}

describe('useTranslation (client)', () => {
  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('en')
    })
  })

  it('starts with the default resolved language', () => {
    render(<LanguageProbe />)

    expect(screen.getByText('en')).toBeInTheDocument()
  })

  it('requests language change when lng prop differs', async () => {
    const spy = vi.spyOn(i18n, 'changeLanguage')

    act(() => {
      render(<LanguageProbe lng="hu" />)
    })

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith('hu')
    })

    spy.mockRestore()
  })
})
