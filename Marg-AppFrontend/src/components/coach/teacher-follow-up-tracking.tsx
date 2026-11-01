import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FollowUpDetailModal } from '@/components/followups/followup-detail-modal';
import { FollowUpCreateModal } from '@/components/followups/followup-create-modal';
import { FollowUpStatusBadge } from '@/components/followups/followup-card';
import { Button, Card, EmptyState, ErrorState, InlineNotice, LoadingState, StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import {
  useFollowUps,
  useGaps,
  useObservations,
  usePlans,
  useRecommendations,
  useSchoolTeachers,
  useSchools,
  useStepStatus,
  useVisits,
} from '@/hooks/api';
import { useStepsForPlans } from '@/hooks/api-cycle';
import type { ActionPlanStepResponse } from '@/lib/api/generated';
import { formatDateTime } from '@/lib/format';

type Props = {
  schoolId?: string;
};

const RESPONDED_STATUSES = new Set(['teacher_responded', 'evidence_submitted', 'mentor_verified', 'needs_revision', 'closed']);

export function TeacherFollowUpTracking({ schoolId }: Props) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Teacher Follow-up &amp; Tracking</Text>
      <Text style={styles.description}>
        Follow-ups are linked to existing action-plan steps and remain available when you return to this school.
      </Text>
      <InlineNotice
        tone="info"
        text="The current API does not persist WhatsApp draft/delivery status or next follow-up dates. Opening WhatsApp does not confirm delivery; response dates shown are when recorded in the system."
      />
      {schoolId ? <SchoolTrackingRecords schoolId={schoolId} /> : (
        <EmptyState title="Select a school" message="Choose a school to view its persisted follow-up records." />
      )}
    </View>
  );
}

function SchoolTrackingRecords({ schoolId }: { schoolId: string }) {
  const plans = usePlans();
  const recommendations = useRecommendations();
  const gaps = useGaps();
  const observations = useObservations();
  const visits = useVisits();
  const schools = useSchools();
  const followUps = useFollowUps();
  const teachers = useSchoolTeachers(schoolId);
  const stepStatus = useStepStatus();

  const schoolPlans = useMemo(() => {
    const recommendationById = new Map((recommendations.data ?? []).map((item) => [item.id, item]));
    const gapById = new Map((gaps.data ?? []).map((item) => [item.id, item]));
    const observationById = new Map((observations.data ?? []).map((item) => [item.id, item]));
    const visitById = new Map((visits.data ?? []).map((item) => [item.id, item]));
    const schoolById = new Map((schools.data ?? []).map((item) => [item.id, item]));

    return (plans.data ?? []).filter((plan) => {
      const recommendation = recommendationById.get(plan.recommendation_id);
      const gap = recommendation ? gapById.get(recommendation.learning_gap_id) : undefined;
      const observation = gap ? observationById.get(gap.observation_id) : undefined;
      const visit = observation ? visitById.get(observation.school_visit_id) : undefined;
      return visit ? schoolById.get(visit.school_id)?.id === schoolId : false;
    });
  }, [schoolId, plans.data, recommendations.data, gaps.data, observations.data, visits.data, schools.data]);

  const planIds = useMemo(() => schoolPlans.map((plan) => plan.id), [schoolPlans]);
  const stepsQuery = useStepsForPlans(planIds);
  const schoolStepIds = useMemo(() => new Set(stepsQuery.steps.map((step) => step.id)), [stepsQuery.steps]);
  const schoolFollowUps = useMemo(
    () => (followUps.data ?? [])
      .filter((item) => schoolStepIds.has(item.action_plan_step_id))
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    [followUps.data, schoolStepIds],
  );
  const planById = useMemo(() => new Map(schoolPlans.map((plan) => [plan.id, plan])), [schoolPlans]);
  const stepById = useMemo(() => new Map(stepsQuery.steps.map((step) => [step.id, step])), [stepsQuery.steps]);
  const teacherById = useMemo(() => new Map((teachers.data ?? []).map((teacher) => [teacher.id, teacher])), [teachers.data]);

  const [createVisible, setCreateVisible] = useState(false);
  const [selectedFollowUpId, setSelectedFollowUpId] = useState<string | null>(null);
  const [stepError, setStepError] = useState<string | null>(null);
  const [busyStepId, setBusyStepId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: 'success' | 'info'; text: string } | null>(null);

  const selectedFollowUp = schoolFollowUps.find((item) => item.id === selectedFollowUpId) ?? null;
  const dataQueries = [plans, recommendations, gaps, observations, visits, schools, followUps];
  const loading = dataQueries.some((query) => query.isLoading) || stepsQuery.isLoading;
  const error = dataQueries.find((query) => query.error)?.error ?? stepsQuery.error;
  const ready = dataQueries.every((query) => query.data !== undefined) && !stepsQuery.error && !stepsQuery.isLoading;
  const openSteps = stepsQuery.steps.filter((step) => step.status === 'pending' || step.status === 'in_progress');

  const retry = () => {
    void Promise.all([
      plans.refetch(),
      recommendations.refetch(),
      gaps.refetch(),
      observations.refetch(),
      visits.refetch(),
      schools.refetch(),
      followUps.refetch(),
      teachers.refetch(),
      stepsQuery.refetch(),
    ]);
  };

  const setActionStatus = async (step: ActionPlanStepResponse, status: 'in_progress' | 'completed') => {
    setStepError(null);
    setBusyStepId(step.id);
    try {
      await stepStatus.mutateAsync({ id: step.id, status });
    } catch (e) {
      setStepError((e as Error).message);
    } finally {
      setBusyStepId(null);
    }
  };

  return (
    <View style={styles.records}>
      {loading && !ready ? (
        <LoadingState label="Loading teacher follow-ups…" />
      ) : !ready ? (
        <ErrorState error={error} onRetry={retry} />
      ) : (
        <>
          {error ? <InlineNotice tone="warning" text="Some follow-up data could not be refreshed; showing the records currently available." /> : null}
          {teachers.error ? <InlineNotice tone="warning" text="Teacher names could not be refreshed; follow-up records are still available." /> : null}
          {stepError ? <InlineNotice tone="danger" text={stepError} /> : null}
          {notice ? <InlineNotice tone={notice.tone} text={notice.text} /> : null}

          <View style={styles.actionsRow}>
            <Text style={styles.lastActivity}>
              {schoolFollowUps[0]
                ? `Last recorded activity: ${formatDateTime(schoolFollowUps[0].updated_at)}`
                : 'No follow-up activity recorded yet.'}
            </Text>
            <Button
              label="New follow-up"
              variant="secondary"
              onPress={() => setCreateVisible(true)}
              disabled={openSteps.length === 0}
            />
          </View>
          {openSteps.length === 0 ? (
            <Text style={styles.hint}>A follow-up can be created only for an existing pending or in-progress action-plan step for this school.</Text>
          ) : null}

          {schoolFollowUps.length === 0 ? (
            <EmptyState
              title="No follow-up records"
              message="No persisted follow-ups are linked to this school yet. Create one from an existing action-plan step."
            />
          ) : (
            <View style={styles.recordList}>
              {schoolFollowUps.map((item) => {
                const step = stepById.get(item.action_plan_step_id);
                const teacher = teacherById.get(item.teacher_id);
                const plan = step ? planById.get(step.action_plan_id) : undefined;
                const responded = RESPONDED_STATUSES.has(item.status) || !!item.responded_at;
                const busy = busyStepId === step?.id;

                return (
                  <Card key={item.id} style={styles.recordCard}>
                    <View style={styles.cardHeading}>
                      <Text style={styles.teacherName} numberOfLines={1}>{teacher?.full_name ?? 'Teacher record'}</Text>
                      <FollowUpStatusBadge status={item.status} />
                    </View>
                    <Text style={styles.actionDescription}>{item.description}</Text>
                    <Text style={styles.meta}>{plan?.title ?? 'Action plan'}{step ? ` · ${step.title}` : ''}</Text>

                    <View style={styles.statusRow}>
                      <View style={styles.statusColumn}>
                        <Text style={styles.fieldLabel}>TEACHER RESPONSE</Text>
                        <StatusBadge status={responded ? 'teacher_responded' : 'pending'} label={responded ? 'Responded' : 'Not Responded'} />
                      </View>
                      <View style={styles.statusColumn}>
                        <Text style={styles.fieldLabel}>ACTION STATUS · MENTOR RECORDED</Text>
                        <StatusBadge status={step?.status ?? 'unknown'} label={actionStatusLabel(step?.status)} />
                      </View>
                    </View>

                    {item.teacher_response ? (
                      <View style={styles.noteBlock}>
                        <Text style={styles.fieldLabel}>LATEST TEACHER RESPONSE / EVIDENCE RECORD</Text>
                        <Text style={styles.bodyText}>{item.teacher_response}</Text>
                        {item.responded_at ? <Text style={styles.meta}>Recorded {formatDateTime(item.responded_at)}</Text> : null}
                      </View>
                    ) : null}
                    {item.mentor_notes ? (
                      <View style={styles.noteBlock}>
                        <Text style={styles.fieldLabel}>MENTOR REVIEW NOTES</Text>
                        <Text style={styles.bodyText}>{item.mentor_notes}</Text>
                      </View>
                    ) : null}
                    {item.status === 'mentor_verified' || item.status === 'closed' ? (
                      <Text style={styles.meta}>Mentor verified{item.verified_at ? ` · ${formatDateTime(item.verified_at)}` : ''}</Text>
                    ) : null}
                    <Text style={styles.meta}>Last recorded activity · {formatDateTime(item.updated_at)}</Text>

                    {step?.status === 'pending' ? (
                      <Button
                        label="Mark action In Progress"
                        variant="secondary"
                        onPress={() => void setActionStatus(step, 'in_progress')}
                        loading={busy}
                        style={styles.actionButton}
                      />
                    ) : step?.status === 'in_progress' ? (
                      <Button
                        label="Mark action Completed"
                        variant="secondary"
                        onPress={() => void setActionStatus(step, 'completed')}
                        loading={busy}
                        style={styles.actionButton}
                      />
                    ) : null}
                    {step?.status === 'completed' ? (
                      <Text style={styles.verificationHint}>
                        Action completion is mentor-recorded; it is separate from a teacher report and from mentor verification of follow-up evidence.
                      </Text>
                    ) : null}
                    <Pressable
                      onPress={() => setSelectedFollowUpId(item.id)}
                      accessibilityRole="button"
                      accessibilityLabel={`Update follow-up for ${teacher?.full_name ?? 'teacher'}`}
                      style={styles.detailButton}
                    >
                      <Text style={styles.detailButtonText}>Record interaction or review evidence</Text>
                    </Pressable>
                  </Card>
                );
              })}
            </View>
          )}

          <FollowUpCreateModal
            visible={createVisible}
            plans={schoolPlans}
            steps={stepsQuery.steps}
            stepsLoading={stepsQuery.isLoading}
            onClose={() => setCreateVisible(false)}
            onCreated={() => {
              setCreateVisible(false);
              setNotice({ tone: 'success', text: 'Follow-up saved.' });
            }}
          />
          <FollowUpDetailModal
            item={selectedFollowUp}
            lookups={{
              step: (id) => stepById.get(id),
              plan: (id) => planById.get(id),
              teacher: (id) => teacherById.get(id),
            }}
            onClose={() => setSelectedFollowUpId(null)}
            onMessage={(tone, text) => setNotice({ tone, text })}
          />
        </>
      )}
    </View>
  );
}

function actionStatusLabel(status?: string) {
  switch (status) {
    case 'pending':
      return 'Not Started';
    case 'in_progress':
      return 'In Progress';
    case 'completed':
      return 'Completed';
    case 'cancelled':
      return 'Cancelled';
    default:
      return 'Unavailable';
  }
}

const styles = StyleSheet.create({
  section: { gap: 10, marginTop: 16 },
  records: { gap: 10 },
  sectionTitle: { color: C.navy, fontSize: 18, fontWeight: '800' },
  description: { color: C.secondaryText, fontSize: 13, lineHeight: 18 },
  actionsRow: { gap: 10 },
  lastActivity: { color: C.secondaryText, fontSize: 12 },
  hint: { color: C.secondaryText, fontSize: 12, lineHeight: 17 },
  recordList: { gap: 9 },
  recordCard: { gap: 8, borderColor: C.border },
  cardHeading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  teacherName: { flex: 1, color: C.navy, fontSize: 15, fontWeight: '800' },
  actionDescription: { color: C.text, fontSize: 14, lineHeight: 19, fontWeight: '600' },
  meta: { color: C.secondaryText, fontSize: 12, lineHeight: 17 },
  statusRow: { flexDirection: 'row', gap: 10 },
  statusColumn: { flex: 1, gap: 5 },
  fieldLabel: { color: C.tealDark, fontSize: 10, fontWeight: '800' },
  noteBlock: { gap: 4, padding: 9, backgroundColor: '#F6F9FC', borderRadius: 9 },
  bodyText: { color: C.text, fontSize: 13, lineHeight: 18 },
  actionButton: { alignSelf: 'flex-start' },
  verificationHint: { color: C.secondaryText, fontSize: 11, lineHeight: 16 },
  detailButton: { alignSelf: 'flex-start', paddingVertical: 6 },
  detailButtonText: { color: C.tealDark, fontSize: 13, fontWeight: '700' },
});
