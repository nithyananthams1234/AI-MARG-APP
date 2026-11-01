import { useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useFollowUpAction } from '@/hooks/api';
import type { FollowUpResponse } from '@/lib/api/generated';
import { confirmAction } from '@/lib/dialogs';
import { formatDate, formatDateTime } from '@/lib/format';
import { isQueued } from '@/lib/query';

import { FollowUpStatusBadge } from './followup-card';
import { FollowUpEvidence } from './followup-evidence';
import { fuStyles as styles } from './followup-styles';
import type { FollowUpLookups } from './followup-utils';

type Props = {
  item: FollowUpResponse | null;
  lookups: FollowUpLookups;
  onClose: () => void;
  onMessage: (tone: 'success' | 'info', text: string) => void;
};

export function FollowUpDetailModal({ item, lookups, onClose, onMessage }: Props) {
  const action = useFollowUpAction();
  const [text, setText] = useState('');
  const [error, setError] = useState<string | null>(null);

  if (!item) return null;
  const step = lookups.step(item.action_plan_step_id);
  const plan = step ? lookups.plan(step.action_plan_id) : undefined;
  const teacher = lookups.teacher(item.teacher_id);
  const busy = action.isPending;

  type Act = Parameters<typeof action.mutateAsync>[0]['action'];
  const run = async (act: Act, done: string) => {
    setError(null);
    try {
      const result = await action.mutateAsync({ followUp: item, action: act });
      if (isQueued(result)) onMessage('info', 'Saved offline, will sync when you are back online.');
      else onMessage('success', done);
      setText('');
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const requireText = (min: number, label: string): string | null => {
    const t = text.trim();
    if (t.length < min) {
      setError(`${label} must be at least ${min} characters.`);
      return null;
    }
    return t;
  };

  const status = item.status;

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.modalOverlay}>
        <View style={[styles.modalCard, styles.wide]}>
          <View style={styles.modalHandle} />
          <View style={styles.modalHeader}>
            <View style={styles.modalHeadingContent}>
              <Text style={styles.modalEyebrow}>FOLLOW-UP DETAILS</Text>
              <Text style={styles.modalTitle} accessibilityRole="header">{teacher?.full_name ?? 'Teacher'}</Text>
            </View>
            <Pressable style={styles.closeButton} onPress={onClose} accessibilityRole="button" accessibilityLabel="Close details">
              <Text style={styles.closeButtonText}>×</Text>
            </Pressable>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.modalScrollContent} keyboardShouldPersistTaps="handled">
            <FollowUpStatusBadge status={status} />
            <Text style={styles.detailActionTitle}>{item.description}</Text>

            <View style={styles.detailSection}>
              <Text style={styles.detailLabel}>ACTION PLAN · STEP</Text>
              <Text style={styles.detailValue}>{plan?.title ?? '—'}</Text>
              <Text style={styles.detailSecondary}>{step ? `${step.title} · due ${formatDate(step.due_date)}` : '—'}</Text>
            </View>

            <View style={styles.detailTwoColumns}>
              <View style={styles.detailColumn}>
                <Text style={styles.detailLabel}>RESPONDED</Text>
                <Text style={styles.detailValue}>{formatDateTime(item.responded_at)}</Text>
              </View>
              <View style={styles.detailColumn}>
                <Text style={styles.detailLabel}>VERIFIED</Text>
                <Text style={styles.detailValue}>{formatDateTime(item.verified_at)}</Text>
              </View>
            </View>

            <View style={styles.detailSection}>
              <Text style={styles.detailLabel}>TEACHER RESPONSE / EVIDENCE NOTES</Text>
              <Text style={styles.responseText}>{item.teacher_response || 'Nothing recorded yet.'}</Text>
            </View>

            {item.mentor_notes ? (
              <View style={styles.detailSection}>
                <Text style={styles.detailLabel}>MENTOR NOTES</Text>
                <Text style={styles.responseText}>{item.mentor_notes}</Text>
              </View>
            ) : null}

            <FollowUpEvidence followUpId={item.id} canUpload={status !== 'closed'} />

            {(status === 'pending' || status === 'needs_revision' || status === 'teacher_responded') ? (
              <View style={styles.modalNotice}>
                <Text style={styles.modalNoticeText}>
                  Teachers do not have app accounts. Record their response and evidence here on their behalf.
                </Text>
              </View>
            ) : null}

            {status !== 'closed' && status !== 'mentor_verified' ? (
              <TextInput
                style={[styles.input, styles.multiline]}
                value={text}
                onChangeText={setText}
                multiline
                placeholder={
                  status === 'teacher_responded'
                    ? 'Describe the evidence the teacher submitted'
                    : status === 'evidence_submitted'
                      ? 'Mentor notes (optional for verification)'
                      : 'What did the teacher say or do?'
                }
                placeholderTextColor={C.muted}
                accessibilityLabel="Follow-up note"
              />
            ) : null}

            {error ? <View style={{ marginTop: 10 }}><InlineNotice tone="danger" text={error} /></View> : null}

            {busy ? <ActivityIndicator color={C.teal} style={{ marginTop: 14 }} /> : null}

            {(status === 'pending' || status === 'needs_revision') ? (
              <ActionButton
                label="Record teacher response"
                busy={busy}
                onPress={() => {
                  const t = requireText(3, 'Teacher response');
                  if (t) void run({ kind: 'teacher_response', text: t }, 'Teacher response recorded.');
                }}
              />
            ) : null}

            {status === 'teacher_responded' ? (
              <ActionButton
                label="Record evidence submitted"
                busy={busy}
                onPress={() => {
                  const t = requireText(3, 'Evidence description');
                  if (t) void run({ kind: 'evidence', text: t }, 'Evidence recorded.');
                }}
              />
            ) : null}

            {status === 'evidence_submitted' ? (
              <>
                <ActionButton
                  label="Verify"
                  busy={busy}
                  onPress={() => void run({ kind: 'mentor_decision', status: 'mentor_verified', notes: text.trim() || undefined }, 'Follow-up verified.')}
                />
                <ActionButton
                  label="Request revision"
                  secondary
                  busy={busy}
                  onPress={() => {
                    const t = requireText(3, 'Revision notes');
                    if (t) void run({ kind: 'mentor_decision', status: 'needs_revision', notes: t }, 'Revision requested.');
                  }}
                />
              </>
            ) : null}

            {status === 'mentor_verified' ? (
              <ActionButton
                label="Close follow-up"
                busy={busy}
                onPress={() => confirmAction('Close follow-up?', 'Closed follow-ups cannot be changed.', () => void run({ kind: 'close' }, 'Follow-up closed.'), 'Close')}
              />
            ) : null}

            {status === 'closed' ? (
              <View style={styles.closedMessage}>
                <Text style={styles.closedMessageText}>This follow-up is closed.</Text>
              </View>
            ) : null}

            <Pressable style={styles.secondaryAction} onPress={onClose} accessibilityRole="button">
              <Text style={styles.secondaryActionText}>Close details</Text>
            </Pressable>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

function ActionButton({ label, onPress, busy, secondary }: { label: string; onPress: () => void; busy: boolean; secondary?: boolean }) {
  return (
    <Pressable
      style={[secondary ? styles.secondaryAction : styles.primaryAction, busy && styles.disabled]}
      onPress={onPress}
      disabled={busy}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: busy, busy }}
    >
      <Text style={secondary ? styles.secondaryActionText : styles.primaryActionText}>{label}</Text>
    </Pressable>
  );
}
