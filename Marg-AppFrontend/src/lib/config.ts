import { Platform } from 'react-native';

/**
 * Backend base URL. Configure with EXPO_PUBLIC_API_URL (see .env.example).
 * Only the MARG backend is ever called from the app: AI services and their
 * keys stay behind the backend.
 */
function defaultApiUrl(): string {
  // Android emulators reach the host machine via 10.0.2.2.
  if (Platform.OS === 'android') return 'http://10.0.2.2:8000/api/v1';
  return 'http://localhost:8000/api/v1';
}

export const API_URL = (process.env.EXPO_PUBLIC_API_URL || defaultApiUrl()).replace(/\/+$/, '');

/** Long-running AI calls (local LLM / Claude) need generous timeouts. */
export const API_TIMEOUT_MS = 30_000;
export const AI_TIMEOUT_MS = 240_000;
