import { describe, expect, it } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useChatRuntime } from './use-chat-runtime'

describe('useChatRuntime', () => {
  it('returns a truthy runtime', () => {
    const { result } = renderHook(() => useChatRuntime())
    expect(result.current).toBeTruthy()
  })
})
