import { View } from 'react-native';

import { Button } from '@/components/ui/states';
import { fieldStyles, MutationError, reportQueued } from '@/components/visits/field-ui';
import { useVisitStatus } from '@/hooks/api';
import type { SchoolVisitResponse } from '@/lib/api/generated';
import { confirmAction } from '@/lib/dialogs';

type Status = SchoolVisitResponse['status'];

/** Allowed visit transitions (mirrors the backend rules). */
export const VISIT_TRANSITIONS: Record<Status, Status[]> = {
  planned: ['in_progress', 'cancelled'],
  in_progress: ['completed', 'cancelled'],
  completed: [],
  cancelled: [],
};

const LABELS: Record<Status, string> = {
  planned: 'Planned',
  in_progress: 'Start visit',
  completed: 'Complete visit',
  cancelled: 'Cancel visit',
};

export function VisitStatusActions({ visit, onEdit }: { visit: SchoolVisitResponse; onEdit?: () => void }) {
  const setStatus = useVisitStatus();
  const next = VISIT_TRANSITIONS[visit.status];
  if (next.length === 0 && !onEdit) return null;

  const run = (status: Status) => {
    const go = () =>
      setStatus.mutate(
        { visit, status },
        { onSuccess: (res) => void reportQueued(res) },
      );
    if (status === 'cancelled') confirmAction('Cancel this visit?', 'A cancelled visit cannot be reopened.', go, 'Cancel visit');
    else if (status === 'completed') confirmAction('Complete this visit?', 'You will not be able to record new observations for it.', go, 'Complete');
    else go();
  };

  const pendingStatus = setStatus.isPending ? setStatus.variables?.status : undefined;

  return (
    <>
      <View style={[fieldStyles.row, { marginTop: 12 }]}>
        {next.map((s) => (
          <Button
            key={s}
            label={LABELS[s]}
            variant={s === 'cancelled' ? 'danger' : 'primary'}
            onPress={() => run(s)}
            loading={pendingStatus === s}
            disabled={setStatus.isPending}
            style={fieldStyles.grow}
          />
        ))}
        {onEdit && visit.status === 'planned' ? (
          <Button label="Edit" variant="secondary" onPress={onEdit} disabled={setStatus.isPending} style={fieldStyles.grow} />
        ) : null}
      </View>
      <MutationError error={setStatus.error} />
    </>
  );
}
