import { Pressable, Text, View } from 'react-native';

import type { PlanContext } from '@/hooks/api-cycle';
import type { ActionPlanResponse } from '@/lib/api/generated';
import { formatDate } from '@/lib/format';

import { planStyles as styles } from './plan-styles';
import { PLAN_STATUS_COLORS, PLAN_STATUS_LABELS, isPlanPastDue } from './plan-utils';

export function PlanStatusBadge({ status }: { status: string }) {
  const color = PLAN_STATUS_COLORS[status] ?? '#718096';
  return (
    <View style={[styles.statusBadge, { backgroundColor: `${color}18`, alignSelf: 'flex-start' }]}>
      <View style={[styles.statusDot, { backgroundColor: color }]} />
      <Text style={[styles.statusText, { color }]}>{PLAN_STATUS_LABELS[status] ?? status}</Text>
    </View>
  );
}

export function PlanCard({ plan, context, onPress }: { plan: ActionPlanResponse; context: PlanContext; onPress: () => void }) {
  const pastDue = isPlanPastDue(plan);
  return (
    <Pressable
      style={styles.planCard}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${plan.title}, ${PLAN_STATUS_LABELS[plan.status] ?? plan.status}. Open plan details`}
    >
      <View style={styles.planTopRow}>
        <Text style={styles.planId} numberOfLines={1}>{context.school?.name ?? 'Action plan'}</Text>
        <PlanStatusBadge status={plan.status} />
      </View>
      <Text style={styles.planTitle}>{plan.title}</Text>
      <Text style={styles.planSchool} numberOfLines={2}>
        {context.gap ? `Gap: ${context.gap.title}` : context.recommendation ? `Recommendation: ${context.recommendation.title}` : plan.description}
      </Text>
      <View style={styles.planInfoRow}>
        <Text style={styles.planInfoLabel}>Responsible</Text>
        <Text style={styles.planInfoValue}>{plan.responsible_person}</Text>
      </View>
      <View style={styles.planInfoRow}>
        <Text style={styles.planInfoLabel}>Start</Text>
        <Text style={styles.planInfoValue}>{formatDate(plan.start_date)}</Text>
      </View>
      <View style={styles.planInfoRow}>
        <Text style={styles.planInfoLabel}>Due</Text>
        <Text style={[styles.planInfoValue, pastDue && styles.overdueText]}>
          {formatDate(plan.due_date)}{pastDue ? ' · past due' : ''}
        </Text>
      </View>
      <Text style={styles.viewDetails}>VIEW PLAN DETAILS →</Text>
    </Pressable>
  );
}
