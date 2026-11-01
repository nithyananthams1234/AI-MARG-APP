import Constants from 'expo-constants';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PageHeader, SectionTitle, pageStyles } from '@/components/reports/page-chrome';
import { Button, Card, EmptyState, InlineNotice, StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useCoachStatus, useMentorAiStatus } from '@/hooks/api';
import { API_URL } from '@/lib/config';
import { confirmAction } from '@/lib/dialogs';
import { formatDateTime, humanize, relativeTime } from '@/lib/format';
import { useOutbox } from '@/lib/offline/outbox';
import { clearQueryCache } from '@/lib/query';
import { useAuth } from '@/stores/auth';

function initials(name?: string) {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow} accessible accessibilityLabel={`${label}: ${value}`}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue} selectable>
        {value}
      </Text>
    </View>
  );
}

function ServiceRow({
  name,
  query,
  detail,
}: {
  name: string;
  query: { data?: { available: boolean }; isLoading: boolean; error: unknown; refetch: () => unknown };
  detail?: string;
}) {
  let status: { key: string; label: string };
  if (query.isLoading && !query.data) status = { key: 'pending', label: 'Checking…' };
  else if (!query.data) status = { key: 'rejected', label: 'Unknown' };
  else status = query.data.available ? { key: 'completed', label: 'Available' } : { key: 'rejected', label: 'Unavailable' };
  return (
    <View style={styles.serviceRow}>
      <View style={{ flex: 1 }}>
        <Text style={pageStyles.itemTitle}>{name}</Text>
        {detail ? <Text style={pageStyles.muted}>{detail}</Text> : null}
        {!query.data && query.error ? (
          <Text style={pageStyles.muted}>{query.error instanceof Error ? query.error.message : 'Could not check status.'}</Text>
        ) : null}
      </View>
      <StatusBadge status={status.key} label={status.label} />
    </View>
  );
}

export default function ProfileScreen() {
  const router = useRouter();
  const user = useAuth((s) => s.user);
  const signOut = useAuth((s) => s.signOut);
  const refreshProfile = useAuth((s) => s.refreshProfile);
  const items = useOutbox((s) => s.items);
  const lastSyncAt = useOutbox((s) => s.lastSyncAt);
  const syncing = useOutbox((s) => s.syncing);
  const coach = useCoachStatus();
  const mentorAi = useMentorAiStatus();
  const [signingOut, setSigningOut] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const pending = items.filter((i) => i.state === 'pending').length;
  const needsAttention = items.length - pending;

  const refresh = async () => {
    setRefreshing(true);
    setRefreshError(null);
    try {
      await Promise.all([refreshProfile(), coach.refetch(), mentorAi.refetch()]);
    } catch (e) {
      setRefreshError(e instanceof Error ? e.message : 'Could not refresh your profile.');
    } finally {
      setRefreshing(false);
    }
  };

  const doSignOut = () =>
    confirmAction(
      'Sign out?',
      items.length > 0
        ? `${items.length} change(s) saved on this device have not reached the server yet and will stay on this device.`
        : 'You will need to sign in again to use the app.',
      () => {
        setSigningOut(true);
        void (async () => {
          try {
            await signOut();
            await clearQueryCache();
          } finally {
            setSigningOut(false);
            router.replace('/');
          }
        })();
      },
      'Sign out',
    );

  const coachDetail = coach.data?.available
    ? [coach.data.llm_model, coach.data.knowledge_chunks != null ? `${coach.data.knowledge_chunks} knowledge passages` : null]
        .filter(Boolean)
        .join(' · ')
    : 'Teaching questions answered from the MARG knowledge base';

  const appVersion = Constants.expoConfig?.version ?? 'unknown';

  return (
    <SafeAreaView style={pageStyles.safeArea} edges={['top']}>
      <ScrollView
        contentContainerStyle={pageStyles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={C.teal} />}
      >
        <PageHeader title="Profile" subtitle="Your account and app status" />

        {refreshError ? <InlineNotice tone="warning" text={refreshError} /> : null}

        {user ? (
          <Card style={styles.userCard}>
            <View style={styles.avatar} accessibilityElementsHidden>
              <Text style={styles.avatarText}>{initials(user.full_name)}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.name} accessibilityRole="header">
                {user.full_name}
              </Text>
              <Text style={pageStyles.muted}>{user.email}</Text>
              <View style={[pageStyles.chipRow, { marginTop: 8 }]}>
                {(user.roles.length ? user.roles : [user.role]).map((r) => (
                  <StatusBadge key={r} status="planned" label={humanize(r)} />
                ))}
              </View>
            </View>
          </Card>
        ) : (
          <EmptyState title="Profile not loaded" message="Pull down to refresh, or sign in again." />
        )}

        <SectionTitle title={`Assigned schools${user ? ` (${user.assigned_schools.length})` : ''}`} />
        {user && user.assigned_schools.length === 0 ? (
          <EmptyState title="No schools assigned" message="Ask your administrator to assign schools to your account." />
        ) : (
          <Card>
            {(user?.assigned_schools ?? []).map((s, i) => (
              <Pressable
                key={s.id}
                style={[styles.schoolRow, i > 0 && styles.divider]}
                onPress={() => router.push('/schools')}
                accessibilityRole="link"
                accessibilityLabel={`${s.name}, code ${s.code}${s.district ? `, ${s.district}` : ''}. Open schools.`}
              >
                <Text style={pageStyles.itemTitle}>{s.name}</Text>
                <Text style={pageStyles.muted}>
                  {s.code}
                  {s.district ? ` · ${s.district}` : ''}
                </Text>
              </Pressable>
            ))}
          </Card>
        )}

        <SectionTitle title="Offline sync" />
        <Card>
          <InfoRow label="Changes waiting to sync" value={syncing ? `${pending} (syncing now…)` : String(pending)} />
          {needsAttention > 0 ? <InfoRow label="Changes needing your review" value={String(needsAttention)} /> : null}
          <InfoRow
            label="Last successful sync"
            value={lastSyncAt ? `${formatDateTime(lastSyncAt)} (${relativeTime(lastSyncAt)})` : 'Not synced yet on this device'}
          />
          <Button label="Open sync status" variant="secondary" onPress={() => router.push('/sync')} style={{ marginTop: 12 }} />
        </Card>

        <SectionTitle title="AI services" />
        <Card>
          <ServiceRow name="Classroom Coach" query={coach} detail={coachDetail} />
          <View style={styles.divider} />
          <ServiceRow name="Mentor AI Assistant" query={mentorAi} detail="Planning, prioritisation and follow-up analysis" />
          <Text style={[pageStyles.muted, { marginTop: 10 }]}>
            Both services are reached only through the MARG server. Pull down to re-check.
          </Text>
        </Card>

        <SectionTitle title="App" />
        <Card>
          <InfoRow label="App version" value={appVersion} />
          <InfoRow label="Server" value={API_URL} />
          <Text style={[pageStyles.muted, { marginTop: 10 }]}>There are no adjustable settings in this version of the app.</Text>
        </Card>

        <Button
          label="Sign out"
          variant="danger"
          onPress={doSignOut}
          loading={signingOut}
          style={{ marginTop: 16 }}
          accessibilityLabel="Sign out of MARG"
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  userCard: { flexDirection: 'row', gap: 14, alignItems: 'center' },
  avatar: { width: 56, height: 56, borderRadius: 28, backgroundColor: C.navy, alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: '#FFF', fontSize: 20, fontWeight: '800' },
  name: { color: C.navy, fontSize: 19, fontWeight: '800' },
  schoolRow: { paddingVertical: 10 },
  divider: { borderTopWidth: 1, borderTopColor: C.border },
  infoRow: { paddingVertical: 8, gap: 2 },
  infoLabel: { color: C.secondaryText, fontSize: 12, fontWeight: '600' },
  infoValue: { color: C.navy, fontSize: 15, fontWeight: '600' },
  serviceRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 },
});
