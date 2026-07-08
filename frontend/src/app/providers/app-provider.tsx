import { Suspense, type ReactNode } from 'react'
import { QueryClientProviderWithClient } from './query-client-provider'
import { ThemeProvider } from './theme-provider'
import { useTranslation } from 'react-i18next'

export type AppProvidersProps = {
  readonly children: ReactNode
}

export function AppProviders({ children }: AppProvidersProps) {
  const { t } = useTranslation()

  return (
    <QueryClientProviderWithClient>
      <ThemeProvider>
        <Suspense
          fallback={
            <div className="flex min-h-screen items-center justify-center">
              <p>{t('common.loadingApplication')}</p>
            </div>
          }
        >
          {children}
        </Suspense>
      </ThemeProvider>
    </QueryClientProviderWithClient>
  )
}
