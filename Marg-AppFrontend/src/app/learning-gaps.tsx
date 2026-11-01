import { useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PageHeader, SectionTitle, pageStyles } from '@/components/reports/page-chrome';
import { Card, EmptyState, ErrorState, InlineNotice, LoadingState, StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import {
  useEvidence,
  useFindings,
  useGaps,
  useObservations,
  useRecommendations,
  useSchools,
  useVisits,
} from '@/hooks/api';
import type {
  LearningGapResponse,
  ObservationFindingResponse,
  ObservationResponse,
  RecommendationResponse,
  SchoolResponse,
  SchoolVisitResponse,
} from '@/lib/api/generated';
import { formatDateTime } from '@/lib/format';

interface DistributionItem {
  label: string;
  count: number;
}

interface SchoolDistribution {
  id: string;
  name: string;
  count: number;
  severities: Map<string, number>;
}

const CHART_COLORS = ['#142B4A', '#2878C8', '#13A89E', '#65B7D9', '#718096', '#8064A2'];
const SEVERITY_COLORS: Record<string, string> = {
  critical: '#B23B3B',
  high: '#D58A32',
  medium: '#2878C8',
  low: '#13A89E',
};

function distribution(gaps: LearningGapResponse[], getLabel: (gap: LearningGapResponse) => string): DistributionItem[] {
  const counts = new Map<string, number>();
  for (const gap of gaps) {
    const label = getLabel(gap).trim() || 'Not recorded';
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function ChartCard({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <Card style={styles.chartCard}>
      <Text style={styles.chartTitle}>{title}</Text>
      <Text style={styles.chartDescription}>{description}</Text>
      {children}
    </Card>
  );
}

function ChartEmpty({ message }: { message: string }) {
  return <Text style={styles.chartEmpty}>{message}</Text>;
}

function DonutChart({ items, total }: { items: DistributionItem[]; total: number }) {
  const dotCount = 48;
  const ringSize = 164;
  const center = ringSize / 2;
  const radius = 65;
  const cumulative = items.reduce<number[]>((values, item, index) => {
    values[index] = item.count + (values[index - 1] ?? 0);
    return values;
  }, []);

  return (
    <View style={styles.donutLayout}>
      <View
        style={[styles.donut, { width: ringSize, height: ringSize }]}
        accessibilityRole="image"
        accessibilityLabel={`Learning gap distribution across ${items.length} subjects. ${items.map((item) => `${item.label}: ${Math.round((item.count / total) * 100)} percent`).join(', ')}`}
      >
        {Array.from({ length: dotCount }, (_, dotIndex) => {
          const valueAtDot = (dotIndex / dotCount) * total;
          const itemIndex = cumulative.findIndex((end) => valueAtDot < end);
          const itemColorIndex = itemIndex < 0 ? items.length - 1 : itemIndex;
          const angle = (dotIndex / dotCount) * Math.PI * 2 - Math.PI / 2;
          return (
            <View
              key={dotIndex}
              style={[
                styles.donutDot,
                {
                  left: center + Math.cos(angle) * radius - 4,
                  top: center + Math.sin(angle) * radius - 4,
                  backgroundColor: CHART_COLORS[itemColorIndex % CHART_COLORS.length],
                },
              ]}
            />
          );
        })}
        <View style={styles.donutCenter}>
          <Text style={styles.donutTotal}>{total}</Text>
          <Text style={styles.donutCaption}>identified</Text>
        </View>
      </View>
      <View style={styles.legendList}>
        {items.map((item, index) => (
          <View key={item.label} style={styles.legendRow}>
            <View style={[styles.legendSwatch, { backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }]} />
            <Text style={styles.legendLabel} numberOfLines={1}>{item.label}</Text>
            <Text style={styles.legendValue}>{Math.round((item.count / total) * 100)}%</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function SchoolBarChart({ items }: { items: SchoolDistribution[] }) {
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <View style={styles.chartRows}>
      {items.map((item) => (
        <View key={item.id} style={styles.schoolBarRow} accessibilityLabel={`${item.name}: ${item.count} learning gaps`}>
          <View style={styles.schoolBarHeading}>
            <Text style={styles.schoolBarLabel} numberOfLines={1}>{item.name}</Text>
            <Text style={styles.schoolBarValue}>{item.count}</Text>
          </View>
          <View style={styles.barTrack}>
            <View style={[styles.barFill, { width: `${(item.count / max) * 100}%` }]} />
          </View>
        </View>
      ))}
    </View>
  );
}

function CategoryBarChart({ items }: { items: DistributionItem[] }) {
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <View style={styles.chartRows}>
      {items.map((item) => (
        <View key={item.label} style={styles.schoolBarRow} accessibilityLabel={`${item.label}: ${item.count} learning gaps`}>
          <View style={styles.schoolBarHeading}>
            <Text style={styles.schoolBarLabel} numberOfLines={1}>{item.label}</Text>
            <Text style={styles.schoolBarValue}>{item.count}</Text>
          </View>
          <View style={styles.barTrack}>
            <View style={[styles.barFill, { width: `${(item.count / max) * 100}%` }]} />
          </View>
        </View>
      ))}
    </View>
  );
}

function SeverityChart({ items, severities }: { items: SchoolDistribution[]; severities: string[] }) {
  return (
    <View style={styles.chartRows}>
      <View style={styles.severityLegend}>
        {severities.map((severity, index) => (
          <View key={severity} style={styles.severityLegendItem}>
            <View style={[styles.legendSwatch, { backgroundColor: SEVERITY_COLORS[severity.toLowerCase()] ?? CHART_COLORS[index % CHART_COLORS.length] }]} />
            <Text style={styles.chartLegendText}>{severity}</Text>
          </View>
        ))}
      </View>
      {items.map((item) => {
        const total = severities.reduce((sum, severity) => sum + (item.severities.get(severity) ?? 0), 0);
        return (
          <View key={item.id} style={styles.severityRow}>
            <Text style={styles.severitySchool} numberOfLines={1}>{item.name}</Text>
            <View
              style={styles.stackedTrack}
              accessibilityRole="image"
              accessibilityLabel={`${item.name}: ${severities.map((severity) => `${severity} ${item.severities.get(severity) ?? 0}`).join(', ')}`}
            >
              {severities.map((severity, index) => {
                const count = item.severities.get(severity) ?? 0;
                return count > 0 ? (
                  <View
                    key={severity}
                    style={{
                      width: `${(count / total) * 100}%`,
                      backgroundColor: SEVERITY_COLORS[severity.toLowerCase()] ?? CHART_COLORS[index % CHART_COLORS.length],
                    }}
                  />
                ) : null;
              })}
            </View>
          </View>
        );
      })}
    </View>
  );
}

function TrendChart({ items, width }: { items: DistributionItem[]; width: number }) {
  const chartHeight = 176;
  const plotTop = 22;
  const plotBottom = 134;
  const plotLeft = 32;
  const plotRight = 12;
  const plotWidth = width - plotLeft - plotRight;
  const max = Math.max(...items.map((item) => item.count), 1);
  const points = items.map((item, index) => ({
    ...item,
    x: plotLeft + (items.length === 1 ? plotWidth / 2 : (index / (items.length - 1)) * plotWidth),
    y: plotBottom - (item.count / max) * (plotBottom - plotTop),
  }));

  return (
    <View style={{ width, height: chartHeight }} accessibilityRole="image" accessibilityLabel={`Monthly learning gaps recorded: ${items.map((item) => `${item.label}: ${item.count}`).join(', ')}`}>
      {[0, 0.5, 1].map((fraction) => {
        const y = plotBottom - fraction * (plotBottom - plotTop);
        return (
          <View key={fraction} style={[styles.gridLine, { left: plotLeft, top: y, width: plotWidth }]}>
            <Text style={[styles.axisValue, { left: -28 }]}>{Math.round(max * fraction)}</Text>
          </View>
        );
      })}
      {points.slice(1).map((point, index) => {
        const previous = points[index];
        const dx = point.x - previous.x;
        const dy = point.y - previous.y;
        const length = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx);
        return (
          <View
            key={`line-${point.label}`}
            style={[
              styles.trendLine,
              {
                left: (point.x + previous.x - length) / 2,
                top: (point.y + previous.y) / 2 - 1,
                width: length,
                transform: [{ rotate: `${angle}rad` }],
              },
            ]}
          />
        );
      })}
      {points.map((point) => (
        <View key={point.label} style={[styles.trendPointGroup, { left: point.x - 12, top: point.y - 17 }]}>
          <Text style={styles.trendValue}>{point.count}</Text>
          <View style={styles.trendPoint} />
        </View>
      ))}
      {points.map((point) => (
        <Text key={`label-${point.label}`} style={[styles.monthLabel, { left: point.x - 32, top: plotBottom + 14 }]} numberOfLines={1}>
          {point.label}
        </Text>
      ))}
    </View>
  );
}

function verificationLabel(finding?: ObservationFindingResponse): string {
  if (!finding) return 'Finding verification status unavailable';
  if (finding.status === 'ai_suggested') return 'AI-suggested finding · not mentor-verified';
  if (finding.status === 'mentor_approved') return 'Mentor-verified finding';
  if (finding.status === 'rejected') return 'Finding rejected by mentor';
  return `Finding status: ${finding.status}`;
}

function GapEvidence({
  gap,
  observation,
  finding,
  school,
  visit,
  recommendations,
}: {
  gap: LearningGapResponse;
  observation?: ObservationResponse;
  finding?: ObservationFindingResponse;
  school?: SchoolResponse;
  visit?: SchoolVisitResponse;
  recommendations: RecommendationResponse[];
}) {
  const [expanded, setExpanded] = useState(false);
  const evidence = useEvidence({ observation_id: expanded ? observation?.id : undefined });

  return (
    <Card style={styles.gapCard}>
      <View style={styles.gapHeader}>
        <Text style={styles.gapTitle}>{gap.title}</Text>
        <StatusBadge status={gap.severity} />
      </View>
      <Text style={styles.gapMeta}>
        {gap.subject}{gap.grade ? ` · Grade ${gap.grade}` : ''} · {gap.status}
      </Text>
      <Text style={pageStyles.body}>{gap.description}</Text>
      <Pressable
        onPress={() => setExpanded((value) => !value)}
        accessibilityRole="button"
        accessibilityState={{ expanded }}
        style={styles.sourceToggle}
      >
        <Text style={styles.sourceToggleText}>{expanded ? 'Hide source and evidence' : 'View source and evidence'}</Text>
      </Pressable>

      {expanded ? (
        <View style={styles.sourcePanel}>
          <Text style={styles.sourceHeading}>Source and verification</Text>
          {school ? <Text style={pageStyles.muted}>School: {school.name}</Text> : <Text style={pageStyles.muted}>School: not linked in available records</Text>}
          {visit ? <Text style={pageStyles.muted}>Visit: {formatDateTime(visit.scheduled_at)} · {visit.status}</Text> : null}
          {observation ? (
            <>
              <Text style={pageStyles.muted}>
                Observation: {observation.subject}{observation.topic ? ` · ${observation.topic}` : ''}
              </Text>
              {observation.notes ? <Text style={pageStyles.body}>Recorded notes: {observation.notes}</Text> : null}
            </>
          ) : (
            <Text style={pageStyles.muted}>The linked observation record is not available.</Text>
          )}
          {finding ? (
            <>
              <Text style={pageStyles.muted}>Finding: {finding.title}</Text>
              <Text style={styles.verification}>{verificationLabel(finding)}</Text>
              <Text style={pageStyles.body}>{finding.description}</Text>
              {finding.mentor_comment ? <Text style={pageStyles.muted}>Mentor comment: {finding.mentor_comment}</Text> : null}
            </>
          ) : (
            <Text style={styles.verification}>{verificationLabel(finding)}</Text>
          )}

          <Text style={styles.sourceHeading}>Related recommendations</Text>
          {recommendations.length === 0 ? (
            <Text style={pageStyles.muted}>No recommendations are linked to this learning gap.</Text>
          ) : recommendations.map((recommendation) => (
            <View key={recommendation.id} style={styles.recommendation}>
              <View style={styles.gapHeader}>
                <Text style={styles.recommendationTitle}>{recommendation.title}</Text>
                <StatusBadge status={recommendation.status} />
              </View>
              <Text style={pageStyles.body}>{recommendation.description}</Text>
              {recommendation.rationale ? <Text style={pageStyles.muted}>Rationale: {recommendation.rationale}</Text> : null}
            </View>
          ))}

          <Text style={styles.sourceHeading}>Evidence files</Text>
          {!observation ? (
            <Text style={pageStyles.muted}>Evidence cannot be looked up without the source observation.</Text>
          ) : evidence.isLoading && !evidence.data ? (
            <LoadingState label="Loading evidence…" />
          ) : evidence.error && !evidence.data ? (
            <InlineNotice tone="warning" text="Evidence files could not be loaded." />
          ) : evidence.data?.length ? (
            evidence.data.map((item) => (
              <View key={item.id} style={styles.evidenceRow}>
                <Text style={styles.recommendationTitle}>{item.original_filename}</Text>
                {item.description ? <Text style={pageStyles.muted}>{item.description}</Text> : null}
                <Text style={pageStyles.muted}>Added {formatDateTime(item.created_at)}</Text>
              </View>
            ))
          ) : (
            <Text style={pageStyles.muted}>No evidence files are recorded for this observation.</Text>
          )}
        </View>
      ) : null}
    </Card>
  );
}

export default function LearningGapsScreen() {
  const queryClient = useQueryClient();
  const { width: screenWidth } = useWindowDimensions();
  const chartWidth = Math.max(220, Math.min(screenWidth - 80, 820));
  const gaps = useGaps();
  const observations = useObservations();
  const findings = useFindings();
  const recommendations = useRecommendations();
  const visits = useVisits();
  const schools = useSchools();
  const queries = [observations, findings, recommendations, visits, schools];

  const observationById = useMemo(() => new Map((observations.data ?? []).map((item) => [item.id, item])), [observations.data]);
  const findingById = useMemo(() => new Map((findings.data ?? []).map((item) => [item.id, item])), [findings.data]);
  const visitById = useMemo(() => new Map((visits.data ?? []).map((item) => [item.id, item])), [visits.data]);
  const schoolById = useMemo(() => new Map((schools.data ?? []).map((item) => [item.id, item])), [schools.data]);
  const recommendationByGap = useMemo(() => {
    const grouped = new Map<string, RecommendationResponse[]>();
    for (const item of recommendations.data ?? []) {
      grouped.set(item.learning_gap_id, [...(grouped.get(item.learning_gap_id) ?? []), item]);
    }
    return grouped;
  }, [recommendations.data]);

  const subjectDistribution = useMemo(
    () => distribution(gaps.data ?? [], (gap) => gap.subject),
    [gaps.data],
  );
  const gradeDistribution = useMemo(
    () => distribution(gaps.data ?? [], (gap) => gap.grade ?? 'Not recorded'),
    [gaps.data],
  );
  const schoolDistribution = useMemo(() => {
    const grouped = new Map<string, SchoolDistribution>();
    for (const gap of gaps.data ?? []) {
      const observation = observationById.get(gap.observation_id);
      const visit = observation ? visitById.get(observation.school_visit_id) : undefined;
      const school = visit ? schoolById.get(visit.school_id) : undefined;
      if (!school) continue;

      const item = grouped.get(school.id) ?? {
        id: school.id,
        name: school.name,
        count: 0,
        severities: new Map<string, number>(),
      };
      item.count += 1;
      const severity = gap.severity.trim();
      if (severity) item.severities.set(severity, (item.severities.get(severity) ?? 0) + 1);
      grouped.set(school.id, item);
    }
    return [...grouped.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  }, [gaps.data, observationById, schoolById, visitById]);
  const severityLabels = useMemo(
    () => [...new Set((gaps.data ?? []).map((gap) => gap.severity.trim()).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b)),
    [gaps.data],
  );
  const monthlyDistribution = useMemo(() => {
    const monthly = new Map<string, { label: string; count: number }>();
    for (const gap of gaps.data ?? []) {
      const createdAt = new Date(gap.created_at);
      if (Number.isNaN(createdAt.getTime())) continue;
      const key = `${createdAt.getFullYear()}-${String(createdAt.getMonth() + 1).padStart(2, '0')}`;
      const label = createdAt.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
      const item = monthly.get(key) ?? { label, count: 0 };
      item.count += 1;
      monthly.set(key, item);
    }
    return [...monthly.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-6)
      .map(([, item]) => item);
  }, [gaps.data]);

  const supportingDataUnavailable = queries.some((query) => query.error);
  const supportingDataLoading = queries.some((query) => query.isLoading && !query.data);
  const [refreshing, setRefreshing] = useState(false);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all(
        ['gaps', 'observations', 'findings', 'recommendations', 'visits', 'schools', 'evidence'].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <SafeAreaView style={pageStyles.safeArea} edges={['top']}>
      <ScrollView
        contentContainerStyle={pageStyles.content}
        refreshControl={<RefreshControl refreshing={refreshing || gaps.isRefetching} onRefresh={() => void refresh()} tintColor={C.teal} />}
      >
        <PageHeader title="Report Analysis" subtitle="Learning-gap patterns, school comparisons and source-backed classroom challenges" />

        {gaps.isLoading && !gaps.data ? (
          <LoadingState label="Loading learning gaps…" />
        ) : gaps.error && !gaps.data ? (
          <ErrorState error={gaps.error} onRetry={() => void gaps.refetch()} />
        ) : (
          <>
            {supportingDataLoading ? <LoadingState label="Loading related school and observation records…" /> : null}
            {supportingDataUnavailable ? (
              <InlineNotice tone="warning" text="Some source, recommendation or school data could not be refreshed. Available saved records are still shown." />
            ) : null}
            {gaps.error && gaps.data ? (
              <InlineNotice tone="warning" text="Showing saved learning-gap records because the latest refresh failed." />
            ) : null}

            <Card style={styles.totalCard}>
              <Text style={styles.totalLabel}>Total identified learning gaps</Text>
              <Text style={styles.totalValue}>{gaps.data?.length ?? 0}</Text>
              <Text style={pageStyles.muted}>Counted from the learning-gap records returned for your account.</Text>
            </Card>

            <SectionTitle title="Analytics" />
            <ChartCard title="Learning Gap Distribution" description="Share of recorded learning gaps by subject.">
              {subjectDistribution.length && gaps.data?.length ? (
                <DonutChart items={subjectDistribution} total={gaps.data.length} />
              ) : (
                <ChartEmpty message="Subject distribution is not available because no learning-gap records are recorded." />
              )}
            </ChartCard>

            <ChartCard title="Grade-wise Distribution" description="Recorded learning-gap counts by grade level.">
              {gradeDistribution.length && gaps.data?.length ? (
                <CategoryBarChart items={gradeDistribution} />
              ) : (
                <ChartEmpty message="Grade distribution is not available because no learning-gap records are recorded." />
              )}
            </ChartCard>

            <ChartCard title="School-wise Comparison" description="Recorded learning-gap counts for schools linked to the source observations.">
              {schoolDistribution.length ? (
                <SchoolBarChart items={schoolDistribution} />
              ) : (
                <ChartEmpty message="School comparison is not available because no learning gaps are linked to school records." />
              )}
            </ChartCard>

            <ChartCard title="Progress Trend" description="Monthly gap records based on their recorded creation dates; this is not a resolution-history chart.">
              {monthlyDistribution.length > 1 ? (
                <TrendChart items={monthlyDistribution} width={chartWidth} />
              ) : (
                <ChartEmpty message="A trend is not available yet. Dated learning-gap records from at least two different months are required." />
              )}
            </ChartCard>

            <ChartCard title="Gap Severity" description="Recorded severity levels across schools linked to source observations.">
              {schoolDistribution.length && severityLabels.length ? (
                <SeverityChart items={schoolDistribution} severities={severityLabels} />
              ) : (
                <ChartEmpty message="Severity comparison is not available because linked school and severity records are missing." />
              )}
            </ChartCard>

            <SectionTitle title="Identified challenges" />
            {gaps.data?.length ? (
              gaps.data.map((gap) => {
                const observation = observationById.get(gap.observation_id);
                const visit = observation ? visitById.get(observation.school_visit_id) : undefined;
                const finding = gap.observation_finding_id ? findingById.get(gap.observation_finding_id) : undefined;
                const school = visit ? schoolById.get(visit.school_id) : undefined;
                return (
                  <GapEvidence
                    key={gap.id}
                    gap={gap}
                    observation={observation}
                    finding={finding}
                    school={school}
                    visit={visit}
                    recommendations={recommendationByGap.get(gap.id) ?? []}
                  />
                );
              })
            ) : (
              <EmptyState title="No learning gaps recorded" message="Learning gaps from classroom observations will appear here when available." />
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  totalCard: { alignItems: 'flex-start', gap: 4, borderLeftWidth: 4, borderLeftColor: C.teal },
  totalLabel: { color: C.secondaryText, fontSize: 13, fontWeight: '700' },
  totalValue: { color: C.navy, fontSize: 30, fontWeight: '800' },
  chartCard: { gap: 6, marginBottom: 12, borderRadius: 18, shadowColor: C.navy, shadowOpacity: 0.045, shadowRadius: 10, shadowOffset: { width: 0, height: 3 }, elevation: 2 },
  chartTitle: { color: C.navy, fontSize: 16, fontWeight: '800' },
  chartDescription: { color: C.secondaryText, fontSize: 12, lineHeight: 18, marginBottom: 10 },
  chartEmpty: { color: C.secondaryText, fontSize: 13, lineHeight: 19, backgroundColor: '#F8FAFC', borderRadius: 12, padding: 12 },
  donutLayout: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'center', gap: 16, paddingVertical: 6 },
  donut: { position: 'relative', flexShrink: 0 },
  donutDot: { position: 'absolute', width: 8, height: 8, borderRadius: 4 },
  donutCenter: { position: 'absolute', left: 35, top: 35, width: 94, height: 94, borderRadius: 47, backgroundColor: C.surface, alignItems: 'center', justifyContent: 'center' },
  donutTotal: { color: C.navy, fontSize: 25, fontWeight: '800' },
  donutCaption: { color: C.secondaryText, fontSize: 11 },
  legendList: { flex: 1, minWidth: 140, gap: 10 },
  legendRow: { flexDirection: 'row', alignItems: 'center', gap: 7 },
  legendSwatch: { width: 10, height: 10, borderRadius: 3 },
  legendLabel: { color: C.text, fontSize: 12, flex: 1 },
  legendValue: { color: C.navy, fontSize: 12, fontWeight: '800' },
  chartRows: { gap: 14, paddingTop: 4 },
  schoolBarRow: { gap: 6 },
  schoolBarHeading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10 },
  schoolBarLabel: { color: C.text, fontSize: 12, flex: 1 },
  schoolBarValue: { color: C.navy, fontSize: 13, fontWeight: '800' },
  barTrack: { height: 10, borderRadius: 5, overflow: 'hidden', backgroundColor: '#E8EEF4' },
  barFill: { height: '100%', borderRadius: 5, backgroundColor: C.teal },
  severityLegend: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 2 },
  severityLegendItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  chartLegendText: { color: C.secondaryText, fontSize: 11 },
  severityRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  severitySchool: { width: '38%', color: C.text, fontSize: 11 },
  stackedTrack: { flex: 1, height: 13, borderRadius: 7, flexDirection: 'row', overflow: 'hidden', backgroundColor: '#E8EEF4' },
  gridLine: { position: 'absolute', height: 1, backgroundColor: '#E8EEF4' },
  axisValue: { position: 'absolute', top: -8, width: 24, textAlign: 'right', color: C.secondaryText, fontSize: 10 },
  trendLine: { position: 'absolute', height: 3, borderRadius: 2, backgroundColor: C.tealDark },
  trendPointGroup: { position: 'absolute', width: 24, alignItems: 'center', gap: 2 },
  trendValue: { color: C.navy, fontSize: 10, fontWeight: '800' },
  trendPoint: { width: 9, height: 9, borderRadius: 5, borderWidth: 2, borderColor: C.surface, backgroundColor: C.tealDark },
  monthLabel: { position: 'absolute', width: 64, textAlign: 'center', color: C.secondaryText, fontSize: 10 },
  gapCard: { gap: 8, marginBottom: 10 },
  gapHeader: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 },
  gapTitle: { color: C.navy, fontSize: 15, fontWeight: '800', flex: 1 },
  gapMeta: { color: C.tealDark, fontSize: 12, fontWeight: '700' },
  sourceToggle: { alignSelf: 'flex-start', paddingVertical: 5 },
  sourceToggleText: { color: C.tealDark, fontSize: 13, fontWeight: '700' },
  sourcePanel: { gap: 8, borderTopWidth: 1, borderTopColor: C.border, paddingTop: 10 },
  sourceHeading: { color: C.navy, fontSize: 13, fontWeight: '800', marginTop: 4 },
  verification: { color: C.tealDark, fontSize: 12, fontWeight: '700' },
  recommendation: { gap: 5, paddingVertical: 8, borderTopWidth: 1, borderTopColor: C.border },
  recommendationTitle: { color: C.navy, fontSize: 13, fontWeight: '700', flex: 1 },
  evidenceRow: { gap: 3, paddingVertical: 6 },
});
