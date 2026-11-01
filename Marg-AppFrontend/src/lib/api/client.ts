/**
 * Central HTTP client for the MARG backend.
 *
 * - One axios instance; every screen goes through `api` (no scattered URLs).
 * - Attaches the access token; on 401 performs ONE shared refresh (rotation)
 *   and retries the request; if refresh fails the session is cleared.
 * - Normalises errors into ApiError with a user-presentable message.
 */
import axios, { AxiosError, isAxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios';

import { API_TIMEOUT_MS, API_URL } from '@/lib/config';
import { secureStorage } from '@/lib/secure-storage';

const ACCESS_KEY = 'marg.access_token';
const REFRESH_KEY = 'marg.refresh_token';

export interface TokenPair {
  access_token: string;
  refresh_token?: string | null;
  expires_in: number;
}

export class ApiError extends Error {
  status: number | null;
  offline: boolean;
  details: unknown;

  constructor(message: string, status: number | null, details?: unknown, offline = false) {
    super(message);
    this.status = status;
    this.details = details;
    this.offline = offline;
  }
}

let accessToken: string | null = null;
let onSessionExpired: (() => void) | null = null;

export const tokenStore = {
  async load(): Promise<{ access: string | null; refresh: string | null }> {
    const [access, refresh] = await Promise.all([secureStorage.get(ACCESS_KEY), secureStorage.get(REFRESH_KEY)]);
    accessToken = access;
    return { access, refresh };
  },
  async save(tokens: TokenPair): Promise<void> {
    accessToken = tokens.access_token;
    await secureStorage.set(ACCESS_KEY, tokens.access_token);
    if (tokens.refresh_token) await secureStorage.set(REFRESH_KEY, tokens.refresh_token);
  },
  async clear(): Promise<void> {
    accessToken = null;
    await Promise.all([secureStorage.remove(ACCESS_KEY), secureStorage.remove(REFRESH_KEY)]);
  },
  refreshToken: () => secureStorage.get(REFRESH_KEY),
  hasAccessToken: () => accessToken !== null,
};

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler;
}

export const api = axios.create({ baseURL: API_URL, timeout: API_TIMEOUT_MS });

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshInFlight: Promise<boolean> | null = null;

async function refreshSession(): Promise<boolean> {
  const refresh = await tokenStore.refreshToken();
  if (!refresh) return false;
  try {
    const { data } = await axios.post<TokenPair>(`${API_URL}/auth/refresh`, { refresh_token: refresh }, { timeout: API_TIMEOUT_MS });
    await tokenStore.save(data);
    return true;
  } catch {
    return false;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined;
    const isAuthCall = original?.url?.includes('/auth/login') || original?.url?.includes('/auth/refresh');

    if (error.response?.status === 401 && original && !original._retried && !isAuthCall) {
      original._retried = true;
      refreshInFlight ??= refreshSession().finally(() => {
        refreshInFlight = null;
      });
      if (await refreshInFlight) {
        original.headers = { ...(original.headers ?? {}), Authorization: `Bearer ${accessToken}` };
        return api(original);
      }
      await tokenStore.clear();
      onSessionExpired?.();
    }
    return Promise.reject(toApiError(error));
  },
);

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (isAxiosError(error)) {
    if (!error.response) {
      const timedOut = error.code === 'ECONNABORTED';
      return new ApiError(
        timedOut ? 'The server took too long to respond. Please try again.' : 'Cannot reach the MARG server. Check your connection.',
        null,
        undefined,
        !timedOut,
      );
    }
    const { status, data } = error.response;
    const detail = (data as { detail?: unknown })?.detail;
    let message = 'Something went wrong. Please try again.';
    if (typeof detail === 'string') message = detail;
    else if (Array.isArray(detail) && detail.length) {
      const first = detail[0] as { loc?: unknown[]; msg?: string };
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : undefined;
      message = field ? `${String(field).replace(/_/g, ' ')}: ${first.msg}` : first.msg ?? message;
    } else if (status === 403) message = 'You do not have permission to do this.';
    else if (status === 404) message = 'This record was not found or is not assigned to you.';
    else if (status >= 500) message = 'The server had a problem. Please try again shortly.';
    return new ApiError(message, status, data);
  }
  return new ApiError(error instanceof Error ? error.message : 'Unexpected error', null);
}

export async function login(email: string, password: string): Promise<TokenPair> {
  const body = new URLSearchParams({ username: email.trim(), password });
  try {
    const { data } = await api.post<TokenPair>('/auth/login', body.toString(), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    await tokenStore.save(data);
    return data;
  } catch (e) {
    const err = toApiError(e);
    if (err.status === 401) throw new ApiError('Incorrect email or password.', 401);
    if (err.status === 429) throw new ApiError('Too many attempts. Please wait a few minutes and try again.', 429);
    throw err;
  }
}

export async function logout(): Promise<void> {
  const refresh = await tokenStore.refreshToken();
  try {
    if (refresh && accessToken) await api.post('/auth/logout', { refresh_token: refresh });
  } catch {
    // Logging out locally must always succeed even if the server is unreachable.
  } finally {
    await tokenStore.clear();
  }
}
