import { useMemo, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useGaps, useRecommendations } from '@/hooks/api';
import type { ActionPlanCreate, ActionPlanResponse } from '@/lib/api/generated';

import { planStyles as styles } from './plan-styles';
import { isValidDate, todayLocal } from './plan-utils';

type Props = {
  visible: boolean;
  /** When set, the form edits this (draft) plan; otherwise it creates a plan. */
  plan: ActionPlanResponse | null;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (body: ActionPlanCreate) => void;
};

/** Mounted only while open, so every opening starts from fresh initial state. */
export function PlanFormModal(props: Props) {
  return props.visible ? <PlanForm key={props.plan?.id ?? 'new'} {...props} /> : null;
}

function PlanForm({ plan, saving, error, onClose, onSubmit }: Props) {
  const recs = useRecommendations({ status: 'mentor_approved' });
  const gaps = useGaps();
  const gapTitle = useMemo(() => {
    const map = new Map((gaps.data ?? []).map((g) => [g.id, g.title]));
    return (id: string) => map.get(id);
  }, [gaps.data]);

  const [recommendationId, setRecommendationId] = useState<string | null>(plan?.recommendation_id ?? null);
  const [title, setTitle] = useState(plan?.title ?? '');
  const [description, setDescription] = useState(plan?.description ?? '');
  const [responsible, setResponsible] = useState(plan?.responsible_person ?? '');
  const [startDate, setStartDate] = useState(plan?.start_date ?? todayLocal());
  const [dueDate, setDueDate] = useState(plan?.due_date ?? '');
  const [formError, setFormError] = useState<string | null>(null);

  const submit = () => {
    if (!recommendationId) return setFormError('Choose an approved recommendation for this plan.');
    const t = title.trim();
    if (t.length < 3 || t.length > 200) return setFormError('Title must be between 3 and 200 characters.');
    if (description.trim().length < 3) return setFormError('Description must be at least 3 characters.');
    const r = responsible.trim();
    if (r.length < 2 || r.length > 150) return setFormError('Responsible person must be between 2 and 150 characters.');
    if (!isValidDate(startDate)) return setFormError('Enter a valid start date (YYYY-MM-DD).');
    if (!isValidDate(dueDate)) return setFormError('Enter a valid due date (YYYY-MM-DD).');
    if (dueDate < startDate) return setFormError('The due date cannot be before the start date.');
    setFormError(null);
    onSubmit({
      recommendation_id: recommendationId,
      title: t,
      description: description.trim(),
      responsible_person: r,
      start_date: startDate,
      due_date: dueDate,
    });
  };

  const shownError = formError ?? error;

  return (
    <Modal visible animationType="slide" transparent onRequestClose={onClose}>
      <KeyboardAvoidingView style={styles.modalOverlay} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <View style={[styles.formModal, styles.formModalWide]}>
          <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
            <View style={styles.modalHeader}>
              <View>
                <Text style={styles.modalSubtitle}>{plan ? 'Draft plan' : 'New action plan'}</Text>
                <Text style={styles.modalTitle} accessibilityRole="header">{plan ? 'Edit action plan' : 'Create action plan'}</Text>
              </View>
              <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" hitSlop={8}>
                <Text style={styles.closeButton}>×</Text>
              </Pressable>
            </View>

            <Text style={styles.inputLabel}>Approved recommendation *</Text>
            {plan ? (
              <View style={styles.contextBox}>
                <Text style={styles.contextLabel}>RECOMMENDATION</Text>
                <Text style={styles.contextValue}>
                  {recs.data?.find((x) => x.id === plan.recommendation_id)?.title ?? 'Linked recommendation'}
                </Text>
              </View>
            ) : recs.isLoading ? (
              <ActivityIndicator color={C.teal} />
            ) : recs.error && !recs.data ? (
              <InlineNotice tone="danger" text={`Could not load recommendations: ${(recs.error as Error).message}`} />
            ) : (recs.data ?? []).length === 0 ? (
              <InlineNotice
                tone="warning"
                text="No mentor-approved recommendations yet. Approve a recommendation from an observation's learning gap first."
              />
            ) : (
              <View style={styles.focusOptions} accessibilityRole="radiogroup">
                {(recs.data ?? []).map((rec) => {
                  const active = recommendationId === rec.id;
                  const gap = gapTitle(rec.learning_gap_id);
                  return (
                    <Pressable
                      key={rec.id}
                      onPress={() => setRecommendationId(rec.id)}
                      style={[styles.focusOption, active && styles.focusOptionActive]}
                      accessibilityRole="radio"
                      accessibilityState={{ selected: active }}
                      accessibilityLabel={`${rec.title}${gap ? `, learning gap: ${gap}` : ''}`}
                    >
                      <Text style={[styles.focusOptionText, active && styles.focusOptionTextActive]}>{rec.title}</Text>
                      {gap ? <Text style={styles.modalSubtitle}>Learning gap: {gap}</Text> : null}
                    </Pressable>
                  );
                })}
              </View>
            )}

            <Text style={styles.inputLabel}>Plan title *</Text>
            <TextInput style={styles.input} value={title} onChangeText={setTitle} placeholder="e.g. Daily read-aloud with inference questions" placeholderTextColor={C.muted} maxLength={200} accessibilityLabel="Plan title" />

            <Text style={styles.inputLabel}>Description *</Text>
            <TextInput style={[styles.input, styles.multilineInput]} value={description} onChangeText={setDescription} placeholder="What will be done and why" placeholderTextColor={C.muted} multiline textAlignVertical="top" accessibilityLabel="Description" />

            <Text style={styles.inputLabel}>Responsible person *</Text>
            <TextInput style={styles.input} value={responsible} onChangeText={setResponsible} placeholder="Teacher or staff name" placeholderTextColor={C.muted} maxLength={150} accessibilityLabel="Responsible person" />

            <View style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={styles.inputLabel}>Start date *</Text>
                <TextInput style={styles.input} value={startDate} onChangeText={setStartDate} placeholder="YYYY-MM-DD" placeholderTextColor={C.muted} autoCapitalize="none" accessibilityLabel="Start date" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.inputLabel}>Due date *</Text>
                <TextInput style={styles.input} value={dueDate} onChangeText={setDueDate} placeholder="YYYY-MM-DD" placeholderTextColor={C.muted} autoCapitalize="none" accessibilityLabel="Due date" />
              </View>
            </View>

            <Text style={styles.formHint}>New plans start as drafts. Submit a draft for approval once it is ready.</Text>

            {shownError ? <View style={{ marginTop: 12 }}><InlineNotice tone="danger" text={shownError} /></View> : null}

            <Pressable
              style={[styles.saveButton, saving && styles.disabled]}
              onPress={submit}
              disabled={saving}
              accessibilityRole="button"
              accessibilityState={{ disabled: saving, busy: saving }}
            >
              {saving ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.saveButtonText}>{plan ? 'SAVE CHANGES' : 'CREATE PLAN'}</Text>}
            </Pressable>
            <Pressable style={styles.cancelFormButton} onPress={onClose} accessibilityRole="button">
              <Text style={styles.cancelFormText}>Cancel</Text>
            </Pressable>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}
