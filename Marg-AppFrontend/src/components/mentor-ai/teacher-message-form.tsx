/**
 * Draft a teacher message for an open follow-up (teacher_message_draft agent).
 * The draft becomes a send_teacher_message proposal that needs approval.
 */
import { useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { pageStyles } from '@/components/reports/page-chrome';
import { Button, Card, EmptyState, ErrorState, InlineNotice, LoadingState, StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useRunMentorAgent } from '@/hooks/api';
import type { MiExecution } from '@/lib/api/services';

import { AgentResult } from './agent-result';
import type { Lookups } from './lookups';

const OPEN = new Set(['pending', 'teacher_responded', 'evidence_submitted', 'needs_revision']);
const PURPOSES = [
  { value: 'reminder', label: 'Reminder' },
  { value: 'feedback', label: 'Feedback' },
  { value: 'followup', label: 'Follow-up' },
] as const;
const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'ta', label: 'Tamil' },
] as const;

function Chips<T extends string>({ options, value, onChange, disabled }: { options: readonly { value: T; label: string }[]; value: T; onChange: (v: T) => void; disabled: boolean }) {
  return (
    <View style={pageStyles.chipRow} accessibilityRole="radiogroup">
      {options.map((o) => (
        <Pressable
          key={o.value}
          onPress={() => onChange(o.value)}
          disabled={disabled}
          accessibilityRole="radio"
          accessibilityState={{ checked: value === o.value, disabled }}
          style={[pageStyles.chip, value === o.value && pageStyles.chipActive]}
        >
          <Text style={[pageStyles.chipText, value === o.value && pageStyles.chipTextActive]}>{o.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export function TeacherMessageForm({ lookups }: { lookups: Lookups }) {
  const run = useRunMentorAgent();
  const qc = useQueryClient();
  const followUps = lookups.followUps;
  const [followUpId, setFollowUpId] = useState<string | undefined>();
  const [purpose, setPurpose] = useState<(typeof PURPOSES)[number]['value']>('reminder');
  const [language, setLanguage] = useState<(typeof LANGUAGES)[number]['value']>('en');
  const [note, setNote] = useState('');
  const [result, setResult] = useState<MiExecution | null>(null);
  const [error, setError] = useState<string | null>(null);

  const open = useMemo(() => (followUps.data ?? []).filter((f) => OPEN.has(f.status)), [followUps.data]);
  const selected = open.find((f) => f.id === followUpId);

  const submit = () => {
    if (!selected) return;
    setError(null);
    run.mutate(
      {
        agent: 'teacher_message_draft',
        options: {
          followup_ref: selected.id,
          teacher_ref: selected.teacher_id,
          purpose,
          language,
          ...(note.trim() ? { mentor_note: note.trim() } : {}),
        },
      },
      {
        onSuccess: (env) => {
          void qc.invalidateQueries({ queryKey: ['mentor-ai', 'proposals'] });
          if (env.success && env.data) setResult(env.data);
          else setError(env.error?.message ?? 'No draft was returned.');
        },
        onError: (e) => setError(e.message),
      },
    );
  };

  return (
    <Card>
      <Text style={pageStyles.itemTitle}>Draft a message to a teacher</Text>
      <Text style={pageStyles.muted}>
        Choose an open follow-up. A draft is prepared for your review; nothing is sent until you approve it under Suggested actions and send it
        yourself.
      </Text>

      <Text style={pageStyles.label}>Open follow-up</Text>
      {followUps.isLoading && !followUps.data ? (
        <LoadingState label="Loading follow-ups…" />
      ) : !followUps.data ? (
        <ErrorState error={followUps.error} onRetry={() => void followUps.refetch()} />
      ) : open.length === 0 ? (
        <EmptyState title="No open follow-ups" message="Messages can be drafted for follow-ups that are still open." />
      ) : (
        <View style={{ gap: 6 }}>
          {open.map((f) => {
            const active = f.id === followUpId;
            const teacher = lookups.teacher(f.teacher_id);
            return (
              <Pressable
                key={f.id}
                onPress={() => setFollowUpId(active ? undefined : f.id)}
                disabled={run.isPending}
                accessibilityRole="radio"
                accessibilityState={{ checked: active, disabled: run.isPending }}
                style={[styles.option, active && styles.optionActive]}
              >
                <View style={pageStyles.rowBetween}>
                  <Text style={[styles.optionTitle, { flex: 1 }]}>
                    {active ? '● ' : '○ '}
                    {f.description}
                  </Text>
                  <StatusBadge status={f.status} />
                </View>
                <Text style={pageStyles.muted}>{teacher?.full_name ?? 'Teacher'}</Text>
              </Pressable>
            );
          })}
        </View>
      )}

      <Text style={pageStyles.label}>Purpose</Text>
      <Chips options={PURPOSES} value={purpose} onChange={setPurpose} disabled={run.isPending} />
      <Text style={pageStyles.label}>Language</Text>
      <Chips options={LANGUAGES} value={language} onChange={setLanguage} disabled={run.isPending} />
      <Text style={pageStyles.label}>Note to include (optional)</Text>
      <TextInput
        value={note}
        onChangeText={setNote}
        maxLength={500}
        multiline
        editable={!run.isPending}
        placeholder="Anything specific you want the message to mention"
        placeholderTextColor={C.muted}
        style={[pageStyles.input, { minHeight: 70, textAlignVertical: 'top' }]}
        accessibilityLabel="Optional note for the message"
      />
      <Button label="Prepare draft" onPress={submit} disabled={!selected} loading={run.isPending} style={{ marginTop: 12 }} />
      {error ? <InlineNotice tone="danger" text={error} /> : null}
      {result ? (
        <View style={{ marginTop: 12 }}>
          <AgentResult agent="teacher_message_draft" execution={result} lookups={lookups} />
        </View>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  option: { borderWidth: 1, borderColor: C.border, borderRadius: 10, padding: 10, backgroundColor: C.surface },
  optionActive: { borderColor: C.teal, backgroundColor: '#F2FBFA' },
  optionTitle: { color: C.navy, fontSize: 14, fontWeight: '600' },
});
