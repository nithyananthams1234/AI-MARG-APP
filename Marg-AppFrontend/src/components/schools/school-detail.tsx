import { useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Button, Card, EmptyState, ErrorState, InlineNotice, LoadingState, QueryView, StatusBadge } from '@/components/ui/states';
import { ChipSelect, fieldStyles, InfoRow, ScreenShell, SectionTitle } from '@/components/visits/field-ui';
import { MargColors as C } from '@/constants/theme';
import { useClassrooms, useEvidence, useFollowUps, useGaps, useObservations, usePlans, useRecommendations, useSchool, useSchoolReport, useSchoolTeachers, useSchoolTimetables, useSteps, useTimetable, useVisits } from '@/hooks/api';
import type { ActionPlanResponse, LearningGapResponse, ObservationResponse, RecommendationResponse, TeacherResponse, TimetableResponse } from '@/lib/api/generated';
import { formatDate, formatDateTime } from '@/lib/format';

const WEEK_ORDER = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
const dayRank = (d: string) => {
  const i = WEEK_ORDER.indexOf(d.toLowerCase());
  return i === -1 ? WEEK_ORDER.length : i;
};
const hhmm = (t: string) => t.slice(0, 5);

export function SchoolDetail({
  schoolId,
  onBack,
  onPlanVisit,
  onAskCoach,
  onOpenVisit,
  onOpenObservation,
}: {
  schoolId: string;
  onBack: () => void;
  onPlanVisit: () => void;
  onAskCoach: (schoolName: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenObservation: (observationId: string) => void;
}) {
  const school = useSchool(schoolId);
  const report = useSchoolReport(schoolId);
  const teachers = useSchoolTeachers(schoolId);
  const classrooms = useClassrooms(schoolId);
  const schoolTimetables = useSchoolTimetables((classrooms.data ?? []).map((classroom) => classroom.id));
  const visits = useVisits({ school_id: schoolId });
  const observations = useObservations();
  const gaps = useGaps();
  const recommendations = useRecommendations();
  const plans = usePlans();
  const [classroomId, setClassroomId] = useState<string | null>(null);

  const refreshing = school.isRefetching || report.isRefetching || teachers.isRefetching || classrooms.isRefetching || visits.isRefetching;
  const refresh = () => {
    void school.refetch();
    void report.refetch();
    void teachers.refetch();
    void classrooms.refetch();
    schoolTimetables.forEach((query) => void query.refetch());
    void visits.refetch();
    void observations.refetch();
    void gaps.refetch();
    void recommendations.refetch();
    void plans.refetch();
  };

  const s = school.data;
  const visitIds = useMemo(() => new Set((visits.data ?? []).map((visit) => visit.id)), [visits.data]);
  const schoolObservations = useMemo(
    () => (observations.data ?? []).filter((observation) => visitIds.has(observation.school_visit_id)),
    [observations.data, visitIds],
  );
  const observationIds = useMemo(() => new Set(schoolObservations.map((observation) => observation.id)), [schoolObservations]);
  const schoolGaps = useMemo(
    () => (gaps.data ?? []).filter((gap) => observationIds.has(gap.observation_id)),
    [gaps.data, observationIds],
  );
  const gapIds = useMemo(() => new Set(schoolGaps.map((gap) => gap.id)), [schoolGaps]);
  const schoolRecommendations = useMemo(
    () => (recommendations.data ?? []).filter((recommendation) => gapIds.has(recommendation.learning_gap_id)),
    [recommendations.data, gapIds],
  );
  const recommendationIds = useMemo(() => new Set(schoolRecommendations.map((recommendation) => recommendation.id)), [schoolRecommendations]);
  const schoolPlans = useMemo(
    () => (plans.data ?? []).filter((plan) => recommendationIds.has(plan.recommendation_id)),
    [plans.data, recommendationIds],
  );
  const recommendationsByGap = useMemo(() => {
    const grouped = new Map<string, RecommendationResponse[]>();
    schoolRecommendations.forEach((recommendation) => {
      grouped.set(recommendation.learning_gap_id, [...(grouped.get(recommendation.learning_gap_id) ?? []), recommendation]);
    });
    return grouped;
  }, [schoolRecommendations]);
  const gapsByObservation = useMemo(() => {
    const grouped = new Map<string, LearningGapResponse[]>();
    schoolGaps.forEach((gap) => grouped.set(gap.observation_id, [...(grouped.get(gap.observation_id) ?? []), gap]));
    return grouped;
  }, [schoolGaps]);
  const observationById = useMemo(() => new Map(schoolObservations.map((observation) => [observation.id, observation])), [schoolObservations]);
  const recommendationById = useMemo(() => new Map(schoolRecommendations.map((recommendation) => [recommendation.id, recommendation])), [schoolRecommendations]);

  return (
    <ScreenShell title={s?.name ?? 'School'} subtitle={s?.code} icon="⌂" onBack={onBack} refreshing={refreshing} onRefresh={refresh}>
      <QueryView query={school} loadingLabel="Loading school…">
        {(data) => (
          <>
            <Card>
              <InfoRow label="District" value={data.district} />
              <InfoRow label="Block" value={data.block} />
              <InfoRow label="State" value={data.state} />
              <InfoRow label="Address" value={data.address} />
              <InfoRow label="School category" value={null} />
              <InfoRow
                label="Travel from base"
                value={data.travel_minutes_from_base != null ? `${data.travel_minutes_from_base} min` : null}
              />
              <View style={[fieldStyles.row, { marginTop: 14 }]}>
                <Button label="Plan visit" onPress={onPlanVisit} style={fieldStyles.grow} accessibilityLabel={`Plan a visit to ${data.name}`} />
                <Button label="Ask Classroom Coach" variant="secondary" onPress={() => onAskCoach(data.name)} style={fieldStyles.grow} />
              </View>
            </Card>
            <InlineNotice text="School category is not provided by the current school records." />

            <SectionTitle title="School report" />
            <QueryView query={report} loadingLabel="Loading report…">
              {(r) => (
                <View style={styles.statsGrid}>
                  <Stat label="Visits" value={r.total_visits} detail={`${r.completed_visits} completed`} />
                  <Stat label="Observations" value={r.total_observations} />
                  <Stat label="Learning gaps" value={r.total_learning_gaps} detail={`${r.open_learning_gaps ?? 0} open`} />
                  <Stat label="Action plans" value={r.total_action_plans} detail={`${r.completed_action_plans} completed`} />
                  <Stat label="Open follow-ups" value={r.open_follow_ups ?? 0} />
                </View>
              )}
            </QueryView>

            <SectionTitle title="Teachers" />
            <QueryView query={teachers} loadingLabel="Loading teachers…">
              {(list) =>
                list.length === 0 ? (
                  <EmptyState title="No teachers assigned" message="No teachers are assigned to this school yet." />
                ) : (
                  <Card>
                    {list.map((t, i) => (
                      <View key={t.id} style={[styles.teacherRow, i === list.length - 1 && { borderBottomWidth: 0 }]}>
                        <Text style={fieldStyles.itemTitle}>{t.full_name}</Text>
                        <Text style={fieldStyles.muted}>
                          {teacherHistorySummary(t, schoolObservations, schoolGaps, schoolRecommendations, observationById, classrooms.data ?? [], schoolTimetables)}
                        </Text>
                      </View>
                    ))}
                  </Card>
                )
              }
            </QueryView>

            <SectionTitle title="Classrooms" />
            <QueryView query={classrooms} loadingLabel="Loading classrooms…">
              {(list) =>
                list.length === 0 ? (
                  <EmptyState title="No classrooms" message="No classrooms are recorded for this school." />
                ) : (
                  <>
                    <ChipSelect
                      label="Select a classroom to see its weekly timetable"
                      options={[...list]
                        .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
                        .map((c) => ({
                          value: c.id,
                          label: c.name,
                          detail: `Grade ${c.grade}${c.section ? ` · Section ${c.section}` : ''}${c.capacity != null ? ` · Capacity ${c.capacity}` : ''}`,
                        }))}
                      value={classroomId}
                      onChange={setClassroomId}
                    />
                    {classroomId ? <Timetable classroomId={classroomId} teachers={teachers.data ?? []} /> : null}
                  </>
                )
              }
            </QueryView>

            <SectionTitle title="Previous visits" />
            <QueryView query={visits} loadingLabel="Loading school visits…">
              {(list) => {
                const ordered = [...list].sort((a, b) => b.scheduled_at.localeCompare(a.scheduled_at));
                return ordered.length === 0 ? (
                  <EmptyState title="No visit history" message="Visits for this school will appear here." />
                ) : (
                  ordered.map((visit) => (
                    <Card key={visit.id}>
                      <View style={fieldStyles.rowBetween}>
                        <Text style={fieldStyles.itemTitle}>{formatDateTime(visit.scheduled_at)}</Text>
                        <StatusBadge status={visit.status} />
                      </View>
                      <Text style={fieldStyles.itemText}>{visit.notes || 'No mentor notes recorded.'}</Text>
                      <Button label="Open visit and observations" variant="ghost" onPress={() => onOpenVisit(visit.id)} />
                    </Card>
                  ))
                );
              }}
            </QueryView>

            <SectionTitle title="Classroom observations and learning gaps" />
            {observations.isLoading || gaps.isLoading || recommendations.isLoading ? (
              <LoadingState label="Loading mentoring history…" />
            ) : observations.error || gaps.error || recommendations.error ? (
              <ErrorState
                error={observations.error ?? gaps.error ?? recommendations.error}
                onRetry={() => {
                  void observations.refetch();
                  void gaps.refetch();
                  void recommendations.refetch();
                }}
              />
            ) : schoolObservations.length === 0 ? (
              <EmptyState title="No classroom observations" message="Observation records for this school will appear here." />
            ) : (
              [...schoolObservations].sort((a, b) => b.created_at.localeCompare(a.created_at)).map((observation) => (
                <ObservationHistoryCard
                  key={observation.id}
                  observation={observation}
                  teacher={teachers.data?.find((teacher) => teacher.id === observation.teacher_id)}
                  classroom={classrooms.data?.find((classroom) => classroom.id === observation.classroom_id)}
                  gaps={gapsByObservation.get(observation.id) ?? []}
                  recommendationsByGap={recommendationsByGap}
                  onOpen={() => onOpenObservation(observation.id)}
                />
              ))
            )}

            <SectionTitle title="Action plans and follow-ups" />
            {plans.isLoading || recommendations.isLoading || gaps.isLoading || observations.isLoading ? (
              <LoadingState label="Loading action plans…" />
            ) : plans.error || recommendations.error || gaps.error || observations.error ? (
              <ErrorState
                error={plans.error ?? recommendations.error ?? gaps.error ?? observations.error}
                onRetry={() => {
                  void plans.refetch();
                  void recommendations.refetch();
                  void gaps.refetch();
                  void observations.refetch();
                }}
              />
            ) : schoolPlans.length === 0 ? (
              <EmptyState title="No action plans" message="Plans linked to this school's recommendations will appear here." />
            ) : (
              [...schoolPlans].sort((a, b) => b.due_date.localeCompare(a.due_date)).map((plan) => {
                const recommendation = recommendationById.get(plan.recommendation_id);
                const gap = recommendation ? schoolGaps.find((item) => item.id === recommendation.learning_gap_id) : undefined;
                const observation = gap ? observationById.get(gap.observation_id) : undefined;
                const teacher = observation ? teachers.data?.find((item) => item.id === observation.teacher_id) : undefined;
                return (
                  <SchoolActionPlan
                    key={plan.id}
                    plan={plan}
                    recommendation={recommendation}
                    gap={gap}
                    teacherName={teacher?.full_name}
                    teachers={teachers.data ?? []}
                  />
                );
              })
            )}
          </>
        )}
      </QueryView>
    </ScreenShell>
  );
}

function ObservationHistoryCard({
  observation,
  teacher,
  classroom,
  gaps,
  recommendationsByGap,
  onOpen,
}: {
  observation: ObservationResponse;
  teacher?: TeacherResponse;
  classroom?: { grade: string; section: string | null };
  gaps: LearningGapResponse[];
  recommendationsByGap: Map<string, RecommendationResponse[]>;
  onOpen: () => void;
}) {
  return (
    <Card onPress={onOpen}>
      <View style={fieldStyles.rowBetween}>
        <Text style={fieldStyles.itemTitle}>{observation.subject}{observation.topic ? ` · ${observation.topic}` : ''}</Text>
        <StatusBadge status={observation.status} />
      </View>
      <Text style={fieldStyles.muted}>
        {teacher?.full_name ?? 'Teacher not listed'} · {classroom ? `Grade ${classroom.grade}${classroom.section ? ` · ${classroom.section}` : ''}` : 'Classroom details unavailable'} · {formatDate(observation.created_at)}
      </Text>
      <Text style={fieldStyles.itemText}>{observation.notes || 'No observation notes recorded.'}</Text>
      {gaps.map((gap) => {
        const linkedRecommendations = recommendationsByGap.get(gap.id) ?? [];
        return (
          <View key={gap.id} style={styles.historyItem}>
            <View style={fieldStyles.rowBetween}>
              <Text style={fieldStyles.itemTitle}>{gap.title}</Text>
              <StatusBadge status={gap.severity} />
            </View>
            <Text style={fieldStyles.itemText}>{gap.description}</Text>
            <Text style={fieldStyles.muted}>Learning gap status: {gap.status}</Text>
            {linkedRecommendations.map((recommendation) => (
              <View key={recommendation.id} style={styles.historyItem}>
                <Text style={fieldStyles.itemTitle}>{recommendation.title}</Text>
                <Text style={fieldStyles.itemText}>{recommendation.description}</Text>
                <View style={fieldStyles.rowBetween}>
                  <Text style={fieldStyles.muted}>Recommendation</Text>
                  <StatusBadge status={recommendation.status} />
                </View>
              </View>
            ))}
          </View>
        );
      })}
      <Button label="Open observation analysis" variant="ghost" onPress={onOpen} />
    </Card>
  );
}

function SchoolActionPlan({
  plan,
  recommendation,
  gap,
  teacherName,
  teachers,
}: {
  plan: ActionPlanResponse;
  recommendation?: RecommendationResponse;
  gap?: LearningGapResponse;
  teacherName?: string;
  teachers: TeacherResponse[];
}) {
  const steps = useSteps(plan.id);
  return (
    <Card>
      <View style={fieldStyles.rowBetween}>
        <Text style={fieldStyles.itemTitle}>{plan.title}</Text>
        <StatusBadge status={plan.status} />
      </View>
      {recommendation ? (
        <View style={styles.historyItem}>
          <Text style={fieldStyles.muted}>Linked recommendation · {recommendation.status}</Text>
          <Text style={fieldStyles.itemText}>{recommendation.title}</Text>
        </View>
      ) : null}
      {gap ? <Text style={fieldStyles.muted}>Learning gap: {gap.title} · {gap.severity}</Text> : null}
      {teacherName ? <Text style={fieldStyles.muted}>Observed teacher: {teacherName}</Text> : null}
      <Text style={fieldStyles.itemText}>{plan.description}</Text>
      <InfoRow label="Responsible person" value={plan.responsible_person} />
      <InfoRow label="Deadline" value={formatDate(plan.due_date)} />
      <QueryView query={steps} loadingLabel="Loading action-plan steps…">
        {(list) => (
          list.length === 0 ? (
            <Text style={fieldStyles.muted}>No measurable steps are recorded for this plan.</Text>
          ) : list.map((step) => (
            <View key={step.id} style={styles.historyItem}>
              <View style={fieldStyles.rowBetween}>
                <Text style={fieldStyles.itemTitle}>{step.title}</Text>
                <StatusBadge status={step.status} />
              </View>
              <Text style={fieldStyles.itemText}>{step.description}</Text>
              <Text style={fieldStyles.muted}>Due {formatDate(step.due_date)} · Responsible: {step.responsible_person}</Text>
              {step.completion_notes ? <Text style={fieldStyles.itemText}>Completion note: {step.completion_notes}</Text> : null}
              <StepFollowUps stepId={step.id} teachers={teachers} />
            </View>
          ))
        )}
      </QueryView>
    </Card>
  );
}

function StepFollowUps({ stepId, teachers }: { stepId: string; teachers: TeacherResponse[] }) {
  const followUps = useFollowUps({ action_plan_step_id: stepId });
  if (followUps.isLoading && !followUps.data) return <LoadingState label="Loading teacher follow-ups…" />;
  if (!followUps.data) return <ErrorState error={followUps.error} onRetry={() => void followUps.refetch()} />;
  if (followUps.data.length === 0) return <Text style={fieldStyles.muted}>No teacher follow-up is recorded for this step.</Text>;

  return (
    <>
      {followUps.data.map((followUp) => (
        <View key={followUp.id} style={styles.followUpItem}>
          <View style={fieldStyles.rowBetween}>
            <Text style={fieldStyles.itemTitle}>{teachers.find((teacher) => teacher.id === followUp.teacher_id)?.full_name ?? 'Teacher'}</Text>
            <StatusBadge status={followUp.status} />
          </View>
          <Text style={fieldStyles.itemText}>{followUp.description}</Text>
          {followUp.teacher_response ? <Text style={fieldStyles.itemText}>Teacher response: {followUp.teacher_response}</Text> : null}
          {followUp.mentor_notes ? <Text style={fieldStyles.itemText}>Mentor notes: {followUp.mentor_notes}</Text> : null}
          <InfoRow label="Mentor verification" value={followUp.verified_at ? formatDateTime(followUp.verified_at) : 'Not verified'} />
          <FollowUpEvidence followUpId={followUp.id} />
        </View>
      ))}
    </>
  );
}

function FollowUpEvidence({ followUpId }: { followUpId: string }) {
  const evidence = useEvidence({ follow_up_id: followUpId });
  if (evidence.isLoading && !evidence.data) return <Text style={fieldStyles.muted}>Loading submitted evidence…</Text>;
  if (!evidence.data) return <ErrorState error={evidence.error} onRetry={() => void evidence.refetch()} />;
  return <Text style={fieldStyles.muted}>Evidence files: {evidence.data.length}</Text>;
}

function teacherHistorySummary(
  teacher: TeacherResponse,
  observations: ObservationResponse[],
  gaps: LearningGapResponse[],
  recommendations: RecommendationResponse[],
  observationById: Map<string, ObservationResponse>,
  classrooms: { id: string; name: string }[],
  timetableQueries: ReturnType<typeof useSchoolTimetables>,
) {
  const observed = observations.filter((observation) => observation.teacher_id === teacher.id);
  const teacherGapIds = new Set(gaps.filter((gap) => observationById.get(gap.observation_id)?.teacher_id === teacher.id).map((gap) => gap.id));
  const teacherRecommendations = recommendations.filter((recommendation) => teacherGapIds.has(recommendation.learning_gap_id));
  const timetableEntries = timetableQueries.flatMap((query) => query.data ?? []).filter((entry) => entry.teacher_id === teacher.id);
  const classroomIds = new Set(timetableEntries.map((entry) => entry.classroom_id));
  const assignedClasses = classrooms.filter((classroom) => classroomIds.has(classroom.id)).map((classroom) => classroom.name);
  const subjects = [...new Set(timetableEntries.map((entry) => entry.subject))];
  const timetableLoading = timetableQueries.some((query) => query.isLoading && !query.data);
  const timetableError = timetableQueries.some((query) => query.error);
  const assignments = assignedClasses.length
    ? `Timetable classes: ${assignedClasses.join(', ')}`
    : timetableLoading
      ? 'Loading timetable assignments'
      : timetableError
        ? 'Timetable assignments unavailable'
        : 'No timetable class assignment recorded';
  const subjectList = subjects.length ? `Subjects: ${subjects.join(', ')}` : timetableLoading ? 'Loading timetable subjects' : 'Subjects not recorded';
  const waiting = teacherRecommendations.filter((recommendation) => recommendation.status === 'ai_suggested').length;
  const approved = teacherRecommendations.filter((recommendation) => recommendation.status === 'mentor_approved').length;
  const progress = `${observed.length} observations · ${waiting} AI suggestions awaiting review · ${approved} mentor-approved recommendations`;
  return [teacher.employee_code, assignments, subjectList, progress].filter(Boolean).join(' · ');
}

function Stat({ label, value, detail }: { label: string; value: number; detail?: string }) {
  return (
    <View style={styles.stat} accessible accessibilityLabel={`${label}: ${value}${detail ? `, ${detail}` : ''}`}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
      {detail ? <Text style={fieldStyles.muted}>{detail}</Text> : null}
    </View>
  );
}

function Timetable({ classroomId, teachers }: { classroomId: string; teachers: TeacherResponse[] }) {
  const timetable = useTimetable(classroomId);

  const days = useMemo(() => {
    const groups = new Map<string, TimetableResponse[]>();
    for (const p of timetable.data ?? []) {
      const list = groups.get(p.day_of_week) ?? [];
      list.push(p);
      groups.set(p.day_of_week, list);
    }
    return [...groups.entries()]
      .sort(([a], [b]) => dayRank(a) - dayRank(b))
      .map(([day, periods]) => ({ day, periods: periods.sort((a, b) => a.period_number - b.period_number) }));
  }, [timetable.data]);

  const teacherName = (id: string | null) => {
    if (!id) return 'No teacher assigned';
    return teachers.find((t) => t.id === id)?.full_name ?? 'Teacher not listed for this school';
  };

  if (timetable.isLoading && !timetable.data) return <LoadingState label="Loading timetable…" />;
  if (!timetable.data) return <ErrorState error={timetable.error} onRetry={() => void timetable.refetch()} />;
  if (days.length === 0) return <EmptyState title="No timetable" message="No periods are scheduled for this classroom." />;

  return (
    <>
      {days.map(({ day, periods }) => (
        <Card key={day}>
          <Text style={styles.dayTitle}>{day}</Text>
          {periods.map((p) => (
            <View key={p.id} style={styles.periodRow}>
              <Text style={styles.periodNo}>P{p.period_number}</Text>
              <View style={{ flex: 1 }}>
                <Text style={fieldStyles.itemTitle}>{p.subject}</Text>
                <Text style={fieldStyles.muted}>
                  {hhmm(p.start_time)}–{hhmm(p.end_time)} · {teacherName(p.teacher_id)}
                </Text>
              </View>
            </View>
          ))}
        </Card>
      ))}
    </>
  );
}

const styles = StyleSheet.create({
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 8 },
  stat: { flexGrow: 1, flexBasis: '30%', minWidth: 120, backgroundColor: C.surface, borderRadius: 14, borderWidth: 1, borderColor: C.border, padding: 12 },
  statValue: { color: C.navy, fontSize: 24, fontWeight: '800' },
  statLabel: { color: C.navy, fontSize: 13, fontWeight: '700' },
  teacherRow: { paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: C.border },
  historyItem: { borderLeftWidth: 3, borderLeftColor: C.teal, paddingLeft: 10, marginTop: 10 },
  followUpItem: { backgroundColor: '#F6F8FA', borderRadius: 12, padding: 10, marginTop: 10 },
  dayTitle: { color: C.navy, fontSize: 16, fontWeight: '800', marginBottom: 6 },
  periodRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 6 },
  periodNo: {
    width: 36,
    textAlign: 'center',
    color: C.tealDark,
    fontWeight: '800',
    backgroundColor: '#E7F5F3',
    borderRadius: 8,
    paddingVertical: 4,
    overflow: 'hidden',
  },
});
