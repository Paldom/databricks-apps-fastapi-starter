import { useTranslation as useTranslationOrg } from 'react-i18next'
import { useEffect, useState } from 'react'
import { type Locale } from './config'

type Namespace = Parameters<typeof useTranslationOrg>[0]

export function useTranslation(lng?: Locale, ns: Namespace = 'common') {
  const ret = useTranslationOrg(ns)
  const { i18n } = ret
  const [activeLng, setActiveLng] = useState(i18n.resolvedLanguage)

  useEffect(() => {
    if (activeLng === i18n.resolvedLanguage) return
    setActiveLng(i18n.resolvedLanguage)
  }, [activeLng, i18n.resolvedLanguage])

  // Only force a language change when an explicit lng was passed
  useEffect(() => {
    if (!lng || i18n.resolvedLanguage === lng) return
    void i18n.changeLanguage(lng)
  }, [lng, i18n])

  return ret
}
