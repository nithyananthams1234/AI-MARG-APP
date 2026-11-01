import { useState } from 'react';
import { Modal, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { usePlanStatus } from '@/hooks/api';
import { useDeletePlan, type PlanContext } from '@/hooks/api-cycle';
import type { ActionPlanResponse, ActionPlanStepResponse } from '@/lib/api/generated';
import { confirmAction } from '@/lib/dialogs';
import { formatDate, formatDateTime } from '@/lib/format';

import { PlanStatusBadge } from './plan-card';
import { PlanSteps, SmallButton } from './plan-steps';
import { planStyles as styles } from './plan-styles';
import { PLAN_TRANSITIONS, TRANSITION_LABELS, isPlanDeletable, isPlanEditable, isPlanPastDue, type PlanTarget } from './plan-utils';

type Props = {
  plan: ActionPlanResponse | null;
  context: PlanContext;
  onClose: () => void;
  onEdit: (plan: ActionPlanResponse) => void;
  onCreateFollowUp: (plan: ActionPlanResponse, step: ActionPlanStepResponse) => void;
  onMessage: (text: string) => void;
};

export function PlanDetailModal({ plan, context, onClose, onEdit, onCreateFollowUp, onMessage }: Props) {
  const planStatus = usePlanStatus();
  const deletePlan = useDeletePlan();
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (!plan) return null;
  const transitions = PLAN_TRANSITIONS[plan.status] ?? [];
  const busy = planStatus.isPending || deletePlan.isPending;
  const pastDue = isPlanPastDue(plan);

  const changeStatus = (status: PlanTarget) => {
    const run = async () => {
      setError(null);
      try {
        await planStatus.mutateAsync({ id: plan.id, status, mentor_comment: comment.trim() || null });
        setComment('');
        onMessage(`Plan updated: ${TRANSITION_LABELS[status].toLowerCase()}.`);
      } catch (e) {
        setError((e as Error).message);
      }
    };
    if (status === 'cancelled') confirmAction('Cancel this plan?', 'A cancelled plan cannot be reopened.', () => void run(), 'Cancel plan');
    else void run();
  };

  const remove = () =>
    confirmAction('Delete this plan?', `“${plan.title}” will be permanently deleted.`, async () => {
      setError(null);
      try {
        await deletePlan.mutateAsync(plan.id);
        onMessage('Plan deleted.');
        onClose();
      } catch (e) {
        setError((e as Error).message);
      }
    }, 'Delete');

  return (
    <Modal visible animationType="fade" transparent onRequestClose={onClose}>
      <View style={styles.detailOverlay}>
        <View style={[styles.detailModal, styles.detailModalWide]}>
          <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
            <View style={styles.modalHeader}>
              <View style={{ flex: 1 }}>
                <PlanStatusBadge status={plan.status} />
                <Text style={styles.modalTitle} accessibilityRole="header">{plan.title}</Text>
              </View>
              <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" hitSlop={8}>
                <Text style={styles.closeButton}>×</Text>
              </Pressable>
            </View>

            <View style={styles.contextBox}>
              <Text style={styles.contextLabel}>RECOMMENDATION</Text>
              <Text style={styles.contextValue}>{context.recommendation?.title ?? '—'}</Text>
              <Text style={[styles.contextLabel, { marginTop: 8 }]}>LEARNING GAP</Text>
              <Text style={styles.contextValue}>{context.gap?.title ?? '—'}</Text>
              {context.school ? (
                <>
                  <Text style={[styles.contextLabel, { marginTop: 8 }]}>SCHOOL</Text>
                  <Text style={styles.contextValue}>{context.school.name}</Text>
                </>
              ) : null}
            </View>

            <Text style={styles.detailLabel}>Description</Text>
            <Text style={styles.detailValue}>{plan.description}</Text>
            <Text style={styles.detailLabel}>Responsible person</Text>
            <Text style={styles.detailValue}>{plan.responsible_person}</Text>
            <Text style={styles.detailLabel}>Timeline</Text>
            <Text style={[styles.detailValue, pastDue && styles.overdueText]}>
              {formatDate(plan.start_date)} → {formatDate(plan.due_date)}{pastDue ? ' (past due)' : ''}
            </Text>
            {plan.mentor_comment ? (
              <>
                <Text style={styles.detailLabel}>Mentor comment</Text>
                <Text style={styles.detailValue}>{plan.mentor_comment}</Text>
              </>
            ) : null}
            <Text style={styles.detailLabel}>Last updated</Text>
            <Text style={styles.detailValue}>{formatDateTime(plan.updated_at)}</Text>

            {transitions.length > 0 ? (
              <>
                <Text style={styles.inputLabel}>Comment for status change (optional)</Text>
                <TextInput style={styles.input} value={comment} onChangeText={setComment} placeholder="Add a note for this decision" placeholderTextColor={C.muted} accessibilityLabel="Status change comment" />
              </>
            ) : null}

            {error ? <View style={{ marginTop: 12 }}><InlineNotice tone="danger" text={error} /></View> : null}

            <View style={[styles.actionButtons, styles.detailActions]}>
              {transitions.map((t) => (
                <SmallButton key={t} label={TRANSITION_LABELS[t]} onPress={() => changeStatus(t)} busy={busy} primary={t !== 'cancelled'} danger={t === 'cancelled'} />
              ))}
              {isPlanEditable(plan) ? <SmallButton label="Edit" onPress={() => onEdit(plan)} busy={busy} /> : null}
              {isPlanDeletable(plan) ? <SmallButton label="Delete" onPress={remove} busy={busy} danger /> : null}
            </View>
            {plan.status === 'completed' ? <Text style={styles.completedNote}>This plan is completed.</Text> : null}
            {plan.status === 'cancelled' ? <Text style={styles.cancelledNote}>This plan was cancelled.</Text> : null}

            <PlanSteps plan={plan} onCreateFollowUp={(step) => onCreateFollowUp(plan, step)} />
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}
