import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Button, Card, ErrorState, InlineNotice, LoadingState } from '@/components/ui/states';
import { ChipSelect, Field, fieldStyles, MutationError, reportQueued } from '@/components/visits/field-ui';
import { MargColors as C } from '@/constants/theme';
import { useClassrooms, useCreateObservation, useSchools, useSchoolTeachers, useTimetable, useUpdateObservation, useVisits } from '@/hooks/api';
import type { ObservationResponse } from '@/lib/api/generated';
import { formatDateTime } from '@/lib/format';
import { isQueued } from '@/lib/query';

/** Record a new observation: visit -> teacher + classroom of that school -> subject, topic, notes. */
export function ObservationCreateForm({
  initialVisitId,
  onDone,
  onCancel,
}: {
  initialVisitId?: string;
  onDone: (created?: ObservationResponse) => void;
  onCancel: () => void;
}) {
  const visits = useVisits();
  const schools = useSchools();
  const create = useCreateObservation();

  const [visitId, setVisitId] = useState<string | null>(initialVisitId ?? null);
  const [teacherId, setTeacherId] = useState<string | null>(null);
  const [classroomId, setClassroomId] = useState<string | null>(null);
  const [subject, setSubject] = useState('');
  const [topic, setTopic] = useState('');
  const [notes, setNotes] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const activeVisits = useMemo(
    () =>
      (visits.data ?? [])
        .filter((v) => v.status === 'planned' || v.status === 'in_progress')
        .sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at)),
    [visits.data],
  );
  const visit = activeVisits.find((v) => v.id === visitId);
  const schoolId = visit?.school_id;
  const teachers = useSchoolTeachers(schoolId);
  const classrooms = useClassrooms(schoolId);
  const timetable = useTimetable(classroomId ?? undefined);

  const subjects = useMemo(() => {
    const periods = (timetable.data ?? []).filter((p) => !teacherId || p.teacher_id === teacherId);
    return [...new Set(periods.map((p) => p.subject))].sort();
  }, [timetable.data, teacherId]);

  const schoolName = (id: string) => schools.data?.find((s) => s.id === id)?.name ?? 'School';
  const preselectedInvalid = !!initialVisitId && !!visits.data && !visit && visitId === initialVisitId;

  const chooseVisit = (id: string) => {
    setVisitId(id);
    setTeacherId(null);
    setClassroomId(null);
  };

  const save = async () => {
    setFormError(null);
    if (!visit) return setFormError('Choose a planned or in-progress visit.');
    if (!teacherId) return setFormError('Choose the teacher you observed.');
    if (!classroomId) return setFormError('Choose the classroom.');
    if (!subject.trim()) return setFormError('Enter the subject.');
    try {
      const res = await create.mutateAsync({
        school_visit_id: visit.id,
        teacher_id: teacherId,
        classroom_id: classroomId,
        subject: subject.trim(),
        topic: topic.trim() || null,
        notes: notes.trim() || null,
      });
      if (isQueued(res)) {
        reportQueued(res);
        onDone();
      } else onDone(res);
    } catch {
      // Shown via create.error.
    }
  };

  const busy = create.isPending;

  return (
    <Card>
      <Text style={fieldStyles.formTitle}>Record an observation</Text>

      {visits.isLoading && !visits.data ? (
        <LoadingState label="Loading visits…" />
      ) : !visits.data ? (
        <ErrorState error={visits.error} onRetry={() => void visits.refetch()} />
      ) : (
        <>
          {preselectedInvalid ? <InlineNotice tone="warning" text="That visit is no longer planned or in progress. Choose another visit." /> : null}
          <ChipSelect
            label="Visit"
            options={activeVisits.map((v) => ({ value: v.id, label: schoolName(v.school_id), detail: `${formatDateTime(v.scheduled_at)} · ${v.status.replace('_', ' ')}` }))}
            value={visitId}
            onChange={chooseVisit}
            emptyText="No planned or in-progress visits. Plan a visit first."
            disabled={busy}
          />
        </>
      )}

      {visit ? (
        <>
          {teachers.isLoading && !teachers.data ? (
            <LoadingState label="Loading teachers…" />
          ) : !teachers.data ? (
            <ErrorState error={teachers.error} onRetry={() => void teachers.refetch()} />
          ) : (
            <ChipSelect
              label="Teacher"
              options={teachers.data.filter((t) => t.is_active).map((t) => ({ value: t.id, label: t.full_name, detail: t.employee_code ?? undefined }))}
              value={teacherId}
              onChange={setTeacherId}
              emptyText="No teachers are assigned to this school."
              disabled={busy}
            />
          )}
          {classrooms.isLoading && !classrooms.data ? (
            <LoadingState label="Loading classrooms…" />
          ) : !classrooms.data ? (
            <ErrorState error={classrooms.error} onRetry={() => void classrooms.refetch()} />
          ) : (
            <ChipSelect
              label="Classroom"
              options={[...classrooms.data]
                .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }))
                .map((c) => ({ value: c.id, label: c.name, detail: `Grade ${c.grade}${c.section ? ` · ${c.section}` : ''}` }))}
              value={classroomId}
              onChange={setClassroomId}
              emptyText="No classrooms are recorded for this school."
              disabled={busy}
            />
          )}
        </>
      ) : null}

      <Field label="Subject" value={subject} onChangeText={setSubject} placeholder="e.g. Mathematics" maxLength={100} />
      {subjects.length > 0 ? (
        <View style={styles.suggestions}>
          <Text style={fieldStyles.muted}>From the timetable:</Text>
          {subjects.map((s) => (
            <Pressable key={s} onPress={() => setSubject(s)} style={styles.suggestion} accessibilityRole="button" accessibilityLabel={`Use subject ${s}`}>
              <Text style={styles.suggestionText}>{s}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
      <Field label="Topic (optional)" value={topic} onChangeText={setTopic} placeholder="What was being taught?" maxLength={200} />
      <Field
        label="Observation notes"
        value={notes}
        onChangeText={setNotes}
        multiline
        placeholder="Describe what you saw: teaching approach, student engagement, understanding…"
        hint="At least a few sentences (20+ characters) are needed for AI analysis. Do not include student names."
      />
      {formError ? <InlineNotice tone="danger" text={formError} /> : null}
      <MutationError error={create.error} />
      <View style={fieldStyles.row}>
        <Button label="Cancel" variant="secondary" onPress={onCancel} disabled={busy} style={fieldStyles.grow} />
        <Button label="Save as draft" onPress={() => void save()} loading={busy} style={fieldStyles.grow} />
      </View>
    </Card>
  );
}

/** Edit subject, topic and notes of a draft observation. */
export function ObservationEditForm({ observation, onDone }: { observation: ObservationResponse; onDone: () => void }) {
  const update = useUpdateObservation();
  const [subject, setSubject] = useState(observation.subject);
  const [topic, setTopic] = useState(observation.topic ?? '');
  const [notes, setNotes] = useState(observation.notes ?? '');
  const [formError, setFormError] = useState<string | null>(null);

  const save = async () => {
    setFormError(null);
    if (!subject.trim()) return setFormError('Enter the subject.');
    try {
      const res = await update.mutateAsync({
        observation,
        body: { subject: subject.trim(), topic: topic.trim() || null, notes: notes.trim() || null },
      });
      reportQueued(res);
      onDone();
    } catch {
      // Shown via update.error.
    }
  };

  return (
    <Card>
      <Text style={fieldStyles.formTitle}>Edit draft observation</Text>
      <Field label="Subject" value={subject} onChangeText={setSubject} maxLength={100} />
      <Field label="Topic (optional)" value={topic} onChangeText={setTopic} maxLength={200} />
      <Field label="Observation notes" value={notes} onChangeText={setNotes} multiline hint="Do not include student names." />
      {formError ? <InlineNotice tone="danger" text={formError} /> : null}
      <MutationError error={update.error} />
      <View style={fieldStyles.row}>
        <Button label="Cancel" variant="secondary" onPress={onDone} disabled={update.isPending} style={fieldStyles.grow} />
        <Button label="Save changes" onPress={() => void save()} loading={update.isPending} style={fieldStyles.grow} />
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  suggestions: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginTop: -6, marginBottom: 14 },
  suggestion: { borderRadius: 999, backgroundColor: '#E7F5F3', paddingHorizontal: 10, paddingVertical: 5 },
  suggestionText: { color: C.tealDark, fontSize: 12, fontWeight: '700' },
});
