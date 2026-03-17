import { Suspense, type ReactNode } from 'react'
import { QueryClientProviderWithClient } from './query-client-provider'
import { useTranslation } from '@/i18n/client'

export type AppProvidersProps = {
  readonly children: ReactNode
}

export function AppProviders({ children }: AppProvidersProps) {
  const { t } = useTranslation()

  return (
    <QueryClientProviderWithClient>
      <Suspense
        fallback={
          <div className="flex min-h-screen items-center justify-center">
            <p>{t('common.loadingApplication')}</p>
          </div>
        }
      >
        {children}
      </Suspense>
    </QueryClientProviderWithClient>
  )
}
