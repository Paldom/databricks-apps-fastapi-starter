import { act, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useIsMobile } from './use-mobile'

function Probe() {
  const isMobile = useIsMobile()
  return <div>{isMobile ? 'mobile' : 'desktop'}</div>
}

describe('useIsMobile', () => {
  it('detects mobile based on viewport width', async () => {
    const originalWidth = globalThis.innerWidth
    const originalMatchMedia = globalThis.matchMedia
    let changeHandler: ((event: Event) => void) | null = null
    let registeredHandler: EventListener | null = null
    const addEventListener = vi.fn((_event: string, cb: EventListener) => {
      registeredHandler = cb
      changeHandler = (event: Event) => cb(event)
    })
    const removeEventListener = vi.fn()
    const matchMediaMock = vi.fn((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener,
      removeEventListener,
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }))
    globalThis.matchMedia = matchMediaMock as typeof globalThis.matchMedia
    globalThis.innerWidth = 767

    const { unmount } = render(<Probe />)
    expect(matchMediaMock).toHaveBeenCalledWith('(max-width: 767px)')
    expect(addEventListener).toHaveBeenCalledWith(
      'change',
      expect.any(Function)
    )

    await waitFor(() => {
      expect(screen.getByText('mobile')).toBeInTheDocument()
    })

    globalThis.innerWidth = 768
    act(() => {
      changeHandler?.(new Event('change'))
    })
    await waitFor(() => {
      expect(screen.getByText('desktop')).toBeInTheDocument()
    })

    globalThis.innerWidth = 500
    act(() => {
      changeHandler?.(new Event('change'))
    })
    await waitFor(() => {
      expect(screen.getByText('mobile')).toBeInTheDocument()
    })

    unmount()
    expect(removeEventListener).toHaveBeenCalledWith(
      'change',
      registeredHandler
    )

    globalThis.innerWidth = originalWidth
    globalThis.matchMedia = originalMatchMedia
  })
})
