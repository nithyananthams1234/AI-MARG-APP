import { useState } from 'react';
import { Text, View } from 'react-native';

import { ObservationCreateForm } from '@/components/observations/observation-form';
import { Button, Card, EmptyState, QueryView, StatusBadge } from '@/components/ui/states';
import { FilterTabs, fieldStyles, ScreenShell, SectionTitle } from '@/components/visits/field-ui';
import { useClassrooms, useObservations, useSchools, useVisits } from '@/hooks/api';
import { useAllTeachers } from '@/hooks/api-field';
import { formatDateTime } from '@/lib/format';

type Filter = 'all' | 'draft' | 'submitted' | 'processed' | 'reviewed';
const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'processed', label: 'Processed' },
  { value: 'reviewed', label: 'Reviewed' },
];

export function ObservationList({
  initialVisitId,
  onOpen,
  onBack,
}: {
  initialVisitId?: string;
  onOpen: (id: string) => void;
  onBack: () => void;
}) {
  const observations = useObservations();
  const visits = useVisits();
  const schools = useSchools();
  const teachers = useAllTeachers();
  const classrooms = useClassrooms();
  const [filter, setFilter] = useState<Filter>('all');
  const [creating, setCreating] = useState(!!initialVisitId);

  const all = observations.data ?? [];
  const shown = filter === 'all' ? all : all.filter((o) => o.status === filter);
  const count = (f: Filter) => (f === 'all' ? all.length : all.filter((o) => o.status === f).length);

  const teacherName = (id: string) => teachers.data?.find((t) => t.id === id)?.full_name ?? 'Teacher';
  const classroomName = (id: string) => classrooms.data?.find((c) => c.id === id)?.name ?? 'Classroom';
  const schoolName = (visitId: string) => {
    const v = visits.data?.find((x) => x.id === visitId);
    return (v && schools.data?.find((s) => s.id === v.school_id)?.name) ?? 'School';
  };

  return (
    <ScreenShell
      title="Observations"
      subtitle="Classroom observations from your visits"
      icon="◎"
      onBack={onBack}
      refreshing={observations.isRefetching}
      onRefresh={() => {
        void observations.refetch();
        void visits.refetch();
      }}
    >
      {creating ? (
        <ObservationCreateForm
          initialVisitId={initialVisitId}
          onCancel={() => setCreating(false)}
          onDone={(created) => {
            setCreating(false);
            if (created) onOpen(created.id);
          }}
        />
      ) : (
        <Button label="+ Record observation" onPress={() => setCreating(true)} style={{ marginBottom: 14 }} />
      )}

      <QueryView query={observations} loadingLabel="Loading observations…">
        {() => (
          <>
            <FilterTabs options={FILTERS.map((f) => ({ ...f, count: count(f.value) }))} value={filter} onChange={setFilter} />
            <SectionTitle title={filter === 'all' ? 'All observations' : `${FILTERS.find((f) => f.value === filter)?.label ?? ''} observations`} />
            {shown.length === 0 ? (
              <EmptyState
                title={all.length === 0 ? 'No observations yet' : 'No observations with this status'}
                message={all.length === 0 ? 'Record an observation during a planned or in-progress visit.' : undefined}
              />
            ) : (
              shown.map((o) => (
                <Card key={o.id} onPress={() => onOpen(o.id)}>
                  <View style={fieldStyles.rowBetween}>
                    <Text style={fieldStyles.itemTitle} numberOfLines={2}>
                      {o.subject}
                      {o.topic ? ` · ${o.topic}` : ''}
                    </Text>
                    <StatusBadge status={o.status} />
                  </View>
                  <Text style={fieldStyles.muted}>
                    {teacherName(o.teacher_id)} · {classroomName(o.classroom_id)}
                  </Text>
                  <Text style={fieldStyles.muted}>
                    {schoolName(o.school_visit_id)} · {formatDateTime(o.created_at)}
                  </Text>
                  {o.notes ? (
                    <Text style={fieldStyles.itemText} numberOfLines={2}>
                      {o.notes}
                    </Text>
                  ) : null}
                </Card>
              ))
            )}
          </>
        )}
      </QueryView>
    </ScreenShell>
  );
}
