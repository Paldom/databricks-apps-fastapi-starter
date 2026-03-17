import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

const changeLanguage = vi.fn()

vi.mock('@/i18n/client', () => ({
  useTranslation: () => ({
    i18n: { resolvedLanguage: 'en', changeLanguage },
  }),
}))

import { LanguageSwitcher } from './language-switcher'

describe('LanguageSwitcher', () => {
  it('renders language buttons and switches language on click', async () => {
    const user = userEvent.setup()
    render(<LanguageSwitcher />)

    const english = screen.getByRole('button', { name: /eng/i })
    const hungarian = screen.getByRole('button', { name: /hun/i })

    expect(english).toHaveClass('bg-accent')
    expect(hungarian).toHaveClass('bg-transparent')

    await user.click(hungarian)
    expect(changeLanguage).toHaveBeenCalledWith('hu')
  })
})
