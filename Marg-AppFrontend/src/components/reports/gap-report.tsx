/** Learning gaps per school (severity breakdown) with drill-down selection. */
import { Fragment, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { EmptyState, QueryView } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useGapReport } from '@/hooks/api';
import type { LearningGapReportItem } from '@/lib/api/generated';

import { pageStyles } from './page-chrome';

const SEVERITIES = [
  { key: 'critical_severity', label: 'Critical', color: '#B23B3B' },
  { key: 'high_severity', label: 'High', color: '#D58A32' },
  { key: 'medium_severity', label: 'Medium', color: '#2878C8' },
  { key: 'low_severity', label: 'Low', color: '#A0AEC0' },
] as const;

function SeverityBar({ item }: { item: LearningGapReportItem }) {
  const total = Math.max(1, SEVERITIES.reduce((n, s) => n + (item[s.key] ?? 0), 0));
  return (
    <View style={styles.stack}>
      {SEVERITIES.map((s) => {
        const v = item[s.key] ?? 0;
        return v > 0 ? <View key={s.key} style={{ flex: v / total, backgroundColor: s.color }} /> : null;
      })}
    </View>
  );
}

export function GapReport({
  selectedId,
  onSelect,
  renderSelected,
}: {
  selectedId?: string;
  onSelect: (id: string) => void;
  renderSelected?: (schoolId: string) => ReactNode;
}) {
  const query = useGapReport();
  return (
    <QueryView query={query} loadingLabel="Loading learning gaps…">
      {(items) =>
        items.length === 0 ? (
          <EmptyState title="No schools to report" message="Learning gaps recorded for your assigned schools will appear here." />
        ) : (
          <View style={{ gap: 10 }}>
            <View style={[pageStyles.chipRow, { marginBottom: 2 }]}>
              {SEVERITIES.map((s) => (
                <View key={s.key} style={styles.legend}>
                  <View style={[styles.swatch, { backgroundColor: s.color }]} />
                  <Text style={pageStyles.muted}>{s.label}</Text>
                </View>
              ))}
            </View>
            {items.map((item) => {
              const selected = item.school_id === selectedId;
              const open = item.total_learning_gaps - (item.resolved ?? 0);
              return (
                <Fragment key={item.school_id}>
                <Pressable
                  onPress={() => onSelect(item.school_id)}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  accessibilityLabel={`${item.school_name}: ${item.total_learning_gaps} learning gaps, ${item.critical_severity ?? 0} critical, ${item.high_severity} high, ${item.medium_severity} medium, ${item.low_severity} low, ${item.resolved ?? 0} resolved. Show school report.`}
                  style={[styles.card, selected && styles.cardSelected]}
                >
                  <View style={pageStyles.rowBetween}>
                    <Text style={[pageStyles.itemTitle, { flex: 1 }]} numberOfLines={2}>
                      {item.school_name}
                    </Text>
                    <Text style={styles.total}>{item.total_learning_gaps}</Text>
                  </View>
                  {item.total_learning_gaps > 0 ? <SeverityBar item={item} /> : null}
                  <Text style={pageStyles.muted}>
                    {SEVERITIES.map((s) => `${s.label} ${item[s.key] ?? 0}`).join(' · ')}
                  </Text>
                  <Text style={pageStyles.muted}>
                    {item.resolved ?? 0} resolved · {Math.max(0, open)} not yet resolved
                  </Text>
                  <Text style={styles.link}>{selected ? 'Hide school report ▴' : 'View school report ▾'}</Text>
                </Pressable>
                {selected && renderSelected ? renderSelected(item.school_id) : null}
                </Fragment>
              );
            })}
          </View>
        )
      }
    </QueryView>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: C.surface, borderRadius: 16, borderWidth: 1, borderColor: C.border, padding: 14, gap: 6 },
  cardSelected: { borderColor: C.teal },
  stack: { flexDirection: 'row', height: 10, borderRadius: 5, overflow: 'hidden', backgroundColor: '#EEF1F5', marginVertical: 4 },
  total: { color: C.navy, fontSize: 22, fontWeight: '800' },
  legend: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  swatch: { width: 10, height: 10, borderRadius: 3 },
  link: { color: C.tealDark, fontSize: 13, fontWeight: '700', marginTop: 2 },
});
