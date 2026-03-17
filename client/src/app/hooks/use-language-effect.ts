import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'

export function useLanguageEffect() {
  const { i18n } = useTranslation()

  useEffect(() => {
    const applyLanguageAttributes = () => {
      document.documentElement.lang = i18n.resolvedLanguage || 'en'
      document.documentElement.dir = i18n.dir() // "ltr" | "rtl"
    }

    applyLanguageAttributes()
    i18n.on('languageChanged', applyLanguageAttributes)

    return () => {
      i18n.off('languageChanged', applyLanguageAttributes)
    }
  }, [i18n])
}
