/**
 * Browser end-to-end tests against the running MARG stack:
 *   frontend (Expo web) -> backend -> PostgreSQL (marg_demo) -> Classroom Coach / Mentor Intelligence.
 * Uses the fictional demo mentor. Password is read from E2E_PASSWORD (never committed).
 */
import { expect, test, type Page } from '@playwright/test';

const EMAIL = process.env.E2E_EMAIL ?? 'mentor.demo@marg.example';
const PASSWORD = process.env.E2E_PASSWORD ?? '';

async function signIn(page: Page) {
  await page.goto('/');
  await page.getByPlaceholder('Enter your email').fill(EMAIL);
  await page.getByPlaceholder('Enter your password').fill(PASSWORD);
  await page.getByText('Sign in', { exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 30_000 });
}

function watchErrors(page: Page) {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => {
    if (m.type() === 'error' && !/favicon|DevTools|Download the React DevTools/.test(m.text())) errors.push(`console: ${m.text()}`);
  });
  page.on('response', (r) => {
    if (r.url().includes('/api/v1/') && r.status() >= 500) errors.push(`HTTP ${r.status()} ${r.url()}`);
  });
  return errors;
}

test.beforeAll(() => {
  if (!PASSWORD) throw new Error('Set E2E_PASSWORD to the demo mentor password');
});

test('protected routes redirect to login and wrong password is rejected', async ({ page }) => {
  await page.goto('/tasks');
  await expect(page.getByPlaceholder('Enter your email')).toBeVisible({ timeout: 30_000 });
  await page.getByPlaceholder('Enter your email').fill(EMAIL);
  await page.getByPlaceholder('Enter your password').fill('definitely-wrong-password');
  await page.getByText('Sign in', { exact: true }).click();
  await expect(page.getByText('Incorrect email or password.')).toBeVisible();
});

const SCREENS: [string, RegExp][] = [
  ['/dashboard', /Kavya Subramanian/],
  ['/schools', /Government Middle School, Kalavai Road/],
  ['/visits', /Panchayat Union Primary School, Thiruvalam/],
  ['/observations', /Equivalent fractions|Science|Mathematics/],
  ['/action-plans', /Fractions with concrete models/],
  ['/follow-ups', /Share photos of student strip work|Confirm read-aloud schedule/],
  ['/tasks', /Submit monthly mentoring report to block office/],
  ['/schedule', /Schedule|Agenda|Workload/i],
  ['/notifications', /Welcome to MARG|Task overdue|Upcoming school visit/],
  ['/reports', /Learning gaps|Activity/i],
  ['/classroom-coach', /Classroom Coach/],
  ['/mentor-ai', /Mentor AI/],
  ['/profile', /mentor\.demo@marg\.example/],
  ['/sync', /Offline sync/],
];

test('every mentor screen renders real data without errors', async ({ page }) => {
  const errors = watchErrors(page);
  await signIn(page);
  for (const [path, expected] of SCREENS) {
    await page.goto(path);
    await expect(page.getByText(expected).first(), `content on ${path}`).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText('Could not load data')).toHaveCount(0);
    await page.screenshot({ path: `screenshots${path.replace(/\//g, '_') || '_root'}.png`, fullPage: true });
  }
  expect(errors, errors.join('\n')).toEqual([]);
});

test('mentor creates a task and it is persisted', async ({ page }) => {
  const errors = watchErrors(page);
  const title = `E2E task ${Date.now()}`;
  await signIn(page);
  await page.goto('/tasks');
  await page.getByLabel('Add task').click();
  await page.getByLabel('Task title').fill(title);
  await page.getByRole('button', { name: 'Create task' }).click();
  await expect(page.getByText(title)).toBeVisible({ timeout: 20_000 });
  // Persisted: survives a full reload (fresh fetch from the backend).
  await page.reload();
  await expect(page.getByText(title)).toBeVisible({ timeout: 20_000 });
  expect(errors, errors.join('\n')).toEqual([]);
});

test('Classroom Coach answers with knowledge-base sources', async ({ page }) => {
  test.setTimeout(240_000);
  await signIn(page);
  await page.goto('/classroom-coach');
  await page.getByLabel('Question for the Classroom Coach').fill('How can a teacher check whether students understand equivalent fractions during a lesson?');
  await page.getByRole('button', { name: 'Ask the Coach' }).click();
  await expect(page.getByText(/\[S1\]|S1/).first()).toBeVisible({ timeout: 180_000 });
  await page.screenshot({ path: 'screenshots_coach_answer.png', fullPage: true });
});
