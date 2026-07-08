import '@testing-library/jest-dom/vitest'
import { afterAll, afterEach, beforeAll } from 'vitest'
import { server } from '@/mocks/server'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from '../../public/locales/en/common.json'
import hu from '../../public/locales/hu/common.json'

// Initialize i18next for tests with the real locale fixtures.
void i18n.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  ns: ['common'],
  defaultNS: 'common',
  resources: {
    en: { common: en },
    hu: { common: hu },
  },
  interpolation: { escapeValue: false },
})

const noop = (): void => undefined

// Node >= 25 ships its own global localStorage/sessionStorage (WebStorage),
// which is a non-functional stub without --localstorage-file and shadows
// jsdom's working implementation, breaking zustand persist in tests.
// Replace any non-functional Storage with an in-memory implementation.
function createMemoryStorage(): Storage {
  const store = new Map<string, string>()
  return {
    get length() {
      return store.size
    },
    clear: () => store.clear(),
    getItem: (key: string) => store.get(key) ?? null,
    key: (index: number) => [...store.keys()][index] ?? null,
    removeItem: (key: string) => void store.delete(key),
    setItem: (key: string, value: string) => void store.set(key, value),
  }
}

for (const key of ['localStorage', 'sessionStorage'] as const) {
  if (typeof globalThis[key]?.getItem !== 'function') {
    Object.defineProperty(globalThis, key, {
      value: createMemoryStorage(),
      writable: true,
      configurable: true,
    })
  }
}

if (!globalThis.matchMedia) {
  globalThis.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: noop,
    removeEventListener: noop,
    addListener: noop,
    removeListener: noop,
    dispatchEvent: () => false,
  })
}

if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class ResizeObserver {
    observe(): void {
      noop()
    }

    unobserve(): void {
      noop()
    }

    disconnect(): void {
      noop()
    }
  }
}

if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = noop
}

if (!Element.prototype.scrollTo) {
  Element.prototype.scrollTo = noop
}

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
