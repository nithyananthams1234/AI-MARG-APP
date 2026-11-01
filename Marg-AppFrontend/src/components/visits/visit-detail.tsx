import { useState } from 'react';
import { Text, View } from 'react-native';

import { Button, Card, EmptyState, InlineNotice, QueryView, StatusBadge } from '@/components/ui/states';
import { fieldStyles, InfoRow, ScreenShell, SectionTitle } from '@/components/visits/field-ui';
import { VisitStatusActions } from '@/components/visits/visit-actions';
import { VisitForm } from '@/components/visits/visit-form';
import { useClassrooms, useObservations, useSchool, useSchoolTeachers, useVisit } from '@/hooks/api';
import { formatDateTime } from '@/lib/format';

export function VisitDetail({
  visitId,
  onBack,
  onRecordObservation,
  onOpenObservation,
  onOpenSchool,
  onOpenCoach,
}: {
  visitId: string;
  onBack: () => void;
  onRecordObservation: () => void;
  onOpenObservation: (id: string) => void;
  onOpenSchool: (schoolId: string) => void;
  onOpenCoach: (visitId: string, schoolId: string, schoolName: string) => void;
}) {
  const visit = useVisit(visitId);
  const school = useSchool(visit.data?.school_id);
  const observations = useObservations({ school_visit_id: visitId });
  const teachers = useSchoolTeachers(visit.data?.school_id);
  const classrooms = useClassrooms(visit.data?.school_id);
  const [editing, setEditing] = useState(false);

  const teacherName = (id: string) => teachers.data?.find((t) => t.id === id)?.full_name ?? 'Teacher';
  const classroomName = (id: string) => classrooms.data?.find((c) => c.id === id)?.name ?? 'Classroom';

  return (
    <ScreenShell
      title={school.data?.name ?? 'Visit'}
      subtitle="Visit details"
      icon="⌖"
      onBack={onBack}
      refreshing={visit.isRefetching || observations.isRefetching}
      onRefresh={() => {
        void visit.refetch();
        void observations.refetch();
      }}
    >
      <QueryView query={visit} loadingLabel="Loading visit…">
        {(v) => {
          const active = v.status === 'planned' || v.status === 'in_progress';
          return (
            <>
              {editing && v.status === 'planned' ? (
                <VisitForm visit={v} onCancel={() => setEditing(false)} onDone={() => setEditing(false)} />
              ) : (
                <Card>
                  <View style={fieldStyles.rowBetween}>
                    <Text style={fieldStyles.itemTitle}>{school.data?.name ?? 'School'}</Text>
                    <StatusBadge status={v.status} />
                  </View>
                  <InfoRow label="Scheduled" value={formatDateTime(v.scheduled_at)} />
                  {v.started_at ? <InfoRow label="Started" value={formatDateTime(v.started_at)} /> : null}
                  {v.completed_at ? <InfoRow label="Completed" value={formatDateTime(v.completed_at)} /> : null}
                  {school.data?.district ? <InfoRow label="District" value={school.data.district} /> : null}
                  {school.data?.travel_minutes_from_base != null ? (
                    <InfoRow label="Travel from base" value={`${school.data.travel_minutes_from_base} min`} />
                  ) : null}
                  <Text style={[fieldStyles.itemText, { marginTop: 10 }]}>{v.notes || 'No notes for this visit.'}</Text>
                  <VisitStatusActions visit={v} onEdit={() => setEditing(true)} />
                  <Button label="View school" variant="ghost" onPress={() => onOpenSchool(v.school_id)} style={{ marginTop: 6 }} />
                  <Button
                    label="Open Classroom Coach for this visit"
                    variant="secondary"
                    onPress={() => onOpenCoach(v.id, v.school_id, school.data?.name ?? '')}
                    style={{ marginTop: 6 }}
                  />
                </Card>
              )}

              <SectionTitle
                title="Observations"
                right={active ? <Button label="+ Record observation" onPress={onRecordObservation} /> : null}
              />
              {!active ? <InlineNotice text={`This visit is ${v.status.replace('_', ' ')}; new observations can only be recorded on planned or in-progress visits.`} /> : null}
              <QueryView query={observations} loadingLabel="Loading observations…">
                {(list) =>
                  list.length === 0 ? (
                    <EmptyState title="No observations yet" message={active ? 'Record a classroom observation for this visit.' : undefined} />
                  ) : (
                    list.map((o) => (
                      <Card key={o.id} onPress={() => onOpenObservation(o.id)}>
                        <View style={fieldStyles.rowBetween}>
                          <Text style={fieldStyles.itemTitle}>
                            {o.subject}
                            {o.topic ? ` · ${o.topic}` : ''}
                          </Text>
                          <StatusBadge status={o.status} />
                        </View>
                        <Text style={fieldStyles.muted}>
                          {teacherName(o.teacher_id)} · {classroomName(o.classroom_id)} · {formatDateTime(o.created_at)}
                        </Text>
                      </Card>
                    ))
                  )
                }
              </QueryView>
            </>
          );
        }}
      </QueryView>
    </ScreenShell>
  );
}
