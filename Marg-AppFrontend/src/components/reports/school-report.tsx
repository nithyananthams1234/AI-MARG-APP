/** Per-school drill-down (GET /reports/schools/{id}). */
import { StyleSheet, Text, View } from 'react-native';

import { Card, QueryView } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useSchoolReport } from '@/hooks/api';

import { Bar, pageStyles } from './page-chrome';

function Metric({ label, done, total, color }: { label: string; done: number; total: number; color: string }) {
  return (
    <View style={styles.metric}>
      <View style={pageStyles.rowBetween}>
        <Text style={styles.metricLabel}>{label}</Text>
        <Text style={styles.metricValue}>
          {done} / {total}
        </Text>
      </View>
      <Bar value={done} max={total} color={color} label={`${label}: ${done} of ${total}`} />
    </View>
  );
}

export function SchoolReport({ schoolId }: { schoolId: string }) {
  const query = useSchoolReport(schoolId);
  return (
    <Card>
      <QueryView query={query} loadingLabel="Loading school report…">
        {(r) => (
          <View>
            <Text style={pageStyles.itemTitle}>{r.school_name}</Text>
            <View style={styles.tiles}>
              {(
                [
                  ['Visits', r.total_visits],
                  ['Observations', r.total_observations],
                  ['Learning gaps', r.total_learning_gaps],
                  ['Action plans', r.total_action_plans],
                  ['Open follow-ups', r.open_follow_ups ?? 0],
                ] as const
              ).map(([label, value]) => (
                <View key={label} style={styles.tile}>
                  <Text style={styles.tileValue}>{value}</Text>
                  <Text style={pageStyles.muted}>{label}</Text>
                </View>
              ))}
            </View>
            <Metric label="Visits completed" done={r.completed_visits} total={r.total_visits} color={C.teal} />
            {r.open_learning_gaps !== undefined ? (
              <Metric
                label="Learning gaps no longer open"
                done={Math.max(0, r.total_learning_gaps - r.open_learning_gaps)}
                total={r.total_learning_gaps}
                color="#2878C8"
              />
            ) : null}
            <Metric label="Action plans completed" done={r.completed_action_plans} total={r.total_action_plans} color="#9465C5" />
          </View>
        )}
      </QueryView>
    </Card>
  );
}

const styles = StyleSheet.create({
  tiles: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginVertical: 12 },
  tile: { flexGrow: 1, flexBasis: '28%', minWidth: 100, backgroundColor: C.inputBackground, borderRadius: 12, padding: 10 },
  tileValue: { color: C.navy, fontSize: 20, fontWeight: '800' },
  metric: { marginTop: 10, gap: 6 },
  metricLabel: { color: C.text, fontSize: 13, fontWeight: '600', flex: 1 },
  metricValue: { color: C.navy, fontSize: 13, fontWeight: '700' },
});
