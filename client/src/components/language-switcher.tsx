import { useTranslation } from '@/i18n/client'
import { cn } from '@/lib/utils'

const languages = [
  { code: 'en', label: 'ENG' },
  { code: 'hu', label: 'HUN' },
] as const

export function LanguageSwitcher() {
  const { i18n } = useTranslation()

  return (
    <div className="inline-flex items-center rounded-md border border-input">
      {languages.map(({ code, label }, index) => {
        const isActive = i18n.resolvedLanguage === code
        const isFirst = index === 0
        const isLast = index === languages.length - 1

        return (
          <button
            key={code}
            type="button"
            onClick={() => i18n.changeLanguage(code)}
            className={cn(
              'inline-flex h-8 items-center justify-center px-3 text-xs font-medium transition-colors',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
              'disabled:pointer-events-none disabled:opacity-50',
              isFirst && 'rounded-l-[calc(var(--radius)-1px)]',
              isLast && 'rounded-r-[calc(var(--radius)-1px)]',
              !isLast && 'border-r border-input',
              isActive
                ? 'bg-accent text-accent-foreground'
                : 'bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
