/**
 * Offline outbox.
 *
 * Field operations that fail because the device is offline are stored here
 * (persisted) and pushed to POST /sync/push when connectivity returns. The
 * backend applies them with the same business rules as the online API and
 * reports a per-operation outcome:
 *   synced   -> removed from the outbox
 *   conflict -> kept; the record changed on the server (never overwritten)
 *   failed   -> kept with the server's reason (e.g. invalid transition)
 * The mentor can retry or discard kept operations from the Sync screen.
 */
import * as Network from 'expo-network';
import { create } from 'zustand';

import { toApiError } from '@/lib/api/client';
import type { SyncOperationCreate } from '@/lib/api/generated';
import { syncApi } from '@/lib/api/services';
import { uuid4 } from '@/lib/ids';
import { kv } from '@/lib/storage';

const OUTBOX_KEY = 'marg.outbox.v1';
const DEVICE_KEY = 'marg.device_id';

export type EntityType = SyncOperationCreate['entity_type'];

export interface OutboxItem {
  idempotency_key: string;
  entity_type: EntityType;
  entity_id: string;
  operation_type: 'create' | 'update' | 'delete';
  payload: Record<string, unknown>;
  client_version: number;
  /** Human-readable description for the Sync screen. */
  label: string;
  queued_at: string;
  state: 'pending' | 'conflict' | 'failed';
  error?: string | null;
  server_version?: number | null;
}

interface OutboxState {
  items: OutboxItem[];
  syncing: boolean;
  lastSyncAt: string | null;
  lastError: string | null;
  loaded: boolean;
  load: () => Promise<void>;
  enqueue: (item: Omit<OutboxItem, 'idempotency_key' | 'queued_at' | 'state'>) => Promise<OutboxItem>;
  flush: () => Promise<{ synced: number; conflicts: number; failed: number } | null>;
  retry: (key: string) => Promise<void>;
  discard: (key: string) => Promise<void>;
}

let deviceId: string | null = null;
async function getDeviceId(): Promise<string> {
  if (deviceId) return deviceId;
  deviceId = (await kv.get(DEVICE_KEY)) ?? uuid4();
  await kv.set(DEVICE_KEY, deviceId);
  return deviceId;
}

const persist = (items: OutboxItem[]) => kv.set(OUTBOX_KEY, JSON.stringify(items));

/** Listeners notified after a successful sync (used to refresh queries). */
const syncedListeners = new Set<() => void>();
export function onOutboxSynced(fn: () => void) {
  syncedListeners.add(fn);
  return () => syncedListeners.delete(fn);
}

export const useOutbox = create<OutboxState>((set, get) => ({
  items: [],
  syncing: false,
  lastSyncAt: null,
  lastError: null,
  loaded: false,

  load: async () => {
    const raw = await kv.get(OUTBOX_KEY);
    set({ items: raw ? (JSON.parse(raw) as OutboxItem[]) : [], loaded: true });
  },

  enqueue: async (partial) => {
    const item: OutboxItem = {
      ...partial,
      idempotency_key: uuid4(),
      queued_at: new Date().toISOString(),
      state: 'pending',
    };
    const items = [...get().items, item];
    set({ items });
    await persist(items);
    return item;
  },

  flush: async () => {
    const { syncing, items } = get();
    const pending = items.filter((i) => i.state === 'pending');
    if (syncing || pending.length === 0) return null;
    set({ syncing: true, lastError: null });
    const device_id = await getDeviceId();
    const totals = { synced: 0, conflicts: 0, failed: 0 };
    try {
      // Operations are applied in order; batches keep requests small.
      for (let i = 0; i < pending.length; i += 50) {
        const batch = pending.slice(i, i + 50);
        const res = await syncApi.push({
          operations: batch.map((op) => ({
            idempotency_key: op.idempotency_key,
            device_id,
            entity_type: op.entity_type,
            entity_id: op.entity_id,
            operation_type: op.operation_type,
            payload: op.payload,
            client_version: op.client_version,
          })),
        });
        const outcome = new Map(res.operations.map((o) => [o.idempotency_key, o]));
        const next = get()
          .items.map((item) => {
            const o = outcome.get(item.idempotency_key);
            if (!o) return item;
            if (o.status === 'synced') return null;
            return {
              ...item,
              state: o.status === 'conflict' ? 'conflict' : 'failed',
              error: o.error_message,
              server_version: o.server_version,
            } as OutboxItem;
          })
          .filter((x): x is OutboxItem => x !== null);
        set({ items: next });
        await persist(next);
        totals.synced += res.synced ?? 0;
        totals.conflicts += res.conflicts ?? 0;
        totals.failed += res.failed ?? 0;
      }
      set({ lastSyncAt: new Date().toISOString() });
      if (totals.synced) syncedListeners.forEach((fn) => fn());
      return totals;
    } catch (e) {
      set({ lastError: toApiError(e).message });
      return null;
    } finally {
      set({ syncing: false });
    }
  },

  retry: async (key) => {
    // For a conflict, retrying is the mentor's explicit decision to apply their
    // change on top of the newer server version they have now been shown.
    const items = get().items.map((i) =>
      i.idempotency_key === key
        ? {
            ...i,
            state: 'pending' as const,
            error: null,
            idempotency_key: uuid4(),
            client_version: i.state === 'conflict' && i.server_version ? i.server_version : i.client_version,
          }
        : i,
    );
    set({ items });
    await persist(items);
    await get().flush();
  },

  discard: async (key) => {
    const items = get().items.filter((i) => i.idempotency_key !== key);
    set({ items });
    await persist(items);
  },
}));

/** Start automatic flushing when connectivity is (re)gained. Returns a cleanup. */
export function startOutboxAutoSync(): () => void {
  const sub = Network.addNetworkStateListener((state) => {
    if (state.isConnected && state.isInternetReachable !== false) void useOutbox.getState().flush();
  });
  const timer = setInterval(() => void useOutbox.getState().flush(), 60_000);
  void useOutbox.getState().flush();
  return () => {
    sub.remove();
    clearInterval(timer);
  };
}
