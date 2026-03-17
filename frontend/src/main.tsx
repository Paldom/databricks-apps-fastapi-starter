import React, { Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import { App } from '@/app/app'
import { i18nInit } from './i18n'
import './index.css'
import type { SetupWorker } from 'msw/browser'

type BrowserMocksModule = { worker: SetupWorker }

async function enableMocks() {
  if (!import.meta.env.DEV) {
    return
  }

  const enableMocksFlag = import.meta.env.VITE_ENABLE_MOCKS
  const shouldEnableMocks = enableMocksFlag === 'true'

  if (!shouldEnableMocks) {
    return
  }

  const mocksModule = (await import('@/mocks/browser')) as BrowserMocksModule
  await mocksModule.worker.start({ onUnhandledRequest: 'bypass' })
}

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Root element not found')
}

await enableMocks()
await i18nInit

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <Suspense fallback={<div>Loading...</div>}>
      <App />
    </Suspense>
  </React.StrictMode>
)
