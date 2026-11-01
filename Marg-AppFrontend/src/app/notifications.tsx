import { useRouter, type Href } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PageHeader, pageStyles } from '@/components/reports/page-chrome';
import { Button, EmptyState, InlineNotice, QueryView } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useMarkAllNotificationsRead, useMarkNotificationRead, useNotifications } from '@/hooks/api';
import type { NotificationResponse } from '@/lib/api/generated';
import { formatDateTime, relativeTime } from '@/lib/format';

type Category = { label: string; icon: string; color: string; bg: string };

const CATEGORIES: Record<string, Category> = {
  task_overdue: { label: 'Task overdue', icon: '!', color: '#B23B3B', bg: '#FDECEC' },
  task_due_soon: { label: 'Task due soon', icon: '✓', color: '#9A5B12', bg: '#FFF4E7' },
  visit_upcoming: { label: 'Upcoming visit', icon: '⌖', color: '#0D8982', bg: '#E8F7F5' },
  step_due_soon: { label: 'Action step due soon', icon: '☰', color: '#9A5B12', bg: '#FFF4E7' },
  step_overdue: { label: 'Action step overdue', icon: '☰', color: '#B23B3B', bg: '#FDECEC' },
  follow_up_needs_verification: { label: 'Follow-up to verify', icon: '↻', color: '#6B3FA0', bg: '#F3EDFA' },
  ai_job_completed: { label: 'AI analysis ready', icon: '✦', color: '#2462A8', bg: '#EAF3FC' },
  ai_job_failed: { label: 'AI analysis failed', icon: '✦', color: '#B23B3B', bg: '#FDECEC' },
  mentor_ai_action: { label: 'Mentor AI action', icon: '✦', color: '#203F65', bg: '#EEF1F5' },
  system: { label: 'System', icon: 'i', color: '#4A5568', bg: '#EEF1F5' },
};
const FALLBACK: Category = { label: 'Update', icon: 'i', color: '#4A5568', bg: '#EEF1F5' };

/** Where tapping a notification takes the mentor (by referenced entity). */
function targetFor(n: NotificationResponse): Href | null {
  const id = n.reference_entity_id ?? undefined;
  switch (n.reference_entity_type) {
    case 'mentor_task':
      return '/tasks';
    case 'school_visit':
      return id ? { pathname: '/visits', params: { visitId: id } } : '/visits';
    case 'observation':
      return id ? { pathname: '/observations', params: { observationId: id } } : '/observations';
    case 'follow_up':
      return '/follow-ups';
    case 'action_plan_step':
    case 'action_plan':
      return '/action-plans';
    default:
      return null;
  }
}

type Filter = 'all' | 'unread';

function NotificationRow({ n, onOpen, busy }: { n: NotificationResponse; onOpen: () => void; busy: boolean }) {
  const cat = CATEGORIES[n.notification_type] ?? FALLBACK;
  return (
    <Pressable
      onPress={onOpen}
      disabled={busy}
      accessibilityRole="button"
      accessibilityLabel={`${n.is_read ? '' : 'Unread. '}${cat.label}: ${n.title}. ${n.message}. ${relativeTime(n.created_at)}`}
      style={({ pressed }) => [styles.item, !n.is_read && styles.itemUnread, pressed && { opacity: 0.85 }]}
    >
      <View style={[styles.icon, { backgroundColor: cat.bg }]}>
        <Text style={[styles.iconText, { color: cat.color }]}>{cat.icon}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <View style={pageStyles.rowBetween}>
          <Text style={[styles.category, { color: cat.color }]}>{cat.label}</Text>
          <Text style={styles.time} accessibilityLabel={formatDateTime(n.created_at)}>
            {relativeTime(n.created_at)}
          </Text>
        </View>
        <Text style={[styles.title, !n.is_read && styles.titleUnread]}>{n.title}</Text>
        <Text style={styles.message}>{n.message}</Text>
      </View>
      {!n.is_read ? <View style={styles.dot} accessibilityElementsHidden /> : null}
    </Pressable>
  );
}

export default function NotificationsScreen() {
  const router = useRouter();
  const query = useNotifications();
  const markRead = useMarkNotificationRead();
  const markAll = useMarkAllNotificationsRead();
  const [filter, setFilter] = useState<Filter>('all');

  const unread = query.data?.unread_count ?? 0;

  const open = (n: NotificationResponse) => {
    const target = targetFor(n);
    if (!n.is_read) markRead.mutate(n.id);
    if (target) router.push(target);
  };

  const list = useMemo(
    () => (query.data?.notifications ?? []).filter((n) => filter === 'all' || !n.is_read),
    [query.data, filter],
  );

  return (
    <SafeAreaView style={pageStyles.safeArea} edges={['top']}>
      <ScrollView
        contentContainerStyle={pageStyles.content}
        refreshControl={<RefreshControl refreshing={query.isRefetching} onRefresh={() => void query.refetch()} tintColor={C.teal} />}
      >
        <PageHeader
          title="Notifications"
          subtitle={query.data ? `${unread} unread of ${query.data.total}` : 'Updates across your schools'}
          right={
            <Button
              label="Mark all read"
              variant="secondary"
              onPress={() => markAll.mutate()}
              loading={markAll.isPending}
              disabled={unread === 0}
              accessibilityLabel="Mark all notifications as read"
            />
          }
        />

        {markAll.error ? <InlineNotice tone="danger" text={markAll.error.message} /> : null}
        {markRead.error ? <InlineNotice tone="danger" text={`Could not mark as read: ${markRead.error.message}`} /> : null}

        <View style={[pageStyles.chipRow, { marginBottom: 14 }]} accessibilityRole="tablist">
          {(['all', 'unread'] as const).map((f) => (
            <Pressable
              key={f}
              onPress={() => setFilter(f)}
              accessibilityRole="tab"
              accessibilityState={{ selected: filter === f }}
              style={[pageStyles.chip, filter === f && pageStyles.chipActive]}
            >
              <Text style={[pageStyles.chipText, filter === f && pageStyles.chipTextActive]}>
                {f === 'all' ? 'All' : `Unread (${unread})`}
              </Text>
            </Pressable>
          ))}
        </View>

        <QueryView query={query} loadingLabel="Loading notifications…">
          {() =>
            list.length === 0 ? (
              <EmptyState
                title={filter === 'unread' ? 'No unread notifications' : 'No notifications yet'}
                message="Reminders about tasks, visits, follow-ups and AI analyses will appear here."
              />
            ) : (
              <View style={styles.list}>
                {list.map((n) => (
                  <NotificationRow key={n.id} n={n} onOpen={() => open(n)} busy={markRead.isPending && markRead.variables === n.id} />
                ))}
              </View>
            )
          }
        </QueryView>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  list: { gap: 10 },
  item: {
    flexDirection: 'row',
    gap: 12,
    backgroundColor: C.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: C.border,
    padding: 14,
    alignItems: 'flex-start',
  },
  itemUnread: { borderColor: '#BFE7E3', backgroundColor: '#F7FCFB' },
  icon: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  iconText: { fontSize: 17, fontWeight: '800' },
  category: { fontSize: 12, fontWeight: '700', flex: 1 },
  time: { color: C.muted, fontSize: 12 },
  title: { color: C.navy, fontSize: 15, fontWeight: '600', marginTop: 2 },
  titleUnread: { fontWeight: '800' },
  message: { color: C.secondaryText, fontSize: 13, lineHeight: 19, marginTop: 3 },
  dot: { width: 9, height: 9, borderRadius: 5, backgroundColor: C.teal, marginTop: 6 },
});
