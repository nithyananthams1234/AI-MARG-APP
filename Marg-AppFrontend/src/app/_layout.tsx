import { QueryClientProvider } from '@tanstack/react-query';
import { Stack, usePathname, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';

import BottomNavigation from '@/components/bottom-navigation';
import SyncBanner from '@/components/sync-banner';
import { MargColors } from '@/constants/theme';
import { onOutboxSynced, startOutboxAutoSync, useOutbox } from '@/lib/offline/outbox';
import { queryClient, restoreQueryCache } from '@/lib/query';
import { useAuth } from '@/stores/auth';

export default function RootLayout() {
  const status = useAuth((s) => s.status);
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [startupError, setStartupError] = useState<unknown>(null);
  const [startupAttempt, setStartupAttempt] = useState(0);

  // Restore offline cache + outbox, then the session.
  useEffect(() => {
    let active = true;
    const initialize = async () => {
      try {
        await Promise.all([restoreQueryCache(), useOutbox.getState().load()]);
        await useAuth.getState().bootstrap();
        if (active) {
          setStartupError(null);
          setReady(true);
        }
      } catch (error) {
        if (active) setStartupError(error);
      }
    };
    void initialize();
    return () => {
      active = false;
    };
  }, [startupAttempt]);

  // Sync queued offline changes while signed in; refresh data after a sync.
  useEffect(() => {
    if (status !== 'signed_in') return;
    const stop = startOutboxAutoSync();
    const unsubscribe = onOutboxSynced(() => void queryClient.invalidateQueries());
    return () => {
      stop();
      unsubscribe();
    };
  }, [status]);

  // Route guard: only the login screen is public.
  const onLogin = pathname === '/';
  useEffect(() => {
    if (!ready || status === 'loading') return;
    if (status === 'signed_out' && !onLogin) router.replace('/');
    if (status === 'signed_in' && onLogin) router.replace('/dashboard');
  }, [ready, status, onLogin, router]);

  const signedIn = status === 'signed_in';

  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider>
        <StatusBar style="dark" />
        <View style={styles.container}>
          {startupError ? (
            <SafeAreaView style={styles.startupError}>
              <Text style={styles.startupErrorTitle}>Could not initialize the app</Text>
              <Text style={styles.startupErrorMessage}>
                {startupError instanceof Error ? startupError.message : 'Persistent local storage or session startup failed.'}
              </Text>
              <Text style={styles.startupErrorHint}>
                Offline data is kept in SQLite. Use an SDK-compatible development build and retry; no in-memory storage fallback was used.
              </Text>
              <Pressable
                onPress={() => {
                  setReady(false);
                  setStartupError(null);
                  setStartupAttempt((attempt) => attempt + 1);
                }}
                accessibilityRole="button"
                style={styles.retryButton}
              >
                <Text style={styles.retryButtonText}>Retry startup</Text>
              </Pressable>
            </SafeAreaView>
          ) : !ready || status === 'loading' ? (
            <View style={styles.splash}>
              <ActivityIndicator color={MargColors.teal} size="large" />
            </View>
          ) : (
            <>
              {signedIn && !onLogin ? <SyncBanner /> : null}
              <Stack
                screenOptions={{
                  headerShown: false,
                  animation: 'fade',
                  contentStyle: { backgroundColor: MargColors.background },
                }}
              />
              {signedIn && !onLogin ? (
                <SafeAreaView edges={['bottom']} style={styles.bottomSafeArea}>
                  <BottomNavigation />
                </SafeAreaView>
              ) : null}
            </>
          )}
        </View>
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: MargColors.background },
  splash: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  startupError: { flex: 1, justifyContent: 'center', padding: 24, gap: 12, backgroundColor: MargColors.background },
  startupErrorTitle: { color: MargColors.navy, fontSize: 22, fontWeight: '800' },
  startupErrorMessage: { color: MargColors.danger, fontSize: 14 },
  startupErrorHint: { color: MargColors.secondaryText, fontSize: 14, lineHeight: 20 },
  retryButton: { alignSelf: 'flex-start', borderRadius: 12, backgroundColor: MargColors.teal, paddingVertical: 12, paddingHorizontal: 18 },
  retryButtonText: { color: '#FFFFFF', fontSize: 15, fontWeight: '700' },
  bottomSafeArea: { backgroundColor: MargColors.surface },
});
