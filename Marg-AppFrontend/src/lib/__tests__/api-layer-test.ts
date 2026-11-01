/**
 * Unit tests for the API layer: error normalisation, token refresh on 401,
 * offline queueing and outbox outcome handling. No network: a custom axios
 * adapter plays the backend.
 */
import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios';

const mem: Record<string, string> = {};
jest.mock('@/lib/storage', () => ({
  kv: {
    get: async (k: string) => mem[k] ?? null,
    set: async (k: string, v: string) => {
      mem[k] = v;
    },
    remove: async (k: string) => {
      delete mem[k];
    },
  },
}));
const secure: Record<string, string> = {};
jest.mock('@/lib/secure-storage', () => ({
  secureStorage: {
    get: async (k: string) => secure[k] ?? null,
    set: async (k: string, v: string) => {
      secure[k] = v;
    },
    remove: async (k: string) => {
      delete secure[k];
    },
  },
}));
jest.mock('expo-network', () => ({ addNetworkStateListener: () => ({ remove() {} }) }));

import axios from 'axios';

import { api, ApiError, login, toApiError, tokenStore } from '@/lib/api/client';
import { useOutbox } from '@/lib/offline/outbox';
import { isQueued, runOrQueue } from '@/lib/query';

type Handler = (config: InternalAxiosRequestConfig) => { status: number; data?: unknown } | 'network';
let handler: Handler;
const calls: InternalAxiosRequestConfig[] = [];

const adapter: AxiosAdapter = async (config) => {
  calls.push(config);
  const res = handler(config);
  if (res === 'network') {
    const err = new axios.AxiosError('Network Error', 'ERR_NETWORK', config);
    throw err;
  }
  const response = { data: res.data, status: res.status, statusText: '', headers: {}, config };
  if (res.status >= 400) throw new axios.AxiosError('fail', String(res.status), config, null, response);
  return response;
};

beforeEach(async () => {
  api.defaults.adapter = adapter;
  axios.defaults.adapter = adapter; // refresh call uses the bare axios instance
  calls.length = 0;
  Object.keys(mem).forEach((k) => delete mem[k]);
  await tokenStore.clear();
  useOutbox.setState({ items: [], syncing: false, lastError: null, lastSyncAt: null });
});

describe('error normalisation', () => {
  it('uses the backend detail message', () => {
    const e = toApiError(
      new axios.AxiosError('x', '409', undefined, null, {
        status: 409, data: { detail: 'Only planned visits can be updated' }, statusText: '', headers: {}, config: {} as InternalAxiosRequestConfig,
      }),
    );
    expect(e).toBeInstanceOf(ApiError);
    expect(e.status).toBe(409);
    expect(e.message).toBe('Only planned visits can be updated');
  });

  it('formats FastAPI validation errors and flags network failures as offline', () => {
    const v = toApiError(
      new axios.AxiosError('x', '422', undefined, null, {
        status: 422, data: { detail: [{ loc: ['body', 'due_date'], msg: 'Field required' }] }, statusText: '', headers: {}, config: {} as InternalAxiosRequestConfig,
      }),
    );
    expect(v.message).toBe('due date: Field required');
    const n = toApiError(new axios.AxiosError('Network Error', 'ERR_NETWORK'));
    expect(n.offline).toBe(true);
  });
});

describe('authentication', () => {
  it('logs in with form data and stores both tokens', async () => {
    handler = () => ({ status: 200, data: { access_token: 'A1', refresh_token: 'R1', expires_in: 1800 } });
    await login('mentor@example.org', 'secret-password');
    expect(calls[0].headers['Content-Type']).toBe('application/x-www-form-urlencoded');
    expect(String(calls[0].data)).toContain('username=mentor%40example.org');
    expect(await tokenStore.refreshToken()).toBe('R1');
  });

  it('maps 401 at login to a friendly message', async () => {
    handler = () => ({ status: 401, data: { detail: 'Invalid email or password' } });
    await expect(login('a@b.co', 'x')).rejects.toThrow('Incorrect email or password.');
  });

  it('refreshes once on 401 and retries the request with the new token', async () => {
    await tokenStore.save({ access_token: 'OLD', refresh_token: 'R1', expires_in: 1 });
    handler = (c) => {
      if (c.url?.endsWith('/auth/refresh')) return { status: 200, data: { access_token: 'NEW', refresh_token: 'R2', expires_in: 1800 } };
      return String(c.headers.Authorization) === 'Bearer NEW' ? { status: 200, data: ['ok'] } : { status: 401, data: { detail: 'expired' } };
    };
    const [a, b] = await Promise.all([api.get('/schools/'), api.get('/school-visits/')]);
    expect(a.data).toEqual(['ok']);
    expect(b.data).toEqual(['ok']);
    expect(calls.filter((c) => c.url?.endsWith('/auth/refresh'))).toHaveLength(1); // single-flight
    expect(await tokenStore.refreshToken()).toBe('R2');
  });
});

describe('offline queueing', () => {
  const op = {
    entity_type: 'mentor_task' as const, entity_id: 'id-1', operation_type: 'create' as const,
    payload: { title: 'Task' }, client_version: 1, label: 'Create task',
  };

  it('queues the operation when the server is unreachable', async () => {
    handler = () => 'network';
    const result = await runOrQueue(() => api.post('/mentor-tasks/', {}).then((r) => r.data), op);
    expect(isQueued(result)).toBe(true);
    expect(useOutbox.getState().items).toHaveLength(1);
    expect(JSON.parse(mem['marg.outbox.v1'])).toHaveLength(1); // persisted
  });

  it('does not queue business-rule errors', async () => {
    handler = () => ({ status: 409, data: { detail: 'Invalid transition' } });
    await expect(runOrQueue(() => api.post('/x', {}).then((r) => r.data), op)).rejects.toThrow('Invalid transition');
    expect(useOutbox.getState().items).toHaveLength(0);
  });

  it('flush removes synced operations and keeps conflicts/failures with reasons', async () => {
    await tokenStore.save({ access_token: 'A', refresh_token: 'R', expires_in: 1 });
    const a = await useOutbox.getState().enqueue({ ...op, entity_id: 'a', label: 'a' });
    const b = await useOutbox.getState().enqueue({ ...op, entity_id: 'b', label: 'b', operation_type: 'update', client_version: 1 });
    const c = await useOutbox.getState().enqueue({ ...op, entity_id: 'c', label: 'c' });
    handler = (cfg) => {
      const body = JSON.parse(String(cfg.data));
      expect(body.operations.map((o: { entity_id: string }) => o.entity_id)).toEqual(['a', 'b', 'c']); // order kept
      return {
        status: 200,
        data: {
          accepted: 3, already_received: 0, synced: 1, conflicts: 1, failed: 1,
          operations: [
            { idempotency_key: a.idempotency_key, status: 'synced', server_version: 1 },
            { idempotency_key: b.idempotency_key, status: 'conflict', server_version: 3, error_message: 'Record changed on the server' },
            { idempotency_key: c.idempotency_key, status: 'failed', server_version: null, error_message: 'Invalid payload' },
          ],
        },
      };
    };
    const totals = await useOutbox.getState().flush();
    expect(totals).toEqual({ synced: 1, conflicts: 1, failed: 1 });
    const items = useOutbox.getState().items;
    expect(items.map((i) => [i.entity_id, i.state])).toEqual([['b', 'conflict'], ['c', 'failed']]);
    expect(items[0].server_version).toBe(3);

    // Retrying a conflict is an explicit decision to apply on top of the server version.
    handler = (cfg) => {
      const o = JSON.parse(String(cfg.data)).operations[0];
      expect(o.client_version).toBe(3);
      return { status: 200, data: { accepted: 1, already_received: 0, synced: 1, conflicts: 0, failed: 0, operations: [{ idempotency_key: o.idempotency_key, status: 'synced' }] } };
    };
    await useOutbox.getState().retry(items[0].idempotency_key);
    expect(useOutbox.getState().items.map((i) => i.entity_id)).toEqual(['c']);
  });
});
