import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Button, Card, EmptyState, InlineNotice, LoadingState, ErrorState, QueryView, StatusBadge } from '@/components/ui/states';
import { ChipSelect, Field, fieldStyles, MutationError, SectionTitle } from '@/components/visits/field-ui';
import { MargColors as C } from '@/constants/theme';
import { useCreateGap, useCreateRecommendation, useDecideRecommendation, useFindings, useGaps, useGapStatus, useRecommendations } from '@/hooks/api';
import type { LearningGapCreate, LearningGapResponse, ObservationResponse } from '@/lib/api/generated';

type Severity = NonNullable<LearningGapCreate['severity']>;
const SEVERITIES: Severity[] = ['low', 'medium', 'high', 'critical'];
const NEXT_STATUS: Record<string, { status: 'addressed' | 'resolved'; label: string } | undefined> = {
  identified: { status: 'addressed', label: 'Mark addressed' },
  addressed: { status: 'resolved', label: 'Mark resolved' },
};

export function GapsSection({ observation, grade }: { observation: ObservationResponse; grade?: string }) {
  const gaps = useGaps({ observation_id: observation.id });
  const [adding, setAdding] = useState(false);

  return (
    <>
      <SectionTitle title="Learning gaps" right={!adding ? <Button label="+ Add gap" variant="secondary" onPress={() => setAdding(true)} /> : null} />
      {adding ? <AddGapForm observation={observation} grade={grade} onDone={() => setAdding(false)} /> : null}
      <QueryView query={gaps} loadingLabel="Loading learning gaps…">
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No learning gaps recorded" message="Add a gap you identified, or use the Classroom Coach analysis." />
          ) : (
            list.map((g) => <GapCard key={g.id} gap={g} />)
          )
        }
      </QueryView>
    </>
  );
}

function GapCard({ gap }: { gap: LearningGapResponse }) {
  const setStatus = useGapStatus();
  const next = NEXT_STATUS[gap.status];
  return (
    <Card>
      <View style={fieldStyles.rowBetween}>
        <Text style={fieldStyles.itemTitle}>{gap.title}</Text>
        <StatusBadge status={gap.status} />
      </View>
      <View style={[fieldStyles.row, { marginBottom: 4 }]}>
        <StatusBadge status={gap.severity} label={`${gap.severity} severity`} />
        <Text style={fieldStyles.muted}>
          {gap.subject}
          {gap.grade ? ` · Grade ${gap.grade}` : ''}
        </Text>
      </View>
      <Text style={fieldStyles.itemText}>{gap.description}</Text>
      {next ? (
        <Button
          label={next.label}
          variant="secondary"
          onPress={() => setStatus.mutate({ id: gap.id, status: next.status })}
          loading={setStatus.isPending}
          style={{ marginTop: 10 }}
          accessibilityLabel={`${next.label}: ${gap.title}`}
        />
      ) : null}
      <MutationError error={setStatus.error} />
      <GapRecommendations gap={gap} />
    </Card>
  );
}

function GapRecommendations({ gap }: { gap: LearningGapResponse }) {
  const router = useRouter();
  const recs = useRecommendations({ learning_gap_id: gap.id });
  const decide = useDecideRecommendation();
  const [adding, setAdding] = useState(false);
  const pending = decide.isPending ? decide.variables : undefined;

  return (
    <View style={styles.recBox}>
      <View style={fieldStyles.rowBetween}>
        <Text style={styles.recHeading}>Recommendations</Text>
        {!adding ? <Button label="+ Add" variant="ghost" onPress={() => setAdding(true)} accessibilityLabel={`Add recommendation for ${gap.title}`} /> : null}
      </View>
      {adding ? <AddRecommendationForm gapId={gap.id} onDone={() => setAdding(false)} /> : null}
      <MutationError error={decide.error} />
      {recs.isLoading && !recs.data ? (
        <LoadingState label="Loading recommendations…" />
      ) : !recs.data ? (
        <ErrorState error={recs.error} onRetry={() => void recs.refetch()} />
      ) : recs.data.length === 0 ? (
        <Text style={fieldStyles.muted}>No recommendations yet.</Text>
      ) : (
        recs.data.map((r) => (
          <View key={r.id} style={styles.rec}>
            <View style={fieldStyles.rowBetween}>
              <Text style={fieldStyles.itemTitle}>{r.title}</Text>
              <StatusBadge status={r.status} label={r.status === 'ai_suggested' ? 'Awaiting approval' : undefined} />
            </View>
            <Text style={fieldStyles.muted}>{r.category}</Text>
            <Text style={fieldStyles.itemText}>{r.description}</Text>
            <Text style={[fieldStyles.muted, { marginTop: 4 }]}>Why: {r.rationale}</Text>
            {r.mentor_comment ? <Text style={fieldStyles.muted}>Comment: {r.mentor_comment}</Text> : null}
            {r.status === 'ai_suggested' ? (
              <View style={[fieldStyles.row, { marginTop: 8 }]}>
                <Button
                  label="Approve"
                  onPress={() => decide.mutate({ id: r.id, status: 'mentor_approved' })}
                  loading={pending?.id === r.id && pending.status === 'mentor_approved'}
                  disabled={decide.isPending}
                  style={fieldStyles.grow}
                  accessibilityLabel={`Approve recommendation: ${r.title}`}
                />
                <Button
                  label="Reject"
                  variant="danger"
                  onPress={() => decide.mutate({ id: r.id, status: 'rejected' })}
                  loading={pending?.id === r.id && pending.status === 'rejected'}
                  disabled={decide.isPending}
                  style={fieldStyles.grow}
                  accessibilityLabel={`Reject recommendation: ${r.title}`}
                />
              </View>
            ) : r.status === 'mentor_approved' ? (
              <Button label="Create action plan →" variant="ghost" onPress={() => router.push('/action-plans')} style={{ alignSelf: 'flex-start' }} />
            ) : null}
          </View>
        ))
      )}
    </View>
  );
}

function AddGapForm({ observation, grade, onDone }: { observation: ObservationResponse; grade?: string; onDone: () => void }) {
  const create = useCreateGap();
  const findings = useFindings(observation.id);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [subject, setSubject] = useState(observation.subject);
  const [gradeText, setGradeText] = useState(grade ?? '');
  const [severity, setSeverity] = useState<Severity>('medium');
  const [findingId, setFindingId] = useState<string>('none');
  const [error, setError] = useState<string | null>(null);

  const linkable = (findings.data ?? []).filter((f) => f.status !== 'rejected');

  const save = () => {
    setError(null);
    if (!title.trim() || !description.trim() || !subject.trim()) return setError('Enter a title, description and subject.');
    create.mutate(
      {
        observation_id: observation.id,
        observation_finding_id: findingId === 'none' ? null : findingId,
        title: title.trim(),
        description: description.trim(),
        subject: subject.trim(),
        grade: gradeText.trim() || null,
        severity,
      },
      { onSuccess: onDone },
    );
  };

  return (
    <Card>
      <Text style={fieldStyles.formTitle}>New learning gap</Text>
      <Field label="Title" value={title} onChangeText={setTitle} maxLength={200} />
      <Field label="Description" value={description} onChangeText={setDescription} multiline />
      <View style={fieldStyles.row}>
        <View style={{ flexGrow: 2, flexBasis: 160 }}>
          <Field label="Subject" value={subject} onChangeText={setSubject} maxLength={100} />
        </View>
        <View style={{ flexGrow: 1, flexBasis: 90 }}>
          <Field label="Grade" value={gradeText} onChangeText={setGradeText} maxLength={20} />
        </View>
      </View>
      <ChipSelect label="Severity" options={SEVERITIES.map((s) => ({ value: s, label: s.charAt(0).toUpperCase() + s.slice(1) }))} value={severity} onChange={setSeverity} />
      {linkable.length > 0 ? (
        <ChipSelect
          label="Linked finding (optional)"
          options={[{ value: 'none', label: 'None' }, ...linkable.map((f) => ({ value: f.id, label: f.title }))]}
          value={findingId}
          onChange={setFindingId}
        />
      ) : null}
      {error ? <InlineNotice tone="danger" text={error} /> : null}
      <MutationError error={create.error} />
      <View style={fieldStyles.row}>
        <Button label="Cancel" variant="secondary" onPress={onDone} disabled={create.isPending} style={fieldStyles.grow} />
        <Button label="Save gap" onPress={save} loading={create.isPending} style={fieldStyles.grow} />
      </View>
    </Card>
  );
}

function AddRecommendationForm({ gapId, onDone }: { gapId: string; onDone: () => void }) {
  const create = useCreateRecommendation();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [rationale, setRationale] = useState('');
  const [category, setCategory] = useState('');
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    setError(null);
    if (![title, description, rationale, category].every((v) => v.trim())) return setError('All fields are required.');
    create.mutate(
      { learning_gap_id: gapId, title: title.trim(), description: description.trim(), rationale: rationale.trim(), category: category.trim() },
      { onSuccess: onDone },
    );
  };

  return (
    <View style={{ marginTop: 8 }}>
      <Field label="Title" value={title} onChangeText={setTitle} maxLength={200} />
      <Field label="What should the teacher do?" value={description} onChangeText={setDescription} multiline />
      <Field label="Rationale" value={rationale} onChangeText={setRationale} multiline />
      <Field label="Category" value={category} onChangeText={setCategory} placeholder="e.g. teaching practice" maxLength={100} />
      <Text style={[fieldStyles.muted, { marginBottom: 10 }]}>New recommendations start as suggestions; approve them before creating an action plan.</Text>
      {error ? <InlineNotice tone="danger" text={error} /> : null}
      <MutationError error={create.error} />
      <View style={fieldStyles.row}>
        <Button label="Cancel" variant="secondary" onPress={onDone} disabled={create.isPending} style={fieldStyles.grow} />
        <Button label="Save recommendation" onPress={save} loading={create.isPending} style={fieldStyles.grow} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  recBox: { marginTop: 12, paddingTop: 10, borderTopWidth: 1, borderTopColor: C.border },
  recHeading: { color: C.navy, fontSize: 14, fontWeight: '800' },
  rec: { backgroundColor: C.inputBackground, borderRadius: 12, borderWidth: 1, borderColor: C.border, padding: 12, marginTop: 8 },
});
