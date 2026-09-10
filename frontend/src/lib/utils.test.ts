import { describe, expect, it } from 'vitest'
import { cn, formatCurrency, formatNumber } from './utils'

describe('cn (root lib)', () => {
  it('filters falsy values', () => {
    expect(cn('a', false, null, undefined, 'b')).toBe('a b')
  })

  it('merges tailwind classes correctly', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4')
    expect(cn('text-red-500', 'text-blue-500')).toBe('text-blue-500')
  })
})

describe('formatCurrency', () => {
  it('formats currency correctly', () => {
    expect(formatCurrency(1234.56)).toBe('$1,234.56')
  })

  it('handles zero', () => {
    expect(formatCurrency(0)).toBe('$0.00')
  })

  it('handles negative values', () => {
    expect(formatCurrency(-1234.56)).toBe('-$1,234.56')
  })
})

describe('formatNumber', () => {
  it('formats numbers correctly', () => {
    expect(formatNumber(1234567)).toBe('1,234,567')
  })

  it('handles zero', () => {
    expect(formatNumber(0)).toBe('0')
  })

  it('handles negative values', () => {
    expect(formatNumber(-1234)).toBe('-1,234')
  })
})
