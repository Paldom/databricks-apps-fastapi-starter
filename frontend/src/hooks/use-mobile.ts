import * as React from 'react'

const MOBILE_BREAKPOINT = 768

function subscribe(onChange: () => void) {
  const mql = globalThis.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`)
  mql.addEventListener('change', onChange)
  return () => mql.removeEventListener('change', onChange)
}

export function useIsMobile() {
  return React.useSyncExternalStore(
    subscribe,
    () => globalThis.innerWidth < MOBILE_BREAKPOINT,
    () => false
  )
}
