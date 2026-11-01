/** Daily activity (visits, observations, tasks) as simple View-based bars. */
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Card, EmptyState, QueryView } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useActivity } from '@/hooks/api';
import type { ActivityDay } from '@/lib/api/generated';
import { formatDate } from '@/lib/format';

import { pageStyles } from './page-chrome';

const SERIES = [
  { key: 'visits_completed', label: 'Visits completed', color: '#13A89E' },
  { key: 'observations_recorded', label: 'Observations', color: '#2878C8' },
  { key: 'tasks_completed', label: 'Tasks completed', color: '#D58A32' },
] as const;

function dayLabel(day: string, many: boolean) {
  const d = new Date(`${day}T00:00:00`);
  if (Number.isNaN(d.getTime())) return day;
  return many ? `${d.getDate()}` : d.toLocaleDateString('en-IN', { weekday: 'short' });
}

function Columns({ days }: { days: ActivityDay[] }) {
  const max = Math.max(1, ...days.flatMap((d) => SERIES.map((s) => d[s.key])));
  const many = days.length > 10;
  return (
    <View style={styles.chart}>
      {days.map((d) => (
        <View
          key={d.day}
          style={styles.col}
          accessible
          accessibilityLabel={`${formatDate(d.day)}: ${d.visits_completed} visits, ${d.observations_recorded} observations, ${d.tasks_completed} tasks`}
        >
          <View style={styles.barGroup}>
            {SERIES.map((s) => (
              <View
                key={s.key}
                style={[styles.bar, { height: `${(d[s.key] / max) * 100}%`, backgroundColor: s.color, minHeight: d[s.key] > 0 ? 3 : 0 }]}
              />
            ))}
          </View>
          <Text style={styles.colLabel} numberOfLines={1}>
            {dayLabel(d.day, many)}
          </Text>
        </View>
      ))}
    </View>
  );
}

export function ActivitySection({ days, onChangeDays }: { days: 7 | 30; onChangeDays: (d: 7 | 30) => void }) {
  const query = useActivity(days);
  return (
    <Card>
      <View style={pageStyles.rowBetween}>
        <Text style={pageStyles.itemTitle}>Activity</Text>
        <View style={pageStyles.chipRow} accessibilityRole="tablist">
          {([7, 30] as const).map((d) => (
            <Pressable
              key={d}
              onPress={() => onChangeDays(d)}
              accessibilityRole="tab"
              accessibilityState={{ selected: days === d }}
              style={[pageStyles.chip, days === d && pageStyles.chipActive]}
            >
              <Text style={[pageStyles.chipText, days === d && pageStyles.chipTextActive]}>{d} days</Text>
            </Pressable>
          ))}
        </View>
      </View>
      <QueryView query={query} loadingLabel="Loading activity…">
        {(data) => {
          const totals = SERIES.map((s) => ({ ...s, total: data.days.reduce((n, d) => n + d[s.key], 0) }));
          const any = totals.some((t) => t.total > 0);
          return (
            <View>
              <Text style={[pageStyles.muted, { marginTop: 6 }]}>
                {formatDate(data.start_date)} – {formatDate(data.end_date)}
              </Text>
              <View style={styles.totals}>
                {totals.map((t) => (
                  <View key={t.key} style={styles.total}>
                    <View style={[styles.swatch, { backgroundColor: t.color }]} />
                    <Text style={styles.totalValue}>{t.total}</Text>
                    <Text style={pageStyles.muted}>{t.label}</Text>
                  </View>
                ))}
              </View>
              {any ? (
                <Columns days={data.days} />
              ) : (
                <EmptyState title="No recorded activity" message="Completed visits, observations and tasks in this period will appear here." />
              )}
            </View>
          );
        }}
      </QueryView>
    </Card>
  );
}

const styles = StyleSheet.create({
  totals: { flexDirection: 'row', flexWrap: 'wrap', gap: 16, marginVertical: 12 },
  total: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  swatch: { width: 10, height: 10, borderRadius: 3 },
  totalValue: { color: C.navy, fontSize: 18, fontWeight: '800' },
  chart: { flexDirection: 'row', alignItems: 'flex-end', height: 150, gap: 3, paddingTop: 8 },
  col: { flex: 1, alignItems: 'center', height: '100%' },
  barGroup: { flex: 1, width: '100%', flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'center', gap: 1 },
  bar: { flex: 1, maxWidth: 10, borderTopLeftRadius: 3, borderTopRightRadius: 3 },
  colLabel: { color: C.secondaryText, fontSize: 10, marginTop: 4 },
});
