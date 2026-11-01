import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { EmptyState, InlineNotice, QueryView } from '@/components/ui/states';
import { fieldStyles, FilterTabs, ScreenShell, SectionTitle } from '@/components/visits/field-ui';
import { MargColors as C } from '@/constants/theme';
import { useClassrooms, useGaps, useObservations, usePlans, useRecommendations, useSchoolTeachers, useSchools, useVisits } from '@/hooks/api';
import type { ActionPlanResponse, LearningGapResponse, ObservationResponse, RecommendationResponse, SchoolResponse, SchoolVisitResponse } from '@/lib/api/generated';
import { formatDate, formatDateTime } from '@/lib/format';

type ActiveFilter = 'all' | 'active' | 'inactive';

function plansBySchool(
  schools: SchoolResponse[],
  visits: SchoolVisitResponse[],
  observations: ObservationResponse[],
  gaps: LearningGapResponse[],
  recommendations: RecommendationResponse[],
  plans: ActionPlanResponse[],
) {
  const observationSchool = new Map<string, string>();
  const visitSchool = new Map(visits.map((visit) => [visit.id, visit.school_id]));
  observations.forEach((observation) => {
    const schoolId = visitSchool.get(observation.school_visit_id);
    if (schoolId) observationSchool.set(observation.id, schoolId);
  });
  const gapSchool = new Map<string, string>();
  gaps.forEach((gap) => {
    const schoolId = observationSchool.get(gap.observation_id);
    if (schoolId) gapSchool.set(gap.id, schoolId);
  });
  const recommendationSchool = new Map<string, string>();
  recommendations.forEach((recommendation) => {
    const schoolId = gapSchool.get(recommendation.learning_gap_id);
    if (schoolId) recommendationSchool.set(recommendation.id, schoolId);
  });

  const counts = new Map(schools.map((school) => [school.id, 0]));
  plans.forEach((plan) => {
    const schoolId = recommendationSchool.get(plan.recommendation_id);
    if (schoolId && plan.status !== 'completed' && plan.status !== 'cancelled') {
      counts.set(schoolId, (counts.get(schoolId) ?? 0) + 1);
    }
  });
  return counts;
}

export function SchoolList({ onOpen, onBack }: { onOpen: (school: SchoolResponse) => void; onBack: () => void }) {
  const schools = useSchools();
  const classrooms = useClassrooms();
  const visits = useVisits();
  const observations = useObservations();
  const gaps = useGaps();
  const recommendations = useRecommendations();
  const plans = usePlans();
  const [search, setSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>('all');
  const [districtFilter, setDistrictFilter] = useState('all');

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const list = [...(schools.data ?? [])].sort((a, b) => a.name.localeCompare(b.name));
    return list.filter((school) => {
      const matchesSearch = !q || [school.name, school.code, school.district ?? '', school.block ?? '', school.address ?? ''].some((v) => v.toLowerCase().includes(q));
      const matchesStatus = activeFilter === 'all' || (activeFilter === 'active' ? school.is_active : !school.is_active);
      const matchesDistrict = districtFilter === 'all' || school.district === districtFilter;
      return matchesSearch && matchesStatus && matchesDistrict;
    });
  }, [schools.data, search, activeFilter, districtFilter]);

  const districts = useMemo(() => new Set((schools.data ?? []).map((s) => s.district).filter(Boolean)).size, [schools.data]);
  const districtOptions = useMemo(
    () => ['all', ...new Set((schools.data ?? []).map((school) => school.district).filter((value): value is string => !!value).sort())],
    [schools.data],
  );
  const pendingPlanCounts = useMemo(() => {
    if (!schools.data || !visits.data || !observations.data || !gaps.data || !recommendations.data || !plans.data) return undefined;
    return plansBySchool(schools.data, visits.data, observations.data, gaps.data, recommendations.data, plans.data);
  }, [schools.data, visits.data, observations.data, gaps.data, recommendations.data, plans.data]);
  const supportingQueries = [classrooms, visits, observations, gaps, recommendations, plans];
  const supportingError = supportingQueries.some((query) => query.error);
  const supportingLoading = supportingQueries.some((query) => query.isLoading && !query.data);
  const retrySupporting = () => supportingQueries.forEach((query) => void query.refetch());
  const refreshing = schools.isRefetching || supportingQueries.some((query) => query.isRefetching);
  const refreshAll = () => {
    void schools.refetch();
    retrySupporting();
  };

  return (
    <ScreenShell
      title="My Schools"
      subtitle="Schools assigned to you"
      icon="⌂"
      onBack={onBack}
      refreshing={refreshing}
      onRefresh={refreshAll}
    >
      <QueryView query={schools} loadingLabel="Loading your schools…">
        {(data) => (
          <>
            <View style={styles.summaryCard}>
              <Text style={styles.summaryLabel}>TOTAL ASSIGNED SCHOOLS</Text>
              <Text style={styles.summaryNumber}>{data.length}</Text>
              <Text style={styles.summaryDescription}>
                Across {districts} {districts === 1 ? 'district' : 'districts'}
              </Text>
            </View>

            <View style={styles.searchContainer}>
              <Text style={styles.searchIcon}>⌕</Text>
              <TextInput
                style={styles.searchInput}
                placeholder="Search by name, code or district…"
                placeholderTextColor={C.muted}
                value={search}
                onChangeText={setSearch}
                autoCapitalize="none"
                clearButtonMode="while-editing"
                accessibilityLabel="Search schools"
              />
            </View>

            <FilterTabs
              options={[
                { value: 'all', label: 'All', count: data.length },
                { value: 'active', label: 'Active', count: data.filter((school) => school.is_active).length },
                { value: 'inactive', label: 'Inactive', count: data.filter((school) => !school.is_active).length },
              ]}
              value={activeFilter}
              onChange={setActiveFilter}
            />
            {districtOptions.length > 2 ? (
              <FilterTabs
                options={[
                  { value: 'all', label: 'All districts' },
                  ...districtOptions.slice(1).map((district) => ({ value: district, label: district })),
                ]}
                value={districtFilter}
                onChange={setDistrictFilter}
              />
            ) : null}
            {supportingError ? (
              <View style={{ marginBottom: 8 }}>
                <InlineNotice tone="warning" text="Some school summary details could not be loaded." />
                <Pressable onPress={retrySupporting} accessibilityRole="button" style={{ paddingVertical: 8 }}>
                  <Text style={styles.retryText}>Retry summary details</Text>
                </Pressable>
              </View>
            ) : supportingLoading ? (
              <InlineNotice text="Loading visit, classroom and action-plan summaries…" />
            ) : null}

            <SectionTitle title="Assigned schools" right={<Text style={fieldStyles.muted}>{filtered.length} results</Text>} />

            {data.length === 0 ? (
              <EmptyState title="No schools assigned" message="Ask your administrator to assign schools to your account." />
            ) : filtered.length === 0 ? (
              <EmptyState title="No matching schools" message="Try a different name, code or district." />
            ) : (
              filtered.map((school) => (
                <DirectorySchoolCard
                  key={school.id}
                  school={school}
                  classrooms={classrooms.data ?? []}
                  visits={visits.data ?? []}
                  pendingPlans={pendingPlanCounts?.get(school.id)}
                  summariesReady={!supportingLoading && !!classrooms.data && !!visits.data && !!pendingPlanCounts}
                  onOpen={() => onOpen(school)}
                />
              ))
            )}
          </>
        )}
      </QueryView>
    </ScreenShell>
  );
}

function DirectorySchoolCard({
  school,
  classrooms,
  visits,
  pendingPlans,
  summariesReady,
  onOpen,
}: {
  school: SchoolResponse;
  classrooms: { school_id: string }[];
  visits: SchoolVisitResponse[];
  pendingPlans?: number;
  summariesReady: boolean;
  onOpen: () => void;
}) {
  const teachers = useSchoolTeachers(school.id);
  const schoolClassrooms = classrooms.filter((classroom) => classroom.school_id === school.id);
  const schoolVisits = visits.filter((visit) => visit.school_id === school.id && visit.status !== 'cancelled');
  const completedVisits = schoolVisits.filter((visit) => visit.status === 'completed').sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at));
  const nextVisits = schoolVisits
    .filter((visit) => visit.status === 'planned' || visit.status === 'in_progress')
    .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));

  return (
    <Pressable
      style={({ pressed }) => [styles.schoolCard, pressed && { opacity: 0.9 }]}
      onPress={onOpen}
      accessibilityRole="button"
      accessibilityLabel={`${school.name}, ${school.district ?? ''}. Open details`}
    >
      <View style={styles.schoolCardHeader}>
        <View style={styles.schoolIcon}>
          <Text style={styles.schoolIconText}>{school.name.charAt(0)}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.schoolName}>{school.name}</Text>
          <Text style={styles.schoolLocation}>{[school.block, school.district].filter(Boolean).join(', ') || 'Location not recorded'}</Text>
          <Text style={styles.schoolCode}>
            {school.code}
            {school.travel_minutes_from_base != null ? ` · ${school.travel_minutes_from_base} min from base` : ''}
          </Text>
        </View>
        <Text style={fieldStyles.chevron}>›</Text>
      </View>
      <View style={styles.metricsRow}>
        <Text style={styles.metricText}>Teachers: {teachers.data ? teachers.data.length : teachers.isError ? 'Unavailable' : '—'}</Text>
        <Text style={styles.metricText}>Classrooms: {summariesReady ? schoolClassrooms.length : '—'}</Text>
      </View>
      <View style={styles.metricsRow}>
        <Text style={styles.metricText}>Last visit: {summariesReady ? formatDate(completedVisits[0]?.scheduled_at) : '—'}</Text>
        <Text style={styles.metricText}>Next: {summariesReady ? formatDateTime(nextVisits[0]?.scheduled_at) : '—'}</Text>
      </View>
      <Text style={styles.metricText}>Pending action plans: {pendingPlans === undefined ? '—' : pendingPlans}</Text>
      {!school.is_active ? <Text style={styles.inactiveText}>Inactive assignment</Text> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  summaryCard: { backgroundColor: C.navy, borderRadius: 19, padding: 20, marginBottom: 18 },
  summaryLabel: { color: '#B8C9DC', fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  summaryNumber: { color: '#FFFFFF', fontSize: 39, fontWeight: '800', marginTop: 5 },
  summaryDescription: { color: '#D0DCE9', fontSize: 12, marginTop: 2 },
  searchContainer: {
    height: 49,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 14,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    marginBottom: 6,
  },
  searchIcon: { color: C.muted, fontSize: 20, marginRight: 8 },
  searchInput: { flex: 1, color: C.text, fontSize: 15, height: '100%' },
  schoolCard: {
    backgroundColor: C.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: C.border,
    padding: 16,
    marginBottom: 12,
  },
  schoolCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  metricsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 10, paddingLeft: 56 },
  metricText: { color: C.secondaryText, fontSize: 12, fontWeight: '600' },
  inactiveText: { color: C.danger, fontSize: 12, fontWeight: '700', marginTop: 8, paddingLeft: 56 },
  retryText: { color: C.tealDark, fontSize: 13, fontWeight: '700' },
  schoolIcon: { width: 44, height: 44, borderRadius: 13, backgroundColor: '#E7F5F3', alignItems: 'center', justifyContent: 'center' },
  schoolIconText: { color: C.tealDark, fontSize: 18, fontWeight: '800' },
  schoolName: { color: C.navy, fontSize: 15, fontWeight: '800' },
  schoolLocation: { color: C.secondaryText, fontSize: 13, marginTop: 3 },
  schoolCode: { color: C.muted, fontSize: 12, marginTop: 3, fontWeight: '600' },
});
