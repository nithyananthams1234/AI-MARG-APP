import { useState } from 'react';
import { ActivityIndicator, Pressable, Text, TextInput, View } from 'react-native';

import { InlineNotice, StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useCreateStep, useFollowUps, useStepStatus, useSteps } from '@/hooks/api';
import type { ActionPlanResponse, ActionPlanStepResponse } from '@/lib/api/generated';
import { formatDate } from '@/lib/format';

import { planStyles as styles } from './plan-styles';
import { STEP_EDITABLE_PLAN_STATUSES, isValidDate } from './plan-utils';

type Props = {
  plan: ActionPlanResponse;
  onCreateFollowUp: (step: ActionPlanStepResponse) => void;
};

export function PlanSteps({ plan, onCreateFollowUp }: Props) {
  const steps = useSteps(plan.id);
  const followUps = useFollowUps();
  const stepStatus = useStepStatus();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [completingId, setCompletingId] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const canAdd = STEP_EDITABLE_PLAN_STATUSES.includes(plan.status);
  const followUpCount = (stepId: string) => (followUps.data ?? []).filter((f) => f.action_plan_step_id === stepId).length;

  const setStatus = async (step: ActionPlanStepResponse, status: 'in_progress' | 'completed' | 'cancelled', completion_notes?: string) => {
    setBusyId(step.id);
    setError(null);
    try {
      await stepStatus.mutateAsync({ id: step.id, status, completion_notes: completion_notes?.trim() || null });
      setCompletingId(null);
      setNotes('');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <View>
      <View style={styles.sectionDivider} />
      <View style={[styles.sectionHeader, { marginTop: 12 }]}>
        <Text style={styles.sectionTitle}>Steps</Text>
        {canAdd && !adding ? (
          <Pressable style={styles.primarySmallButton} onPress={() => setAdding(true)} accessibilityRole="button" accessibilityLabel="Add step">
            <Text style={styles.primarySmallButtonText}>+ Add step</Text>
          </Pressable>
        ) : null}
      </View>
      {!canAdd ? <Text style={styles.formHint}>Steps can be added once the plan is approved.</Text> : null}

      {adding ? <AddStepForm plan={plan} onDone={() => setAdding(false)} /> : null}
      {error ? <View style={{ marginTop: 10 }}><InlineNotice tone="danger" text={error} /></View> : null}

      {steps.isLoading ? (
        <ActivityIndicator color={C.teal} style={{ marginTop: 12 }} />
      ) : steps.error && !steps.data ? (
        <View style={{ marginTop: 10 }}>
          <InlineNotice tone="danger" text={`Could not load steps: ${(steps.error as Error).message}`} />
          <Pressable style={styles.secondarySmallButton} onPress={() => void steps.refetch()} accessibilityRole="button">
            <Text style={styles.secondarySmallButtonText}>Try again</Text>
          </Pressable>
        </View>
      ) : (steps.data ?? []).length === 0 ? (
        <Text style={styles.detailValue}>No steps yet.</Text>
      ) : (
        (steps.data ?? []).map((step) => {
          const busy = busyId === step.id;
          const open = step.status === 'pending' || step.status === 'in_progress';
          const count = followUpCount(step.id);
          return (
            <View key={step.id} style={styles.stepCard}>
              <View style={styles.planTopRow}>
                <Text style={styles.stepTitle}>{step.title}</Text>
                <StatusBadge status={step.status} />
              </View>
              <Text style={styles.detailValue}>{step.description}</Text>
              <Text style={styles.stepMeta}>
                {step.responsible_person} · due {formatDate(step.due_date)} · {count} follow-up{count === 1 ? '' : 's'}
              </Text>
              {step.completion_notes ? <Text style={styles.stepMeta}>Notes: {step.completion_notes}</Text> : null}

              {completingId === step.id ? (
                <View>
                  <Text style={styles.inputLabel}>Completion notes (optional)</Text>
                  <TextInput style={[styles.input, styles.multilineInput]} value={notes} onChangeText={setNotes} multiline textAlignVertical="top" placeholder="What was achieved?" placeholderTextColor={C.muted} accessibilityLabel="Completion notes" />
                  <View style={[styles.actionButtons, { marginTop: 10 }]}>
                    <SmallButton label="Confirm completion" onPress={() => void setStatus(step, 'completed', notes)} busy={busy} primary />
                    <SmallButton label="Back" onPress={() => setCompletingId(null)} busy={busy} />
                  </View>
                </View>
              ) : open ? (
                <View style={[styles.actionButtons, { marginTop: 10 }]}>
                  {step.status === 'pending' ? <SmallButton label="Start" onPress={() => void setStatus(step, 'in_progress')} busy={busy} primary /> : null}
                  {step.status === 'in_progress' ? (
                    <SmallButton label="Complete" onPress={() => { setNotes(''); setCompletingId(step.id); }} busy={busy} primary />
                  ) : null}
                  <SmallButton label="Create follow-up" onPress={() => onCreateFollowUp(step)} busy={busy} />
                  <SmallButton label="Cancel step" onPress={() => void setStatus(step, 'cancelled')} busy={busy} danger />
                </View>
              ) : null}
            </View>
          );
        })
      )}
    </View>
  );
}

function AddStepForm({ plan, onDone }: { plan: ActionPlanResponse; onDone: () => void }) {
  const createStep = useCreateStep();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [responsible, setResponsible] = useState(plan.responsible_person);
  const [dueDate, setDueDate] = useState(plan.due_date);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (title.trim().length < 3 || title.trim().length > 200) return setError('Step title must be between 3 and 200 characters.');
    if (description.trim().length < 3) return setError('Description must be at least 3 characters.');
    if (responsible.trim().length < 2) return setError('Responsible person must be at least 2 characters.');
    if (!isValidDate(dueDate)) return setError('Enter a valid due date (YYYY-MM-DD).');
    setError(null);
    try {
      await createStep.mutateAsync({
        action_plan_id: plan.id,
        title: title.trim(),
        description: description.trim(),
        responsible_person: responsible.trim(),
        due_date: dueDate,
      });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <View style={styles.stepCard}>
      <Text style={styles.stepTitle}>New step</Text>
      <Text style={styles.inputLabel}>Title *</Text>
      <TextInput style={styles.input} value={title} onChangeText={setTitle} placeholder="e.g. Model a read-aloud lesson" placeholderTextColor={C.muted} accessibilityLabel="Step title" />
      <Text style={styles.inputLabel}>Description *</Text>
      <TextInput style={[styles.input, styles.multilineInput]} value={description} onChangeText={setDescription} multiline textAlignVertical="top" placeholderTextColor={C.muted} placeholder="What needs to happen" accessibilityLabel="Step description" />
      <View style={styles.row}>
        <View style={{ flex: 1 }}>
          <Text style={styles.inputLabel}>Responsible *</Text>
          <TextInput style={styles.input} value={responsible} onChangeText={setResponsible} placeholderTextColor={C.muted} accessibilityLabel="Responsible person" />
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.inputLabel}>Due date *</Text>
          <TextInput style={styles.input} value={dueDate} onChangeText={setDueDate} placeholder="YYYY-MM-DD" placeholderTextColor={C.muted} autoCapitalize="none" accessibilityLabel="Step due date" />
        </View>
      </View>
      {error ? <View style={{ marginTop: 10 }}><InlineNotice tone="danger" text={error} /></View> : null}
      <View style={[styles.actionButtons, { marginTop: 12 }]}>
        <SmallButton label="Save step" onPress={() => void submit()} busy={createStep.isPending} primary />
        <SmallButton label="Cancel" onPress={onDone} busy={createStep.isPending} />
      </View>
    </View>
  );
}

export function SmallButton({ label, onPress, busy, primary, danger }: { label: string; onPress: () => void; busy?: boolean; primary?: boolean; danger?: boolean }) {
  const box = primary ? styles.primarySmallButton : danger ? styles.dangerSmallButton : styles.secondarySmallButton;
  const text = primary ? styles.primarySmallButtonText : danger ? styles.dangerSmallButtonText : styles.secondarySmallButtonText;
  return (
    <Pressable
      style={[box, busy && styles.disabled]}
      onPress={onPress}
      disabled={busy}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!busy, busy: !!busy }}
    >
      <Text style={text}>{label}</Text>
    </Pressable>
  );
}
