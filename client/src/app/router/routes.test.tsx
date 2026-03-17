import { describe, expect, it } from 'vitest'
import { router } from './routes'

describe('router configuration', () => {
  it('defines a single root route with an error boundary', () => {
    expect(router.routes.length).toBe(1)

    const rootRoute = router.routes[0] as {
      path?: string
      element?: unknown
      errorElement?: unknown
      children?: unknown
    }
    expect(rootRoute.path).toBe('/')
    expect(rootRoute.element).toBeTruthy()
    expect(rootRoute.errorElement).toBeTruthy()
    expect(rootRoute.children).toBeUndefined()
  })
})
