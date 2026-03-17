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

// Export for TypeScript
export const defaultNS = 'common'
export const resources = {
  en: {
    common: {
      app: { title: '', name: '', edition: '', logoAlt: '' },
      chat: {
        newChat: '',
        searchChats: '',
        searchPlaceholder: '',
        noResults: '',
        recentChats: '',
        share: '',
        rename: '',
        duplicate: '',
        delete: '',
        confirmDelete: '',
        emptyState: '',
      },
      project: {
        addProject: '',
        editName: '',
        remove: '',
        selectProject: '',
      },
      user: {
        settings: '',
        logOut: '',
      },
      settings: {
        title: '',
        nav: { general: '', profile: '', notifications: '' },
        general: {
          title: '',
          theme: '',
          themeDescription: '',
          light: '',
          dark: '',
          language: '',
          languageDescription: '',
        },
        profile: {
          title: '',
          name: '',
          email: '',
          save: '',
          cancel: '',
          nameRequired: '',
          emailInvalid: '',
          saveError: '',
          saveSuccess: '',
        },
        notifications: { title: '', enable: '', enableDescription: '' },
      },
      document: {
        title: '',
        addDocument: '',
        addedDocuments: '',
        uploadNew: '',
        pending: '',
        ingested: '',
        error: '',
        dropzoneIdle: '',
        dropzoneActive: '',
        dropzoneAccepted: '',
        removeDocument: '',
      },
      common: {
        loading: '',
        error: '',
        retry: '',
        close: '',
        loadingApplication: '',
        loadingTranslations: '',
        loadMore: '',
        openMenu: '',
        more: '',
        units: {
          byte: '',
          kilobyte: '',
          megabyte: '',
          gigabyte: '',
        },
      },
      errors: {
        title: '',
        unexpected: '',
        requestFailed: '',
        tryAgain: '',
        goHome: '',
      },
      sidebar: {
        title: '',
        description: '',
        toggle: '',
      },
      command: {
        title: '',
        description: '',
      },
    },
  },
} as const

export { default } from 'i18next'
