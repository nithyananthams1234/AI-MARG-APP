import { Pressable, StyleSheet, Text, View } from 'react-native';

import { MargColors } from '@/constants/theme';
import type { MentorTaskResponse } from '@/lib/api/generated';
import { formatDateTime, humanize } from '@/lib/format';

import { PRIORITY_COLORS, isTaskOverdue } from './task-utils';

type Props = {
  task: MentorTaskResponse;
  schoolName?: string;
  busy: boolean;
  onEdit: () => void;
  onStatus: (status: 'in_progress' | 'completed' | 'cancelled') => void;
  onDelete: () => void;
};

export function TaskCard({ task, schoolName, busy, onEdit, onStatus, onDelete }: Props) {
  const overdue = isTaskOverdue(task);
  const color = PRIORITY_COLORS[task.priority];
  const editable = task.status === 'pending' || task.status === 'in_progress';
  const deletable = task.status === 'pending' || task.status === 'cancelled';

  return (
    <View style={styles.taskCard} accessibilityLabel={`${task.title}, ${task.priority} priority, ${humanize(task.status)}${overdue ? ', overdue' : ''}`}>
      <View style={styles.taskTopRow}>
        <View style={styles.taskTitleArea}>
          <Text style={styles.taskTitle}>{task.title}</Text>
          <Text style={styles.schoolName}>{schoolName ?? 'No school linked'}</Text>
        </View>
        <View style={[styles.priorityBadge, { backgroundColor: `${color}18` }]}>
          <Text style={[styles.priorityText, { color }]}>{task.priority.toUpperCase()} · {task.priority_score}</Text>
        </View>
      </View>

      {!!task.description && <Text style={styles.description}>{task.description}</Text>}

      <View style={styles.taskMeta}>
        <Text style={styles.metaText}>{task.due_at ? `Due: ${formatDateTime(task.due_at)}` : 'No due date'}</Text>
        {overdue && <Text style={styles.overdueLabel}>OVERDUE</Text>}
      </View>
      {(task.category || task.estimated_minutes) ? (
        <Text style={styles.metaText}>
          {[task.category ? humanize(task.category) : null, task.estimated_minutes ? `${task.estimated_minutes} min` : null].filter(Boolean).join(' · ')}
        </Text>
      ) : null}

      <View style={styles.cardFooter}>
        <Text style={styles.statusText}>{humanize(task.status).toUpperCase()}</Text>
        <View style={styles.actions}>
          {editable && <SmallButton label="Edit" style="edit" onPress={onEdit} disabled={busy} />}
          {task.status === 'pending' && <SmallButton label="Start" style="reopen" onPress={() => onStatus('in_progress')} disabled={busy} />}
          {task.status === 'in_progress' && <SmallButton label="Complete" style="complete" onPress={() => onStatus('completed')} disabled={busy} />}
          {editable && <SmallButton label="Cancel" style="cancel" onPress={() => onStatus('cancelled')} disabled={busy} />}
          {deletable && <SmallButton label="Delete" style="cancel" onPress={onDelete} disabled={busy} />}
        </View>
      </View>
    </View>
  );
}

function SmallButton({ label, style, onPress, disabled }: { label: string; style: 'edit' | 'complete' | 'reopen' | 'cancel'; onPress: () => void; disabled: boolean }) {
  const box = { edit: styles.editButton, complete: styles.completeButton, reopen: styles.reopenButton, cancel: styles.cancelButton }[style];
  const text = { edit: styles.editText, complete: styles.completeText, reopen: styles.reopenText, cancel: styles.cancelText }[style];
  return (
    <Pressable
      style={[box, disabled && { opacity: 0.5 }]}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled }}
    >
      <Text style={text}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  taskCard: {
    backgroundColor: '#FFFFFF', borderRadius: 16, padding: 16,
    marginBottom: 12, borderWidth: 1, borderColor: MargColors.border,
  },
  taskTopRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  taskTitleArea: { flex: 1 },
  taskTitle: { color: MargColors.navy, fontWeight: '800', fontSize: 15, lineHeight: 21 },
  schoolName: { color: MargColors.tealDark, fontSize: 11, fontWeight: '700', marginTop: 5 },
  priorityBadge: { paddingHorizontal: 8, paddingVertical: 5, borderRadius: 7 },
  priorityText: { fontSize: 9, fontWeight: '800' },
  description: { color: MargColors.secondaryText, fontSize: 12, lineHeight: 18, marginTop: 12 },
  taskMeta: { flexDirection: 'row', alignItems: 'center', marginTop: 13, marginBottom: 4, gap: 10 },
  metaText: { color: MargColors.secondaryText, fontSize: 11 },
  overdueLabel: { color: '#C13F35', fontSize: 9, fontWeight: '800' },
  cardFooter: {
    borderTopWidth: 1, borderTopColor: MargColors.border, marginTop: 14,
    paddingTop: 12, flexDirection: 'row', alignItems: 'center',
    justifyContent: 'space-between', flexWrap: 'wrap', gap: 8,
  },
  statusText: { color: MargColors.secondaryText, fontSize: 9, fontWeight: '800' },
  actions: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 7 },
  editButton: { paddingHorizontal: 10, paddingVertical: 7, backgroundColor: '#F1F4F8', borderRadius: 8 },
  editText: { color: MargColors.navy, fontSize: 10, fontWeight: '700' },
  completeButton: { paddingHorizontal: 10, paddingVertical: 7, backgroundColor: '#E5F6EF', borderRadius: 8 },
  completeText: { color: '#16845E', fontSize: 10, fontWeight: '700' },
  reopenButton: { paddingHorizontal: 10, paddingVertical: 7, backgroundColor: '#E8F3F5', borderRadius: 8 },
  reopenText: { color: MargColors.tealDark, fontSize: 10, fontWeight: '700' },
  cancelButton: { paddingHorizontal: 10, paddingVertical: 7, backgroundColor: '#FFF0F0', borderRadius: 8 },
  cancelText: { color: '#C13F35', fontSize: 10, fontWeight: '700' },
});
