/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { storybookTest } from '@storybook/addon-vitest/vitest-plugin'
import { playwright } from '@vitest/browser-playwright'
const dirname =
  typeof __dirname !== 'undefined'
    ? __dirname
    : path.dirname(fileURLToPath(import.meta.url))

// More info at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(dirname, './src'),
      },
    },
    server: {
      proxy: {
        '/api': {
          target,
          changeOrigin: true,
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              if (env.VITE_DEV_MOCK_AUTH === 'true') {
                proxyReq.setHeader(
                  'X-Forwarded-User',
                  env.VITE_DEV_USER_ID || 'local-user'
                )
                proxyReq.setHeader(
                  'X-Forwarded-Preferred-Username',
                  env.VITE_DEV_USERNAME || 'Local Dev'
                )
                proxyReq.setHeader(
                  'X-Forwarded-Email',
                  env.VITE_DEV_EMAIL || 'local@example.com'
                )
              }
            })
          },
        },
      },
    },
    build: {
      outDir: path.resolve(dirname, '../backend/public'),
      emptyOutDir: true,
      sourcemap: true,
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom', 'react-router-dom'],
            'query-vendor': ['@tanstack/react-query'],
          },
        },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      exclude: ['**/node_modules/**', '**/.stryker-tmp/**'],
      coverage: {
        provider: 'v8',
        reporter: ['text', 'html', 'json', 'lcov'],
        include: ['src/**/*.{ts,tsx}'],
        exclude: [
          'src/**/*.test.{ts,tsx}',
          'src/**/*.stories.{ts,tsx}',
          'src/stories/**',
          '**/.stryker-tmp/**',
          'src/main.tsx',
          'src/mocks/**',
          'src/shared/api/generated/**',
          'src/shared/types/**',
          'src/vite-env.d.ts',
          'src/**/*.d.ts',
        ],
        thresholds: {
          statements: 80,
          branches: 80,
          functions: 80,
          lines: 80,
        },
      },
      projects:
        process.env.VITEST_BROWSER === 'true'
          ? [
              {
                plugins: [
                  // The plugin will run tests for the stories defined in your Storybook config
                  // See options at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon#storybooktest
                  storybookTest({
                    configDir: path.join(dirname, '.storybook'),
                  }),
                ],
                test: {
                  name: 'storybook',
                  browser: {
                    enabled: true,
                    headless: true,
                    provider: playwright({}),
                    instances: [
                      {
                        browser: 'chromium',
                      },
                    ],
                  },
                  setupFiles: ['.storybook/vitest.setup.ts'],
                },
              },
            ]
          : undefined,
    },
  }
})
