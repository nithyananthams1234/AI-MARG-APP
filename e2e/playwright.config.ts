import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 120_000,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8082',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'mobile-chrome',
      // E2E_CHANNEL=chrome uses the locally installed Google Chrome (no browser download).
      use: { ...devices['Pixel 7'], ...(process.env.E2E_CHANNEL ? { channel: process.env.E2E_CHANNEL } : {}) },
    },
  ],
});
