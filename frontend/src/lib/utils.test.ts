import { describe, expect, it } from 'vitest'
import { cn } from './utils'

describe('cn (root lib)', () => {
  it('filters falsy values', () => {
    expect(cn('a', false, null, undefined, 'b')).toBe('a b')
  })

  it('merges tailwind classes correctly', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4')
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500')
  })
})
