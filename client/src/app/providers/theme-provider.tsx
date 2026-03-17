import { type ReactNode } from 'react'
import { useThemeEffect } from '@/app/hooks/use-theme-effect'

export type ThemeProviderProps = {
  readonly children: ReactNode
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  useThemeEffect()

  return <>{children}</>
}
