import { useState } from 'react';
import { Text, View } from 'react-native';

import { Button, Card, ErrorState, InlineNotice, LoadingState } from '@/components/ui/states';
import { ChipSelect, Field, fieldStyles, MutationError, reportQueued } from '@/components/visits/field-ui';
import { useCreateVisit, useSchools, useUpdateVisit } from '@/hooks/api';
import type { SchoolVisitResponse } from '@/lib/api/generated';
import { notify } from '@/lib/dialogs';
import { localDateTimeToIso, toDateInput } from '@/lib/format';
import { isQueued } from '@/lib/query';

const two = (n: number) => `${n}`.padStart(2, '0');

/** Create a visit, or edit a planned visit (date/time and notes only). */
export function VisitForm({
  visit,
  initialSchoolId,
  onDone,
  onCancel,
}: {
  visit?: SchoolVisitResponse;
  initialSchoolId?: string;
  onDone: (created?: SchoolVisitResponse) => void;
  onCancel: () => void;
}) {
  const schools = useSchools();
  const createVisit = useCreateVisit();
  const updateVisit = useUpdateVisit();
  const editing = !!visit;
  const start = visit ? new Date(visit.scheduled_at) : null;

  const [schoolId, setSchoolId] = useState<string | null>(visit?.school_id ?? initialSchoolId ?? null);
  const [date, setDate] = useState(() => (start ? toDateInput(start) : toDateInput(new Date(Date.now() + 86_400_000))));
  const [time, setTime] = useState(start ? `${two(start.getHours())}:${two(start.getMinutes())}` : '09:30');
  const [notes, setNotes] = useState(visit?.notes ?? '');
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = editing ? updateVisit : createVisit;
  const busy = mutation.isPending;

  const save = async () => {
    setFormError(null);
    if (!schoolId) return setFormError('Choose a school.');
    const scheduled = localDateTimeToIso(date.trim(), time.trim());
    if (!scheduled) return setFormError('Enter the date as YYYY-MM-DD and the time as HH:MM (24-hour).');
    const trimmed = notes.trim() || null;
    try {
      if (visit) {
        const res = await updateVisit.mutateAsync({ visit, body: { scheduled_at: scheduled, notes: trimmed } });
        if (!reportQueued(res)) notify('Visit updated');
        onDone();
      } else {
        const res = await createVisit.mutateAsync({ school_id: schoolId, scheduled_at: scheduled, notes: trimmed });
        if (isQueued(res)) {
          reportQueued(res);
          onDone();
        } else onDone(res);
      }
    } catch {
      // Shown below via mutation.error.
    }
  };

  return (
    <Card>
      <Text style={fieldStyles.formTitle}>{editing ? 'Edit planned visit' : 'Plan a school visit'}</Text>
      {editing ? (
        <InlineNotice text="The school of a visit cannot be changed. Cancel the visit and plan a new one instead." />
      ) : schools.isLoading && !schools.data ? (
        <LoadingState label="Loading schools…" />
      ) : !schools.data ? (
        <ErrorState error={schools.error} onRetry={() => void schools.refetch()} />
      ) : (
        <ChipSelect
          label="School"
          options={[...schools.data]
            .sort((a, b) => a.name.localeCompare(b.name))
            .map((s) => ({ value: s.id, label: s.name, detail: [s.code, s.district].filter(Boolean).join(' · ') }))}
          value={schoolId}
          onChange={setSchoolId}
          emptyText="No schools are assigned to you."
          disabled={busy}
        />
      )}
      <View style={fieldStyles.row}>
        <View style={{ flexGrow: 1, flexBasis: 140 }}>
          <Field label="Date (YYYY-MM-DD)" value={date} onChangeText={setDate} placeholder="2026-11-05" maxLength={10} />
        </View>
        <View style={{ flexGrow: 1, flexBasis: 110 }}>
          <Field label="Time (HH:MM)" value={time} onChangeText={setTime} placeholder="09:30" maxLength={5} />
        </View>
      </View>
      <Field label="Purpose / notes" value={notes} onChangeText={setNotes} placeholder="What do you plan to do on this visit?" multiline />
      {formError ? <InlineNotice tone="danger" text={formError} /> : null}
      <MutationError error={mutation.error} />
      <View style={fieldStyles.row}>
        <Button label="Cancel" variant="secondary" onPress={onCancel} disabled={busy} style={fieldStyles.grow} />
        <Button label={editing ? 'Save changes' : 'Plan visit'} onPress={() => void save()} loading={busy} style={fieldStyles.grow} />
      </View>
    </Card>
  );
}
