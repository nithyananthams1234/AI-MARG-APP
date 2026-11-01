import { useMemo, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useCreateFollowUp, useSchoolTeachers } from '@/hooks/api';
import { useRecommendationContext, useTeachers } from '@/hooks/api-cycle';
import type { ActionPlanResponse, ActionPlanStepResponse, FollowUpResponse } from '@/lib/api/generated';
import { formatDate } from '@/lib/format';

import { fuStyles as styles } from './followup-styles';

type Props = {
  visible: boolean;
  initialStepId?: string;
  plans: ActionPlanResponse[];
  steps: ActionPlanStepResponse[];
  stepsLoading: boolean;
  onClose: () => void;
  onCreated: (fu: FollowUpResponse) => void;
};

const OPEN_STEP = ['pending', 'in_progress'];

/**
 * Mounted only while open (and re-mounted once steps have loaded), so the
 * initial plan/step selection is computed from fresh data each time.
 */
export function FollowUpCreateModal(props: Props) {
  if (!props.visible) return null;
  return <FollowUpCreateForm key={`${props.initialStepId ?? 'none'}:${props.stepsLoading ? 'loading' : 'ready'}`} {...props} />;
}

function FollowUpCreateForm({ initialStepId, plans, steps, stepsLoading, onClose, onCreated }: Props) {
  const createFollowUp = useCreateFollowUp();
  const { resolve } = useRecommendationContext();
  const initial = initialStepId ? steps.find((s) => s.id === initialStepId) : undefined;
  const [planId, setPlanId] = useState<string | null>(initial?.action_plan_id ?? null);
  const [stepId, setStepId] = useState<string | null>(initial && OPEN_STEP.includes(initial.status) ? initial.id : null);
  const [chosenTeacherId, setTeacherId] = useState<string | null>(null);
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);

  const openSteps = useMemo(() => steps.filter((s) => OPEN_STEP.includes(s.status)), [steps]);
  const planOptions = useMemo(() => plans.filter((p) => openSteps.some((s) => s.action_plan_id === p.id)), [plans, openSteps]);
  const stepOptions = openSteps.filter((s) => s.action_plan_id === planId);

  const plan = plans.find((p) => p.id === planId);
  const context = resolve(plan?.recommendation_id);
  const schoolTeachers = useSchoolTeachers(context.school?.id);
  const allTeachers = useTeachers();
  // Prefer teachers of the plan's school; fall back to all teachers in the mentor's schools.
  const teachers = context.school ? schoolTeachers : allTeachers;

  // Default to the teacher who was observed, when known.
  const teacherId = chosenTeacherId ?? context.observation?.teacher_id ?? null;

  const submit = async () => {
    if (!stepId) return setError('Choose an action plan step.');
    if (!teacherId) return setError('Choose a teacher.');
    if (description.trim().length < 3) return setError('Describe what the teacher should do (at least 3 characters).');
    setError(null);
    try {
      const fu = await createFollowUp.mutateAsync({ action_plan_step_id: stepId, teacher_id: teacherId, description: description.trim() });
      onCreated(fu);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView style={styles.modalOverlay} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={[styles.modalCard, styles.wide]}>
          <View style={styles.modalHandle} />
          <View style={styles.modalHeader}>
            <View style={styles.modalHeadingContent}>
              <Text style={styles.modalEyebrow}>NEW FOLLOW-UP</Text>
              <Text style={styles.modalTitle} accessibilityRole="header">Create follow-up</Text>
            </View>
            <Pressable style={styles.closeButton} onPress={onClose} accessibilityRole="button" accessibilityLabel="Close">
              <Text style={styles.closeButtonText}>×</Text>
            </Pressable>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.modalScrollContent} keyboardShouldPersistTaps="handled">
            <View style={styles.detailSection}>
              <Text style={styles.detailLabel}>ACTION PLAN</Text>
              {stepsLoading ? (
                <ActivityIndicator color={C.teal} />
              ) : planOptions.length === 0 ? (
                <InlineNotice tone="warning" text="No plan has an open step. Add a step to an approved action plan first." />
              ) : (
                <View style={styles.optionList} accessibilityRole="radiogroup">
                  {planOptions.map((p) => (
                    <Option key={p.id} label={p.title} sub={resolve(p.recommendation_id).school?.name} active={planId === p.id} onPress={() => { setPlanId(p.id); setStepId(null); setTeacherId(null); }} />
                  ))}
                </View>
              )}
            </View>

            {planId ? (
              <View style={styles.detailSection}>
                <Text style={styles.detailLabel}>STEP</Text>
                <View style={styles.optionList} accessibilityRole="radiogroup">
                  {stepOptions.map((s) => (
                    <Option key={s.id} label={s.title} sub={`${s.responsible_person} · due ${formatDate(s.due_date)}`} active={stepId === s.id} onPress={() => setStepId(s.id)} />
                  ))}
                </View>
              </View>
            ) : null}

            {planId ? (
              <View style={styles.detailSection}>
                <Text style={styles.detailLabel}>TEACHER{context.school ? ` · ${context.school.name.toUpperCase()}` : ''}</Text>
                {teachers.isLoading ? (
                  <ActivityIndicator color={C.teal} />
                ) : teachers.error && !teachers.data ? (
                  <InlineNotice tone="danger" text={`Could not load teachers: ${(teachers.error as Error).message}`} />
                ) : (teachers.data ?? []).length === 0 ? (
                  <InlineNotice tone="warning" text="No teachers found for this school." />
                ) : (
                  <View style={styles.optionList} accessibilityRole="radiogroup">
                    {(teachers.data ?? []).map((t) => (
                      <Option
                        key={t.id}
                        label={t.full_name}
                        sub={t.id === context.observation?.teacher_id ? 'Observed teacher' : t.employee_code ?? undefined}
                        active={teacherId === t.id}
                        onPress={() => setTeacherId(t.id)}
                      />
                    ))}
                  </View>
                )}
              </View>
            ) : null}

            <View style={styles.detailSection}>
              <Text style={styles.detailLabel}>WHAT SHOULD THE TEACHER DO?</Text>
              <TextInput
                style={[styles.input, styles.multiline]}
                value={description}
                onChangeText={setDescription}
                multiline
                placeholder="e.g. Use three inference questions in each read-aloud this week"
                placeholderTextColor={C.muted}
                accessibilityLabel="Follow-up description"
              />
            </View>

            {error ? <View style={{ marginTop: 10 }}><InlineNotice tone="danger" text={error} /></View> : null}

            <Pressable
              style={[styles.primaryAction, createFollowUp.isPending && styles.disabled]}
              onPress={() => void submit()}
              disabled={createFollowUp.isPending}
              accessibilityRole="button"
              accessibilityState={{ disabled: createFollowUp.isPending, busy: createFollowUp.isPending }}
            >
              {createFollowUp.isPending ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.primaryActionText}>Create follow-up</Text>}
            </Pressable>
            <Pressable style={styles.secondaryAction} onPress={onClose} accessibilityRole="button">
              <Text style={styles.secondaryActionText}>Cancel</Text>
            </Pressable>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

function Option({ label, sub, active, onPress }: { label: string; sub?: string; active: boolean; onPress: () => void }) {
  return (
    <Pressable
      style={[styles.option, active && styles.optionActive]}
      onPress={onPress}
      accessibilityRole="radio"
      accessibilityState={{ selected: active }}
      accessibilityLabel={sub ? `${label}, ${sub}` : label}
    >
      <Text style={[styles.optionText, active && styles.optionTextActive]}>{label}</Text>
      {sub ? <Text style={styles.optionSub}>{sub}</Text> : null}
    </Pressable>
  );
}
