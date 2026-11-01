/**
 * React Query client with an offline cache.
 *
 * - Successful query results are persisted (throttled) so screens show the
 *   last known data when the device is offline.
 * - `offlineFirst` network mode: cached data is served without the network.
 * - `runOrQueue` performs a write online, or queues it in the outbox when the
 *   device cannot reach the server.
 */
import { dehydrate, hydrate, QueryClient } from '@tanstack/react-query';

import { ApiError, toApiError } from '@/lib/api/client';
import { useOutbox, type OutboxItem } from '@/lib/offline/outbox';
import { kv } from '@/lib/storage';

const CACHE_KEY = 'marg.query-cache.v1';
const CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      networkMode: 'offlineFirst',
      staleTime: 30_000,
      gcTime: CACHE_MAX_AGE_MS,
      retry: (count, error) => {
        const e = error as ApiError;
        if (e?.status && e.status >= 400 && e.status < 500) return false;
        return count < 2;
      },
    },
    mutations: { networkMode: 'always' },
  },
});

let saveTimer: ReturnType<typeof setTimeout> | null = null;

export async function restoreQueryCache(): Promise<void> {
  const raw = await kv.get(CACHE_KEY);
  if (raw) {
    try {
      const { savedAt, state } = JSON.parse(raw);
      if (Date.now() - savedAt < CACHE_MAX_AGE_MS) hydrate(queryClient, state);
    } catch {
      // A corrupt cache is not fatal.
    }
  }
  queryClient.getQueryCache().subscribe(() => {
    if (saveTimer) return;
    saveTimer = setTimeout(() => {
      saveTimer = null;
      const state = dehydrate(queryClient, {
        // Only persist successful data; AI-assistant results are not cached.
        shouldDehydrateQuery: (q) => q.state.status === 'success' && q.queryKey[0] !== 'mentor-ai',
      });
      void kv.set(CACHE_KEY, JSON.stringify({ savedAt: Date.now(), state }));
    }, 2000);
  });
}

export async function clearQueryCache(): Promise<void> {
  queryClient.clear();
  await kv.remove(CACHE_KEY);
}

export type QueuedResult = { queued: true; item: OutboxItem };

/**
 * Run an online write; if the server is unreachable, queue the equivalent
 * offline operation instead. Business/validation errors are NOT queued.
 */
export async function runOrQueue<R>(
  online: () => Promise<R>,
  offline: Omit<OutboxItem, 'idempotency_key' | 'queued_at' | 'state'>,
): Promise<R | QueuedResult> {
  try {
    return await online();
  } catch (e) {
    const err = toApiError(e);
    if (err.offline) {
      const item = await useOutbox.getState().enqueue(offline);
      return { queued: true, item };
    }
    throw err;
  }
}

export function isQueued(result: unknown): result is QueuedResult {
  return typeof result === 'object' && result !== null && (result as QueuedResult).queued === true;
}
