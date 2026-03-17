import { defineConfig } from 'orval'

export default defineConfig({
  api: {
    input: '../openapi/openapi.json',
    output: {
      mode: 'tags-split',
      target: 'src/shared/api/generated/index.ts',
      schemas: 'src/shared/api/generated/models',
      client: 'react-query',
      mock: {
        type: 'msw',
        useExamples: true,
        delay: 100,
      },
      override: {
        mutator: {
          path: 'src/shared/api/client.ts',
          name: 'customInstance',
        },
        operations: {
          listProjects: {
            query: { useInfinite: true, useInfiniteQueryParam: 'cursor' },
          },
          listProjectChats: {
            query: { useInfinite: true, useInfiniteQueryParam: 'cursor' },
          },
          searchChats: {
            query: { useInfinite: true, useInfiniteQueryParam: 'cursor' },
          },
          listDocuments: {
            query: { useInfinite: true, useInfiniteQueryParam: 'cursor' },
          },
        },
      },
    },
  },
})
