import { useNetworkState } from 'expo-network';
import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { MargColors as C } from '@/constants/theme';
import { useOutbox } from '@/lib/offline/outbox';

/** Offline / pending-sync indicator shown at the top of every signed-in screen. */
export default function SyncBanner() {
  const router = useRouter();
  const network = useNetworkState();
  const items = useOutbox((s) => s.items);
  const syncing = useOutbox((s) => s.syncing);
  const insets = useSafeAreaInsets();

  const offline = network.isConnected === false || network.isInternetReachable === false;
  const pending = items.filter((i) => i.state === 'pending').length;
  const problems = items.length - pending;

  if (!offline && items.length === 0) return null;

  let text: string;
  let tone = styles.info;
  if (offline) {
    text = pending ? `Offline — ${pending} change(s) saved on this device, will sync automatically` : 'Offline — showing saved data';
    tone = styles.warn;
  } else if (problems) {
    text = `${problems} change(s) need your attention — tap to review`;
    tone = styles.danger;
  } else {
    text = syncing ? `Syncing ${pending} change(s)…` : `${pending} change(s) waiting to sync — tap to review`;
  }

  return (
    <Pressable onPress={() => router.push('/sync')} style={[styles.banner, tone, { paddingTop: 8 + insets.top }]} accessibilityRole="button" accessibilityLabel={text}>
      <Text style={styles.text}>{text}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  banner: { paddingVertical: 8, paddingHorizontal: 16 },
  info: { backgroundColor: '#EAF3FC' },
  warn: { backgroundColor: '#FFF4E7' },
  danger: { backgroundColor: '#FDECEC' },
  text: { color: C.navy, fontSize: 13, fontWeight: '700', textAlign: 'center' },
});
