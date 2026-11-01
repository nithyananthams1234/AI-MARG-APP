import { useRouter, type Href } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQueryClient } from '@tanstack/react-query';

import { ActivitySection } from '@/components/reports/activity-chart';
import { GapReport } from '@/components/reports/gap-report';
import { Bar, PageHeader, SectionTitle, pageStyles } from '@/components/reports/page-chrome';
import { SchoolReport } from '@/components/reports/school-report';
import { Card, QueryView } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useDashboard } from '@/hooks/api';
import type { MentorDashboardResponse } from '@/lib/api/generated';

function Tile({ label, value, detail, color, onPress }: { label: string; value: number; detail?: string; color: string; onPress?: () => void }) {
  return (
    <Pressable
      style={styles.tile}
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole={onPress ? 'button' : 'summary'}
      accessibilityLabel={`${label}: ${value}${detail ? `. ${detail}` : ''}`}
    >
      <View style={[styles.tileAccent, { backgroundColor: color }]} />
      <Text style={styles.tileValue}>{value}</Text>
      <Text style={styles.tileLabel}>{label}</Text>
      {detail ? <Text style={pageStyles.muted}>{detail}</Text> : null}
    </Pressable>
  );
}

function Progress({ label, done, total, color }: { label: string; done: number; total: number; color: string }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <View style={{ marginTop: 12, gap: 6 }}>
      <View style={pageStyles.rowBetween}>
        <Text style={styles.progressLabel}>{label}</Text>
        <Text style={styles.progressValue}>
          {done} / {total}
          {total > 0 ? ` (${pct}%)` : ''}
        </Text>
      </View>
      <Bar value={done} max={total} color={color} label={`${label}: ${done} of ${total}`} />
    </View>
  );
}

function Overview({ d, go }: { d: MentorDashboardResponse; go: (h: Href) => void }) {
  const totalTasks = d.pending_tasks + d.completed_tasks;
  return (
    <>
      <View style={styles.tiles}>
        <Tile label="Assigned schools" value={d.total_schools} color="#2878C8" onPress={() => go('/schools')} />
        <Tile label="Visits" value={d.total_visits} detail={`${d.upcoming_visits ?? 0} upcoming`} color={C.teal} onPress={() => go('/visits')} />
        <Tile label="Observations" value={d.total_observations ?? 0} color="#2462A8" onPress={() => go('/observations')} />
        <Tile label="Learning gaps" value={d.total_learning_gaps} detail={`${d.recommendations_awaiting_review ?? 0} recommendations to review`} color={C.danger} />
        <Tile label="Action plans" value={d.total_action_plans} detail={`${d.active_action_plans ?? 0} active`} color="#9465C5" onPress={() => go('/action-plans')} />
        <Tile
          label="Open follow-ups"
          value={d.open_follow_ups ?? 0}
          detail={`${d.follow_ups_awaiting_verification ?? 0} awaiting your verification`}
          color="#D58A32"
          onPress={() => go('/follow-ups')}
        />
      </View>
      <Card>
        <Text style={pageStyles.itemTitle}>Progress</Text>
        <Progress label="Visits completed" done={d.completed_visits} total={d.total_visits} color={C.teal} />
        <Progress label="Tasks completed" done={d.completed_tasks} total={totalTasks} color="#D58A32" />
        <Text style={[pageStyles.muted, { marginTop: 10 }]}>
          {d.pending_tasks} open task{d.pending_tasks === 1 ? '' : 's'}
          {d.overdue_tasks ? `, ${d.overdue_tasks} overdue` : ', none overdue'}.
        </Text>
      </Card>
    </>
  );
}

export default function ReportsScreen() {
  const router = useRouter();
  const qc = useQueryClient();
  const dashboard = useDashboard();
  const [days, setDays] = useState<7 | 30>(7);
  const [schoolId, setSchoolId] = useState<string | undefined>();
  const [refreshing, setRefreshing] = useState(false);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await qc.invalidateQueries({ queryKey: ['reports'] });
      if (schoolId) await qc.invalidateQueries({ queryKey: ['schools', schoolId, 'report'] });
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <SafeAreaView style={pageStyles.safeArea} edges={['top']}>
      <ScrollView
        contentContainerStyle={pageStyles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={C.teal} />}
      >
        <PageHeader title="Reports" subtitle="Your mentoring activity from recorded data" />

        <SectionTitle title="Overview" />
        <QueryView query={dashboard} loadingLabel="Loading overview…">
          {(d) => <Overview d={d} go={(h) => router.push(h)} />}
        </QueryView>

        <SectionTitle title="Activity" />
        <ActivitySection days={days} onChangeDays={setDays} />

        <SectionTitle title="Learning gaps by school" />
        <GapReport
          selectedId={schoolId}
          onSelect={(id) => setSchoolId((cur) => (cur === id ? undefined : id))}
          renderSelected={(id) => <SchoolReport schoolId={id} />}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  tiles: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 12 },
  tile: {
    flexGrow: 1,
    flexBasis: '30%',
    minWidth: 140,
    backgroundColor: C.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: C.border,
    padding: 14,
    overflow: 'hidden',
  },
  tileAccent: { position: 'absolute', left: 0, top: 0, bottom: 0, width: 4 },
  tileValue: { color: C.navy, fontSize: 24, fontWeight: '800' },
  tileLabel: { color: C.navy, fontSize: 13, fontWeight: '700', marginTop: 2 },
  progressLabel: { color: C.text, fontSize: 13, fontWeight: '600', flex: 1 },
  progressValue: { color: C.navy, fontSize: 13, fontWeight: '700' },
});
