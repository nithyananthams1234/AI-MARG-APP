import { useState } from 'react';
import { Text, View } from 'react-native';

import { AiAnalysisSection } from '@/components/observations/ai-analysis';
import { EvidenceSection } from '@/components/observations/evidence-section';
import { FindingsSection } from '@/components/observations/findings-section';
import { GapsSection } from '@/components/observations/gaps-section';
import { ObservationEditForm } from '@/components/observations/observation-form';
import { Button, Card, QueryView, StatusBadge } from '@/components/ui/states';
import { fieldStyles, InfoRow, MutationError, reportQueued, ScreenShell } from '@/components/visits/field-ui';
import { useClassrooms, useObservation, useObservationStatus, useSchool, useSchoolTeachers, useVisit } from '@/hooks/api';
import { useDeleteObservation } from '@/hooks/api-field';
import type { ObservationResponse } from '@/lib/api/generated';
import { confirmAction } from '@/lib/dialogs';
import { formatDateTime } from '@/lib/format';

const NEXT: Record<string, { status: string; label: string; confirm?: string } | undefined> = {
  draft: { status: 'submitted', label: 'Submit observation', confirm: 'After submitting, the notes can no longer be edited.' },
  submitted: { status: 'processed', label: 'Mark as processed' },
  processed: { status: 'reviewed', label: 'Mark as reviewed' },
};

export function ObservationDetail({
  observationId,
  onBack,
  onDeleted,
  onOpenVisit,
}: {
  observationId: string;
  onBack: () => void;
  onDeleted: () => void;
  onOpenVisit: (visitId: string) => void;
}) {
  const observation = useObservation(observationId);
  const visit = useVisit(observation.data?.school_visit_id);
  const schoolId = visit.data?.school_id;
  const school = useSchool(schoolId);
  const teachers = useSchoolTeachers(schoolId);
  const classrooms = useClassrooms(schoolId);
  const [editing, setEditing] = useState(false);

  const o = observation.data;
  const classroom = classrooms.data?.find((c) => c.id === o?.classroom_id);
  const teacher = teachers.data?.find((t) => t.id === o?.teacher_id);

  return (
    <ScreenShell
      title={o ? `${o.subject}${o.topic ? ` · ${o.topic}` : ''}` : 'Observation'}
      subtitle={school.data?.name}
      icon="◎"
      onBack={onBack}
      refreshing={observation.isRefetching}
      onRefresh={() => void observation.refetch()}
    >
      <QueryView query={observation} loadingLabel="Loading observation…">
        {(data) => (
          <>
            {editing && data.status === 'draft' ? (
              <ObservationEditForm observation={data} onDone={() => setEditing(false)} />
            ) : (
              <Card>
                <View style={fieldStyles.rowBetween}>
                  <Text style={fieldStyles.itemTitle}>Observation</Text>
                  <StatusBadge status={data.status} />
                </View>
                <InfoRow label="Teacher" value={teacher?.full_name ?? (teachers.isLoading ? 'Loading…' : null)} />
                <InfoRow label="Classroom" value={classroom ? `${classroom.name} (Grade ${classroom.grade})` : classrooms.isLoading ? 'Loading…' : null} />
                <InfoRow label="School" value={school.data?.name} />
                <InfoRow label="Visit" value={visit.data ? formatDateTime(visit.data.scheduled_at) : null} />
                <InfoRow label="Recorded" value={formatDateTime(data.created_at)} />
                <Text style={[fieldStyles.label, { marginTop: 12 }]}>Notes</Text>
                <Text style={fieldStyles.itemText}>{data.notes || 'No notes recorded yet.'}</Text>
                <StatusActions observation={data} onEdit={() => setEditing(true)} onDeleted={onDeleted} />
                <Button label="Open visit" variant="ghost" onPress={() => onOpenVisit(data.school_visit_id)} style={{ marginTop: 6 }} />
              </Card>
            )}

            <EvidenceSection observationId={data.id} />
            <AiAnalysisSection observation={data} />
            <FindingsSection observation={data} />
            <GapsSection observation={data} grade={classroom?.grade} />
          </>
        )}
      </QueryView>
    </ScreenShell>
  );
}

function StatusActions({ observation, onEdit, onDeleted }: { observation: ObservationResponse; onEdit: () => void; onDeleted: () => void }) {
  const setStatus = useObservationStatus();
  const remove = useDeleteObservation();
  const next = NEXT[observation.status];
  const isDraft = observation.status === 'draft';
  const busy = setStatus.isPending || remove.isPending;

  const advance = () => {
    if (!next) return;
    const go = () => setStatus.mutate({ observation, status: next.status }, { onSuccess: (res) => void reportQueued(res) });
    if (next.confirm) confirmAction(`${next.label}?`, next.confirm, go, 'Submit');
    else go();
  };

  const del = () =>
    confirmAction('Delete this draft?', 'The draft observation will be removed.', () => remove.mutate(observation.id, { onSuccess: onDeleted }), 'Delete');

  if (!next && !isDraft) return null;

  return (
    <>
      <View style={[fieldStyles.row, { marginTop: 12 }]}>
        {next ? <Button label={next.label} onPress={advance} loading={setStatus.isPending} disabled={busy} style={fieldStyles.grow} /> : null}
        {isDraft ? <Button label="Edit" variant="secondary" onPress={onEdit} disabled={busy} style={fieldStyles.grow} /> : null}
        {isDraft ? <Button label="Delete" variant="danger" onPress={del} loading={remove.isPending} disabled={busy} style={fieldStyles.grow} /> : null}
      </View>
      <MutationError error={setStatus.error ?? remove.error} />
    </>
  );
}
