import { Pressable, Text, View } from 'react-native';

import type { FollowUpResponse } from '@/lib/api/generated';
import { formatDate, relativeTime } from '@/lib/format';

import { fuStyles as styles } from './followup-styles';
import { FU_STATUS_COLORS, FU_STATUS_LABELS, type FollowUpLookups } from './followup-utils';

export function FollowUpStatusBadge({ status }: { status: string }) {
  const colors = FU_STATUS_COLORS[status] ?? { background: '#EEF1F5', text: '#64748B' };
  return (
    <View style={[styles.statusBadge, { backgroundColor: colors.background }]}>
      <Text style={[styles.statusText, { color: colors.text }]}>{FU_STATUS_LABELS[status] ?? status}</Text>
    </View>
  );
}

export function FollowUpCard({ item, lookups, onPress }: { item: FollowUpResponse; lookups: FollowUpLookups; onPress: () => void }) {
  const step = lookups.step(item.action_plan_step_id);
  const plan = step ? lookups.plan(step.action_plan_id) : undefined;
  const teacher = lookups.teacher(item.teacher_id);
  return (
    <Pressable
      style={styles.followUpCard}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`Follow-up for ${teacher?.full_name ?? 'teacher'}: ${item.description}. ${FU_STATUS_LABELS[item.status] ?? item.status}`}
    >
      <View style={styles.cardTopRow}>
        <Text style={styles.followUpId} numberOfLines={1}>{plan?.title ?? 'Action plan'}</Text>
        <FollowUpStatusBadge status={item.status} />
      </View>

      <Text style={styles.actionTitle}>{item.description}</Text>
      <Text style={styles.teacherName}>{teacher?.full_name ?? 'Teacher'}</Text>

      <View style={styles.schoolRow}>
        <Text style={styles.schoolIcon}>☰</Text>
        <Text style={styles.schoolName}>Step: {step?.title ?? '—'}</Text>
      </View>

      <View style={styles.cardDivider} />

      <View style={styles.cardBottomRow}>
        <View>
          <Text style={styles.dueLabel}>STEP DUE</Text>
          <Text style={styles.dueDate}>{step ? formatDate(step.due_date) : '—'}</Text>
        </View>
        <View>
          <Text style={styles.dueLabel}>UPDATED</Text>
          <Text style={styles.dueDate}>{relativeTime(item.updated_at)}</Text>
        </View>
        <Text style={styles.viewButtonText}>View details →</Text>
      </View>
    </Pressable>
  );
}
