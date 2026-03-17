import { renderHook, act } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useDebouncedValue } from './use-debounced-value'

describe('useDebouncedValue', () => {
  it('returns the initial value immediately', () => {
    const { result } = renderHook(() => useDebouncedValue('hello', 300))
    expect(result.current).toBe('hello')
  })

  it('does not update until delay elapses', () => {
    vi.useFakeTimers()
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 300),
      { initialProps: { value: 'a' } }
    )

    rerender({ value: 'b' })
    expect(result.current).toBe('a')

    void act(() => vi.advanceTimersByTime(200))
    expect(result.current).toBe('a')

    void act(() => vi.advanceTimersByTime(100))
    expect(result.current).toBe('b')

    vi.useRealTimers()
  })

  it('only emits the final value after rapid changes', () => {
    vi.useFakeTimers()
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 300),
      { initialProps: { value: 'a' } }
    )

    rerender({ value: 'b' })
    void act(() => vi.advanceTimersByTime(100))

    rerender({ value: 'c' })
    void act(() => vi.advanceTimersByTime(100))

    rerender({ value: 'd' })
    void act(() => vi.advanceTimersByTime(300))

    expect(result.current).toBe('d')

    vi.useRealTimers()
  })
})
