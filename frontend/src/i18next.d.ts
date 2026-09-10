import 'i18next'
import type { defaultNS } from './i18n'
import type common from '../public/locales/en/common.json'

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: typeof defaultNS
    resources: { common: typeof common }
  }
}
