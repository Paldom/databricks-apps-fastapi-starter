export const defaultLocale = 'en'
export const locales = ['en', 'hu'] as const

export type Locale = (typeof locales)[number]
