import { useMemo, useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { Button, Card, EmptyState, QueryView, StatusBadge } from '@/components/ui/states';
import { FilterTabs, fieldStyles, ScreenShell, SectionTitle } from '@/components/visits/field-ui';
import { VisitStatusActions } from '@/components/visits/visit-actions';
import { VisitForm } from '@/components/visits/visit-form';
import { useSchools, useVisits } from '@/hooks/api';
import type { SchoolVisitResponse } from '@/lib/api/generated';
import { formatDateTime } from '@/lib/format';

type Filter = 'all' | SchoolVisitResponse['status'];
const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'planned', label: 'Planned' },
  { value: 'in_progress', label: 'In progress' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
];
const isActive = (v: SchoolVisitResponse) => v.status === 'planned' || v.status === 'in_progress';

export function VisitList({
  initialSchoolId,
  onOpen,
  onBack,
}: {
  initialSchoolId?: string;
  onOpen: (visitId: string) => void;
  onBack: () => void;
}) {
  const visits = useVisits();
  const schools = useSchools();
  const [filter, setFilter] = useState<Filter>('all');
  const [creating, setCreating] = useState(!!initialSchoolId);

  const schoolName = (id: string) => schools.data?.find((s) => s.id === id)?.name ?? (schools.isLoading ? 'Loading…' : 'Unknown school');

  const sorted = useMemo(() => {
    const list = [...(visits.data ?? [])];
    // Upcoming/active visits first (soonest first), then past visits (latest first).
    return list.sort((a, b) => {
      if (isActive(a) !== isActive(b)) return isActive(a) ? -1 : 1;
      return isActive(a) ? a.scheduled_at.localeCompare(b.scheduled_at) : b.scheduled_at.localeCompare(a.scheduled_at);
    });
  }, [visits.data]);
  const shown = filter === 'all' ? sorted : sorted.filter((v) => v.status === filter);
  const count = (f: Filter) => (f === 'all' ? sorted.length : sorted.filter((v) => v.status === f).length);

  return (
    <ScreenShell
      title="School Visits"
      subtitle="Plan, start and complete your visits"
      icon="⌖"
      onBack={onBack}
      refreshing={visits.isRefetching}
      onRefresh={() => {
        void visits.refetch();
        void schools.refetch();
      }}
    >
      {creating ? (
        <VisitForm
          initialSchoolId={initialSchoolId}
          onCancel={() => setCreating(false)}
          onDone={(created) => {
            setCreating(false);
            if (created) onOpen(created.id);
          }}
        />
      ) : (
        <Button label="+ Plan a visit" onPress={() => setCreating(true)} style={{ marginBottom: 14 }} />
      )}

      <QueryView query={visits} loadingLabel="Loading visits…">
        {() => (
          <>
            <FilterTabs options={FILTERS.map((f) => ({ ...f, count: count(f.value) }))} value={filter} onChange={setFilter} />
            <SectionTitle title={filter === 'all' ? 'All visits' : FILTERS.find((f) => f.value === filter)?.label ?? ''} />
            {shown.length === 0 ? (
              <EmptyState
                title={sorted.length === 0 ? 'No visits yet' : 'No visits with this status'}
                message={sorted.length === 0 ? 'Plan your first school visit to get started.' : undefined}
              />
            ) : (
              shown.map((v) => (
                <Card key={v.id}>
                  <Pressable onPress={() => onOpen(v.id)} accessibilityRole="button" accessibilityLabel={`Visit to ${schoolName(v.school_id)}, ${formatDateTime(v.scheduled_at)}. Open details`}>
                    <View style={fieldStyles.rowBetween}>
                      <Text style={fieldStyles.itemTitle} numberOfLines={2}>
                        {schoolName(v.school_id)}
                      </Text>
                      <StatusBadge status={v.status} />
                    </View>
                    <Text style={fieldStyles.muted}>{formatDateTime(v.scheduled_at)}</Text>
                    {v.notes ? (
                      <Text style={fieldStyles.itemText} numberOfLines={2}>
                        {v.notes}
                      </Text>
                    ) : null}
                  </Pressable>
                  <VisitStatusActions visit={v} />
                </Card>
              ))
            )}
          </>
        )}
      </QueryView>
    </ScreenShell>
  );
}
