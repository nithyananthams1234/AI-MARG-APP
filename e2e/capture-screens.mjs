// Captures fully loaded screenshots (fictional demo data) for the presentation.
// Usage: E2E_PASSWORD=... E2E_CHANNEL=chrome node capture-screens.mjs <outDir>
import { chromium, devices } from '@playwright/test';

const out = process.argv[2] ?? 'shots';
const browser = await chromium.launch(process.env.E2E_CHANNEL ? { channel: process.env.E2E_CHANNEL } : {});
const page = await browser.newPage({ ...devices['Pixel 7'] });
const base = process.env.E2E_BASE_URL ?? 'http://localhost:8082';

await page.goto(base + '/');
await page.getByPlaceholder('Enter your email').fill('mentor.demo@marg.example');
await page.getByPlaceholder('Enter your password').fill(process.env.E2E_PASSWORD ?? '');
await page.getByText('Sign in', { exact: true }).click();
await page.waitForURL(/dashboard/, { timeout: 30000 });

const shots = [
  ['/dashboard', 'Assigned schools'],
  ['/observations', 'Separation of mixtures'],
  ['/mentor-ai', 'Daily plan'],
  ['/action-plans', 'Fractions with concrete models'],
  ['/sync', 'Offline sync'],
];
for (const [path, text] of shots) {
  await page.goto(base + path);
  await page.getByText(text).first().waitFor({ timeout: 30000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${out}/${path.slice(1)}.png` });
}
await browser.close();
console.log('captured', shots.length);
