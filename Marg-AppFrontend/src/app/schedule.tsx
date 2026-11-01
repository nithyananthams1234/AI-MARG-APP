import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ProposalFormModal } from '@/components/schedule/proposal-form-modal';
import { ProposalCard, TaskDueItem, VisitAgendaItem } from '@/components/schedule/schedule-items';
import { schStyles as styles } from '@/components/schedule/schedule-styles';
import { addDays, dayLabel, inRange, sameLocalDay, startOfWeek } from '@/components/schedule/schedule-utils';
import { WeekStrip } from '@/components/schedule/week-strip';
import { EmptyState, ErrorState, InlineNotice, QueryView } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useDecideSchedule, useSchedules, useSchools, useTasks, useVisits } from '@/hooks/api';
import { useDailyWorkload } from '@/hooks/api-cycle';
import type { SchoolVisitResponse } from '@/lib/api/generated';
import { toDateInput } from '@/lib/format';

const proposalFilters = ['proposed', 'accepted', 'rejected'] as const;
type ProposalFilter = (typeof proposalFilters)[number];

export default function ScheduleScreen() {
  const router = useRouter();
  const visits = useVisits();
  const schedules = useSchedules();
  const tasks = useTasks();
  const schools = useSchools();
  const decide = useDecideSchedule();

  const [selected, setSelected] = useState(() => new Date());
  const [proposalFilter, setProposalFilter] = useState<ProposalFilter>('proposed');
  const [proposingFor, setProposingFor] = useState<SchoolVisitResponse | null>(null);
  const [decidingId, setDecidingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: 'success' | 'danger'; text: string } | null>(null);

  const selectedDate = toDateInput(selected);
  const workload = useDailyWorkload(selectedDate);

  const weekStart = useMemo(() => startOfWeek(selected), [selected]);
  const weekEnd = useMemo(() => addDays(weekStart, 7), [weekStart]);
  const schoolName = (id: string | null) => (id ? schools.data?.find((s) => s.id === id)?.name ?? 'School' : undefined);

  const allVisits = useMemo(() => visits.data ?? [], [visits.data]);
  const allProposals = useMemo(() => schedules.data ?? [], [schedules.data]);

  const dayCounts = useMemo(
    () => Array.from({ length: 7 }, (_, i) => allVisits.filter((v) => sameLocalDay(v.scheduled_at, addDays(weekStart, i))).length),
    [allVisits, weekStart],
  );
  const dayVisits = useMemo(
    () => allVisits.filter((v) => sameLocalDay(v.scheduled_at, selected)).sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at)),
    [allVisits, selected],
  );
  const weekVisits = dayCounts.reduce((a, b) => a + b, 0);
  const pendingProposals = allProposals.filter((p) => p.status === 'proposed');
  const shownProposals = allProposals
    .filter((p) => p.status === proposalFilter)
    .sort((a, b) => a.proposed_start_at.localeCompare(b.proposed_start_at));
  const weekTasks = useMemo(
    () => (tasks.data ?? [])
      .filter((t) => (t.status === 'pending' || t.status === 'in_progress') && t.due_at && inRange(t.due_at, weekStart, weekEnd))
      .sort((a, b) => (a.due_at ?? '').localeCompare(b.due_at ?? '')),
    [tasks.data, weekStart, weekEnd],
  );

  const decideProposal = async (id: string, status: 'accepted' | 'rejected') => {
    setDecidingId(id);
    setNotice(null);
    try {
      await decide.mutateAsync({ id, status });
      setNotice({ tone: 'success', text: status === 'accepted' ? 'Proposal accepted — the visit was moved to the proposed time.' : 'Proposal rejected.' });
    } catch (e) {
      setNotice({ tone: 'danger', text: (e as Error).message });
    } finally {
      setDecidingId(null);
    }
  };

  const refresh = () => {
    void visits.refetch();
    void schedules.refetch();
    void tasks.refetch();
    void workload.refetch();
  };

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.container}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={visits.isRefetching || schedules.isRefetching} onRefresh={refresh} tintColor={C.teal} />}
      >
        <View style={styles.header}>
          <Pressable style={styles.backButton} onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Go back">
            <Text style={styles.backText}>‹</Text>
          </Pressable>
          <View style={styles.headerTitle}>
            <Text style={styles.heading} accessibilityRole="header">Schedule</Text>
            <Text style={styles.subheading}>Your visits, time proposals and deadlines</Text>
          </View>
        </View>

        {notice ? <InlineNotice tone={notice.tone} text={notice.text} /> : null}

        <View style={styles.summaryRow}>
          <SummaryCard value={visits.data ? weekVisits : '–'} label="Visits this week" />
          <SummaryCard value={schedules.data ? pendingProposals.length : '–'} label="Proposals to decide" color="#8B5CC7" />
          <SummaryCard value={tasks.data ? weekTasks.length : '–'} label="Tasks due this week" color="#D58A28" />
        </View>

        <WeekStrip
          weekStart={weekStart}
          selected={selected}
          counts={dayCounts}
          onSelect={setSelected}
          onShiftWeek={(delta) => setSelected((d) => addDays(d, delta * 7))}
          onToday={() => setSelected(new Date())}
        />

        {/* Daily workload */}
        <View style={styles.noteCard} accessibilityLabel="Daily workload">
          <Text style={styles.noteTitle}>Workload · {dayLabel(selected)}</Text>
          {workload.isLoading ? (
            <ActivityIndicator color={C.teal} />
          ) : workload.data ? (
            <Text style={styles.noteText}>
              {workload.data.total_visits} visit{workload.data.total_visits === 1 ? '' : 's'} · {workload.data.total_minutes} min
              ({workload.data.total_hours} h) scheduled
            </Text>
          ) : (
            <Text style={styles.noteText}>Could not load workload: {(workload.error as Error | null)?.message ?? 'unknown error'}</Text>
          )}
        </View>

        {/* Agenda for the selected day */}
        <View style={[styles.section, { marginTop: 20 }]}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>{dayLabel(selected)}</Text>
            <Text style={styles.eventCount}>{dayVisits.length} visits</Text>
          </View>
          <QueryView query={visits} loadingLabel="Loading visits…">
            {() =>
              dayVisits.length === 0 ? (
                <View style={styles.emptyCard}>
                  <Text style={styles.emptyTitle}>No visits on this day</Text>
                  <Text style={styles.emptyText}>Plan visits from the Visits screen.</Text>
                </View>
              ) : (
                dayVisits.map((v) => (
                  <VisitAgendaItem
                    key={v.id}
                    visit={v}
                    schoolName={schoolName(v.school_id) ?? 'School'}
                    pendingProposals={pendingProposals.filter((p) => p.school_visit_id === v.id).length}
                    onPropose={() => setProposingFor(v)}
                  />
                ))
              )
            }
          </QueryView>
        </View>

        {/* Time proposals */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Visit time proposals</Text>
            <Text style={styles.eventCount}>{shownProposals.length} shown</Text>
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
            {proposalFilters.map((f) => {
              const active = proposalFilter === f;
              return (
                <Pressable
                  key={f}
                  onPress={() => setProposalFilter(f)}
                  style={[styles.filterButton, active && styles.activeFilter]}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                >
                  <Text style={[styles.filterText, active && styles.activeFilterText]}>{f.charAt(0).toUpperCase() + f.slice(1)}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
          {schedules.isLoading && !schedules.data ? (
            <ActivityIndicator color={C.teal} />
          ) : !schedules.data ? (
            <ErrorState error={schedules.error} onRetry={() => void schedules.refetch()} />
          ) : shownProposals.length === 0 ? (
            <EmptyState title={`No ${proposalFilter} proposals`} message="Use “Propose time” on a planned visit to suggest a new time." />
          ) : (
            shownProposals.map((p) => (
              <ProposalCard
                key={p.id}
                proposal={p}
                schoolName={schoolName(p.school_id) ?? 'School'}
                busy={decidingId === p.id}
                onDecide={(status) => void decideProposal(p.id, status)}
              />
            ))
          )}
        </View>

        {/* Task deadlines this week */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Task deadlines this week</Text>
            <Pressable onPress={() => router.push('/tasks')} accessibilityRole="link">
              <Text style={[styles.eventCount, { color: C.tealDark, fontWeight: '700' }]}>All tasks</Text>
            </Pressable>
          </View>
          {tasks.isLoading && !tasks.data ? (
            <ActivityIndicator color={C.teal} />
          ) : !tasks.data ? (
            <ErrorState error={tasks.error} onRetry={() => void tasks.refetch()} />
          ) : weekTasks.length === 0 ? (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyTitle}>No open tasks due this week</Text>
            </View>
          ) : (
            weekTasks.map((t) => <TaskDueItem key={t.id} task={t} schoolName={schoolName(t.school_id)} />)
          )}
        </View>
      </ScrollView>

      <ProposalFormModal
        visit={proposingFor}
        schoolName={schoolName(proposingFor?.school_id ?? null) ?? 'School'}
        onClose={() => setProposingFor(null)}
        onCreated={() => {
          setProposingFor(null);
          setProposalFilter('proposed');
          setNotice({ tone: 'success', text: 'Time proposal created. Accept it to move the visit.' });
        }}
      />
    </SafeAreaView>
  );
}

function SummaryCard({ value, label, color }: { value: number | string; label: string; color?: string }) {
  return (
    <View style={styles.summaryCard} accessibilityLabel={`${label}: ${value}`}>
      <Text style={[styles.summaryNumber, color ? { color } : null]}>{value}</Text>
      <Text style={styles.summaryLabel}>{label}</Text>
    </View>
  );
}
