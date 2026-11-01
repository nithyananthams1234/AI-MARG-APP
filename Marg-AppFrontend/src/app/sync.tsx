import { useNetworkState } from 'expo-network';
import { useRouter } from 'expo-router';
import { Alert, Platform, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Button, Card, EmptyState, InlineNotice, ScreenHeader, StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { formatDateTime, relativeTime } from '@/lib/format';
import { useOutbox, type OutboxItem } from '@/lib/offline/outbox';

function confirm(title: string, message: string, onOk: () => void) {
  if (Platform.OS === 'web') {
    if (window.confirm(`${title}\n\n${message}`)) onOk();
    return;
  }
  Alert.alert(title, message, [
    { text: 'Cancel', style: 'cancel' },
    { text: 'Confirm', style: 'destructive', onPress: onOk },
  ]);
}

function Item({ item }: { item: OutboxItem }) {
  const retry = useOutbox((s) => s.retry);
  const discard = useOutbox((s) => s.discard);

  return (
    <Card>
      <View style={styles.row}>
        <Text style={styles.label}>{item.label}</Text>
        <StatusBadge status={item.state === 'failed' ? 'rejected' : item.state === 'conflict' ? 'needs_revision' : 'pending'} label={item.state === 'pending' ? 'Waiting' : item.state === 'conflict' ? 'Conflict' : 'Not applied'} />
      </View>
      <Text style={styles.meta}>Saved {formatDateTime(item.queued_at)} on this device</Text>
      {item.error ? <InlineNotice tone={item.state === 'conflict' ? 'warning' : 'danger'} text={item.error} /> : null}
      {item.state === 'conflict' ? (
        <Text style={styles.help}>
          This record was changed elsewhere after you went offline. Your change was not applied, so nothing was overwritten.
          Open the record to review the latest version, then discard your change or apply it on top.
        </Text>
      ) : null}
      {item.state !== 'pending' ? (
        <View style={styles.actions}>
          <Button
            label={item.state === 'conflict' ? 'Apply my change anyway' : 'Retry'}
            variant="secondary"
            onPress={() =>
              item.state === 'conflict'
                ? confirm('Apply your change?', 'Your offline change will be applied on top of the newer server version.', () => void retry(item.idempotency_key))
                : void retry(item.idempotency_key)
            }
            style={{ flex: 1 }}
          />
          <Button
            label="Discard"
            variant="danger"
            onPress={() => confirm('Discard this change?', 'The change saved on this device will be removed.', () => void discard(item.idempotency_key))}
            style={{ flex: 1 }}
          />
        </View>
      ) : null}
    </Card>
  );
}

export default function SyncScreen() {
  const router = useRouter();
  const network = useNetworkState();
  const { items, syncing, lastSyncAt, lastError, flush } = useOutbox();
  const offline = network.isConnected === false || network.isInternetReachable === false;
  const pending = items.filter((i) => i.state === 'pending').length;

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <ScreenHeader
        title="Offline sync"
        subtitle={lastSyncAt ? `Last synced ${relativeTime(lastSyncAt)}` : 'Changes made offline are saved here until they reach the server.'}
        right={<Button label="Back" variant="ghost" onPress={() => (router.canGoBack() ? router.back() : router.replace('/dashboard'))} />}
      />
      {offline ? <InlineNotice tone="warning" text="You are offline. Changes will sync automatically when you reconnect." /> : null}
      {lastError ? <InlineNotice tone="danger" text={`Last sync attempt failed: ${lastError}`} /> : null}
      <Button
        label={syncing ? 'Syncing…' : pending ? `Sync ${pending} change(s) now` : 'Nothing waiting to sync'}
        onPress={() => void flush()}
        loading={syncing}
        disabled={offline || pending === 0}
        style={{ marginBottom: 16 }}
      />
      {items.length === 0 ? (
        <EmptyState title="All changes are synced" message="Visits, observations, tasks and follow-up updates you make offline will appear here until they are saved to the server." />
      ) : (
        items.map((item) => <Item key={item.idempotency_key} item={item} />)
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, paddingBottom: 40, maxWidth: 800, width: '100%', alignSelf: 'center' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 6 },
  label: { color: C.navy, fontSize: 15, fontWeight: '700', flex: 1 },
  meta: { color: C.secondaryText, fontSize: 13, marginBottom: 8 },
  help: { color: C.secondaryText, fontSize: 13, lineHeight: 19, marginBottom: 10 },
  actions: { flexDirection: 'row', gap: 10 },
});
