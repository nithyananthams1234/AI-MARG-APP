import { create } from 'zustand';

import { login as apiLogin, logout as apiLogout, setSessionExpiredHandler, tokenStore } from '@/lib/api/client';
import type { CurrentUserResponse } from '@/lib/api/generated';
import { authApi } from '@/lib/api/services';
import { kv } from '@/lib/storage';

type Status = 'loading' | 'signed_out' | 'signed_in';

const PROFILE_KEY = 'marg.profile';

interface AuthState {
  status: Status;
  user: CurrentUserResponse | null;
  bootstrap: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

export const useAuth = create<AuthState>((set, get) => ({
  status: 'loading',
  user: null,

  bootstrap: async () => {
    const { access, refresh } = await tokenStore.load();
    if (!access && !refresh) {
      set({ status: 'signed_out', user: null });
      return;
    }
    // Show the cached profile immediately (works offline), then refresh.
    const cached = await kv.get(PROFILE_KEY);
    if (cached) set({ status: 'signed_in', user: JSON.parse(cached) });
    try {
      await get().refreshProfile();
    } catch (e) {
      const status = (e as { status?: number | null }).status;
      if (status === 401) {
        await tokenStore.clear();
        set({ status: 'signed_out', user: null });
      } else if (!cached) {
        // Offline with no cached profile: keep tokens, allow retry.
        set({ status: 'signed_out', user: null });
      }
    }
  },

  signIn: async (email, password) => {
    await apiLogin(email, password);
    await get().refreshProfile();
  },

  refreshProfile: async () => {
    const user = await authApi.me();
    await kv.set(PROFILE_KEY, JSON.stringify(user));
    set({ status: 'signed_in', user });
  },

  signOut: async () => {
    await apiLogout();
    await kv.remove(PROFILE_KEY);
    set({ status: 'signed_out', user: null });
  },
}));

setSessionExpiredHandler(() => {
  void kv.remove(PROFILE_KEY);
  useAuth.setState({ status: 'signed_out', user: null });
});
