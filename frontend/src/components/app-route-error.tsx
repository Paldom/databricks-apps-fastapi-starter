import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n/client'
import {
  isRouteErrorResponse,
  useNavigate,
  useRouteError,
} from 'react-router-dom'

export function AppRouteError() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const error = useRouteError()

  let message: string = t('errors.unexpected')

  if (isRouteErrorResponse(error)) {
    message =
      error.statusText || t('errors.requestFailed', { status: error.status })
  } else if (error instanceof Error && error.message) {
    message = error.message
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-muted/20 p-8 text-center">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold">{t('errors.title')}</h1>
        <p className="max-w-md text-balance text-sm text-muted-foreground">
          {message}
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-3">
        <Button onClick={() => navigate(0)}>{t('errors.tryAgain')}</Button>
        <Button
          variant="outline"
          onClick={() => navigate('/', { replace: true })}
        >
          {t('errors.goHome')}
        </Button>
      </div>
    </div>
  )
}
