import { defineConfig } from 'orval'

export default defineConfig({
  api: {
    input: {
      target: '../backend/openapi.yaml',
      // The chat stream endpoint is consumed by the hand-written NDJSON
      // adapter (src/lib/assistant); a generated react-query client for it
      // would not compile and is never imported.
      filters: {
        mode: 'exclude',
        tags: ['chat'],
        // @ts-expect-error -- added in newer orval; no-op on the pinned 8.2.0
        includeUnreferencedSchemas: true,
      },
    },
    output: {
      mode: 'tags-split',
      target: 'src/shared/api/generated/index.ts',
      schemas: 'src/shared/api/generated/models',
      client: 'react-query',
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
