import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: '.',
  timeout: 30000,
  use: {
    baseURL: 'http://localhost:8000',
    headless: true,
  },
  reporter: [['list'], ['html', { open: 'never' }]],
})
