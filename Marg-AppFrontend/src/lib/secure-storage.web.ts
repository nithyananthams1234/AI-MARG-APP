/**
 * Credentials storage (web). SecureStore is not available on web, so tokens
 * are kept in sessionStorage: they are cleared when the browser tab closes.
 * Access tokens are short-lived and refresh tokens rotate on every use.
 */
function ss(): Storage | null {
  try {
    return typeof window !== 'undefined' ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

export const secureStorage = {
  get: async (key: string) => ss()?.getItem(key) ?? null,
  set: async (key: string, value: string) => {
    ss()?.setItem(key, value);
  },
  remove: async (key: string) => {
    ss()?.removeItem(key);
  },
};
