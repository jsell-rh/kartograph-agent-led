import { defineConfig } from 'vitest/config'
import { fileURLToPath } from 'node:url'
import { resolve, dirname } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  // Set root to the app/utils directory so vite picks up tsconfig.vitest.json
  // instead of the root tsconfig.json which references Nuxt-generated .nuxt/tsconfig*.json
  root: resolve(__dirname, 'app/utils'),
  test: {
    root: resolve(__dirname, 'app/utils'),
    include: ['**/*.test.ts'],
    environment: 'node',
  },
})
