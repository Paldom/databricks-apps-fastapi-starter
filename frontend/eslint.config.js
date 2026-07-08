// For more info, see https://github.com/storybookjs/eslint-plugin-storybook#configuration-flat-config-format
import storybook from 'eslint-plugin-storybook'
import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import eslintReact from '@eslint-react/eslint-plugin'
import reactHooks from 'eslint-plugin-react-hooks'
import tanstackQuery from '@tanstack/eslint-plugin-query'

export default tseslint.config(
  {
    ignores: [
      'dist',
      'node_modules',
      'coverage',
      'reports',
      'public',
      'storybook-static',
      '*.config.{js,ts,mjs}',
      '.stryker-tmp',
      '.storybook',
      '.scannerwork',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    files: ['**/*.{ts,tsx}'],
    ...eslintReact.configs['recommended-type-checked'],
  },
  {
    files: ['**/*.{ts,tsx}'],
    ignores: ['**/*.config.ts'],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.json'],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      '@tanstack/query': tanstackQuery,
    },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      '@tanstack/query/exhaustive-deps': 'error',
      '@typescript-eslint/no-misused-promises': [
        'error',
        {
          checksVoidReturn: {
            attributes: false,
          },
        },
      ],
    },
  },
  {
    files: ['src/shared/**/*.{ts,tsx}'],
    ignores: [
      '**/*.test.{ts,tsx}',
      '**/*.stories.{ts,tsx}',
      'src/shared/api/generated/**',
    ],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: [
                '@/app/*',
                '@/stories/*',
                '@/mocks/*',
                '@/test/*',
                '@/components/**',
                '../*',
              ],
              message: 'shared code cannot import from app-specific modules',
            },
          ],
        },
      ],
    },
  },
  storybook.configs['flat/recommended']
)
