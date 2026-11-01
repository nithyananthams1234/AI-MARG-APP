/**
 * Screen workflow test: real root layout + login + dashboard screens with a
 * fake backend (axios adapter). Verifies the route guard, failed login,
 * successful login, and that the dashboard renders API data (no mock data).
 */
import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios';
import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { renderRouter } from 'expo-router/testing-library';

jest.mock('@/lib/storage', () => {
  const m: Record<string, string> = {};
  return { kv: { get: async (k: string) => m[k] ?? null, set: async (k: string, v: string) => void (m[k] = v), remove: async (k: string) => void delete m[k] } };
});
jest.mock('@/lib/secure-storage', () => {
  const m: Record<string, string> = {};
  return { secureStorage: { get: async (k: string) => m[k] ?? null, set: async (k: string, v: string) => void (m[k] = v), remove: async (k: string) => void delete m[k] } };
});
jest.mock('expo-network', () => ({
  addNetworkStateListener: () => ({ remove() {} }),
  useNetworkState: () => ({ isConnected: true, isInternetReachable: true }),
}));

import axios from 'axios';

import { api } from '@/lib/api/client';
import RootLayout from '@/app/_layout';
import Dashboard from '@/app/dashboard';
import Login from '@/app/index';

const PASSWORD = 'correct-horse-battery';

const routes: Record<string, (c: InternalAxiosRequestConfig) => unknown> = {
  '/auth/me': () => ({ id: 'u1', full_name: 'Kavya Subramanian', email: 'mentor.fixture@marg.example', role: 'Mentor', roles: ['Mentor'], assigned_schools: [] }),
  '/reports/dashboard': () => ({
    total_schools: 4, total_visits: 8, completed_visits: 3, pending_tasks: 6, completed_tasks: 1, total_learning_gaps: 4,
    total_action_plans: 3, upcoming_visits: 3, overdue_tasks: 1, total_observations: 4, recommendations_awaiting_review: 1,
    active_action_plans: 2, open_follow_ups: 4, follow_ups_awaiting_verification: 1, unread_notifications: 9,
  }),
  '/schools/': () => [{ id: 's1', name: 'Aadhirai Government Higher Secondary School', code: 'AAD-GHSS-GUD' }],
  '/school-visits/': (c) =>
    c.params?.visit_status === 'planned'
      ? [{ id: 'v1', school_id: 's1', scheduled_at: '2030-01-02T04:30:00Z', status: 'planned', notes: 'Check read-aloud routine', version: 1 }]
      : [],
  '/mentor-tasks/': () => [
    { id: 't1', title: 'Submit monthly mentoring report', status: 'pending', priority: 'high', priority_score: 68, due_at: '2020-01-01T00:00:00Z', version: 1 },
  ],
  '/follow-ups/': () => [],
  '/teachers/': () => [],
  '/coach/status': () => ({ available: true, knowledge_chunks: 12 }),
  '/mentor-ai/status': () => ({ available: true }),
  '/mentor-ai/proposals': () => ({ schema_version: '1', success: true, data: [], error: null }),
};

const adapter: AxiosAdapter = async (config) => {
  const url = (config.url ?? '').replace(/^https?:\/\/[^/]+\/api\/v1/, '');
  let status = 200;
  let data: unknown;
  if (url === '/auth/login') {
    const ok = String(config.data).includes(`password=${PASSWORD}`);
    status = ok ? 200 : 401;
    data = ok ? { access_token: 'A', refresh_token: 'R'.repeat(30), expires_in: 1800 } : { detail: 'Invalid email or password' };
  } else if (routes[url]) {
    data = routes[url](config);
  } else {
    data = [];
  }
  const response = { data, status, statusText: '', headers: {}, config };
  if (status >= 400) throw new axios.AxiosError('fail', String(status), config, null, response);
  return response;
};

beforeEach(() => {
  api.defaults.adapter = adapter;
});

const app = { _layout: RootLayout, index: Login, dashboard: Dashboard };

it('redirects signed-out users to login, rejects bad credentials, then signs in to a live dashboard', async () => {
  await renderRouter(app, { initialUrl: '/dashboard' });

  // Route guard: protected route -> login
  expect(await screen.findByText('Sign in')).toBeTruthy();
  expect(screen).toHavePathname('/');

  const [email, password] = screen.getAllByPlaceholderText(/./);
  await fireEvent.changeText(email, 'mentor.fixture@marg.example');
  await fireEvent.changeText(password, 'wrong-password');
  await fireEvent.press(screen.getByText('Sign in'));
  expect(await screen.findByText('Incorrect email or password.')).toBeTruthy();

  await fireEvent.changeText(password, PASSWORD);
  await fireEvent.press(screen.getByText('Sign in'));

  // Lands on the dashboard populated from the API
  await waitFor(() => expect(screen).toHavePathname('/dashboard'));
  expect(await screen.findByText('Kavya Subramanian')).toBeTruthy();
  expect(await screen.findByText('YOUR WORKSPACE')).toBeTruthy();
  expect(screen.getByText('MENTORING CALENDAR')).toBeTruthy();
  expect(screen.getByText('MENTOR AI PLANNER')).toBeTruthy();
  expect(screen.getByText('LEARNING GAPS')).toBeTruthy();
  expect(screen.getByRole('button', { name: /Assigned Schools/ })).toBeTruthy();
  expect(screen.getByRole('button', { name: /Pending Tasks/ })).toBeTruthy();
});
