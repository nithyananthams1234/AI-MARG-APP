/**
 * Persistent key-value storage (native): SQLite-backed kv-store.
 * Used for the offline outbox and the cached query data.
 */
type SQLiteKeyValueStore = typeof import('expo-sqlite/kv-store').default;

let storePromise: Promise<SQLiteKeyValueStore> | undefined;

function getStore(): Promise<SQLiteKeyValueStore> {
  if (!storePromise) {
    storePromise = import('expo-sqlite/kv-store')
      .then((module) => module.default)
      .catch((error: unknown) => {
        storePromise = undefined;
        throw error;
      });
  }
  return storePromise;
}

export const kv = {
  get: async (key: string) => (await getStore()).getItem(key),
  set: async (key: string, value: string) => (await getStore()).setItem(key, value),
  remove: async (key: string) => (await getStore()).removeItem(key),
};
