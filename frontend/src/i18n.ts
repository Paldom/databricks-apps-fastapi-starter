import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import HttpBackend from 'i18next-http-backend'

export const i18nInit = i18n
  .use(HttpBackend) // load /locales/{{lng}}/{{ns}}.json over HTTP
  .use(LanguageDetector) // detect user language
  .use(initReactI18next) // bind i18next to React
  .init({
    // what languages you actually ship:
    supportedLngs: ['en', 'hu'],
    fallbackLng: 'en',

    // where JSON files live
    backend: {
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },

    // reduce 404s like /en-US/... if you only serve plain 'en' or 'hu'
    load: 'languageOnly',

    // default namespace
    ns: ['common'],
    defaultNS: 'common',

    // useful while wiring things up
    debug: import.meta.env.MODE === 'development',

    // not needed for React; it already escapes
    interpolation: { escapeValue: false },
  })
