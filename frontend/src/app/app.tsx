import { RouterProvider } from 'react-router-dom'
import { AppProviders } from './providers/app-provider'
import { router } from './router/routes'
import { useLanguageEffect } from '@/app/hooks/use-language-effect'

export function App() {
  useLanguageEffect()

  return (
    <AppProviders>
      <RouterProvider router={router} />
    </AppProviders>
  )
}
