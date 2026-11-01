import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PlanCard } from '@/components/plans/plan-card';
import { PlanDetailModal } from '@/components/plans/plan-detail-modal';
import { PlanFormModal } from '@/components/plans/plan-form-modal';
import { planStyles as styles } from '@/components/plans/plan-styles';
import { isPlanPastDue } from '@/components/plans/plan-utils';
import { InlineNotice, QueryView } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useCreatePlan, usePlans } from '@/hooks/api';
import { useRecommendationContext, useUpdatePlan } from '@/hooks/api-cycle';
import type { ActionPlanCreate, ActionPlanResponse } from '@/lib/api/generated';

const filters = [
  { label: 'All', value: 'all' },
  { label: 'Draft', value: 'draft' },
  { label: 'Approval', value: 'pending_approval' },
  { label: 'Approved', value: 'approved' },
  { label: 'In progress', value: 'in_progress' },
  { label: 'Completed', value: 'completed' },
  { label: 'Overdue', value: 'overdue' },
  { label: 'Cancelled', value: 'cancelled' },
];

export default function ActionPlansScreen() {
  const router = useRouter();
  const plans = usePlans();
  const { resolve } = useRecommendationContext();
  const createPlan = useCreatePlan();
  const updatePlan = useUpdatePlan();

  const [activeFilter, setActiveFilter] = useState('all');
  const [formVisible, setFormVisible] = useState(false);
  const [editingPlan, setEditingPlan] = useState<ActionPlanResponse | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const all = useMemo(() => plans.data ?? [], [plans.data]);
  const selectedPlan = all.find((p) => p.id === selectedId) ?? null;

  const counts = useMemo(() => ({
    total: all.length,
    pending: all.filter((p) => p.status === 'draft' || p.status === 'pending_approval').length,
    active: all.filter((p) => p.status === 'approved' || p.status === 'in_progress').length,
    completed: all.filter((p) => p.status === 'completed').length,
  }), [all]);

  const filteredPlans = useMemo(() => {
    return all
      .filter((plan) => {
        if (activeFilter === 'all') return true;
        // "Overdue" also includes open plans whose due date has passed.
        if (activeFilter === 'overdue') return plan.status === 'overdue' || isPlanPastDue(plan);
        return plan.status === activeFilter;
      })
      .sort((a, b) => a.due_date.localeCompare(b.due_date));
  }, [all, activeFilter]);

  const openCreate = () => {
    setEditingPlan(null);
    setFormError(null);
    setFormVisible(true);
  };

  const openEdit = (plan: ActionPlanResponse) => {
    setSelectedId(null);
    setEditingPlan(plan);
    setFormError(null);
    setFormVisible(true);
  };

  const savePlan = async (body: ActionPlanCreate) => {
    setFormError(null);
    try {
      if (editingPlan) {
        const { recommendation_id: _ignored, ...update } = body;
        await updatePlan.mutateAsync({ id: editingPlan.id, body: update });
        setMessage('Plan updated.');
      } else {
        const created = await createPlan.mutateAsync(body);
        setMessage(`Plan “${created.title}” created as ${created.status.replace('_', ' ')}.`);
      }
      setFormVisible(false);
    } catch (e) {
      setFormError((e as Error).message);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <View style={styles.header}>
        <Pressable style={styles.backButton} onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Go back">
          <Text style={styles.backButtonText}>‹</Text>
        </Pressable>
        <View style={styles.headerTextContainer}>
          <Text style={styles.headerTitle} accessibilityRole="header">Action Plans</Text>
          <Text style={styles.headerSubtitle}>Turn approved recommendations into improvement plans</Text>
        </View>
        <Pressable style={styles.addButton} onPress={openCreate} accessibilityRole="button" accessibilityLabel="Create action plan">
          <Text style={styles.addButtonText}>+</Text>
        </Pressable>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={plans.isRefetching} onRefresh={() => void plans.refetch()} tintColor={C.teal} />}
      >
        {message ? <InlineNotice tone="success" text={message} /> : null}

        <QueryView query={plans} loadingLabel="Loading action plans…">
          {() => (
            <>
              <View style={styles.summaryGrid}>
                <SummaryCard value={counts.total} label="Total plans" />
                <SummaryCard value={counts.pending} label="Draft / awaiting approval" />
                <SummaryCard value={counts.active} label="Active plans" />
                <SummaryCard value={counts.completed} label="Completed" />
              </View>

              <View style={styles.sectionHeader}>
                <Text style={styles.sectionTitle}>Plans</Text>
                <Text style={styles.sectionCount}>{filteredPlans.length} shown</Text>
              </View>

              <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterContainer}>
                {filters.map((filter) => {
                  const selected = activeFilter === filter.value;
                  return (
                    <Pressable
                      key={filter.value}
                      style={[styles.filterChip, selected && styles.filterChipActive]}
                      onPress={() => setActiveFilter(filter.value)}
                      accessibilityRole="button"
                      accessibilityState={{ selected }}
                    >
                      <Text style={[styles.filterText, selected && styles.filterTextActive]}>{filter.label}</Text>
                    </Pressable>
                  );
                })}
              </ScrollView>

              {filteredPlans.length > 0 ? (
                filteredPlans.map((plan) => (
                  <PlanCard key={plan.id} plan={plan} context={resolve(plan.recommendation_id)} onPress={() => setSelectedId(plan.id)} />
                ))
              ) : (
                <View style={styles.emptyState}>
                  <Text style={styles.emptyIcon}>✓</Text>
                  <Text style={styles.emptyTitle}>{all.length === 0 ? 'No action plans yet' : 'No action plans found'}</Text>
                  <Text style={styles.emptyDescription}>
                    {all.length === 0
                      ? 'Create a plan from a mentor-approved recommendation to get started.'
                      : 'There are no plans in this category.'}
                  </Text>
                </View>
              )}

              <View style={styles.footerNote}>
                <Text style={styles.footerNoteTitle}>How plans move forward</Text>
                <Text style={styles.footerNoteText}>
                  Draft → submitted for approval → approved → in progress → completed. Steps can be added once a plan is
                  approved, and follow-ups are created for individual steps.
                </Text>
              </View>
            </>
          )}
        </QueryView>
      </ScrollView>

      <PlanFormModal
        visible={formVisible}
        plan={editingPlan}
        saving={createPlan.isPending || updatePlan.isPending}
        error={formError}
        onClose={() => setFormVisible(false)}
        onSubmit={(body) => void savePlan(body)}
      />

      <PlanDetailModal
        key={selectedPlan?.id ?? 'none'}
        plan={selectedPlan}
        context={resolve(selectedPlan?.recommendation_id)}
        onClose={() => setSelectedId(null)}
        onEdit={openEdit}
        onMessage={setMessage}
        onCreateFollowUp={(_plan, step) => {
          setSelectedId(null);
          router.push({ pathname: '/follow-ups', params: { stepId: step.id } });
        }}
      />
    </SafeAreaView>
  );
}

function SummaryCard({ value, label }: { value: number; label: string }) {
  return (
    <View style={styles.summaryCard} accessibilityLabel={`${label}: ${value}`}>
      <Text style={styles.summaryNumber}>{value}</Text>
      <Text style={styles.summaryLabel}>{label}</Text>
    </View>
  );
}
