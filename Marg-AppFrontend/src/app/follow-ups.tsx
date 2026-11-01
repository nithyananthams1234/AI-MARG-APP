import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, Text, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { FollowUpCard } from '@/components/followups/followup-card';
import { FollowUpCreateModal } from '@/components/followups/followup-create-modal';
import { FollowUpDetailModal } from '@/components/followups/followup-detail-modal';
import { fuStyles as styles } from '@/components/followups/followup-styles';
import { FU_FILTERS, type FollowUpLookups } from '@/components/followups/followup-utils';
import { InlineNotice, QueryView } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useFollowUps, usePlans } from '@/hooks/api';
import { useStepsForPlans, useTeachers } from '@/hooks/api-cycle';

function SummaryCard({ title, value, color }: { title: string; value: number; color: string }) {
  return (
    <View style={styles.summaryCard} accessibilityLabel={`${title}: ${value}`}>
      <Text style={[styles.summaryValue, { color }]}>{value}</Text>
      <Text style={styles.summaryTitle}>{title}</Text>
    </View>
  );
}

export default function FollowUpsScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ stepId?: string }>();
  const followUps = useFollowUps();
  const plans = usePlans();
  const teachers = useTeachers();
  const planIds = useMemo(() => (plans.data ?? []).map((p) => p.id), [plans.data]);
  const stepsQuery = useStepsForPlans(planIds);

  const [activeFilter, setActiveFilter] = useState('all');
  const [searchText, setSearchText] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createVisible, setCreateVisible] = useState(false);
  const [notice, setNotice] = useState<{ tone: 'success' | 'info'; text: string } | null>(null);

  // Opened from an action-plan step (?stepId=...): start creating a follow-up for it.
  const showCreate = createVisible || !!params.stepId;

  const lookups: FollowUpLookups = useMemo(() => {
    const stepMap = new Map(stepsQuery.steps.map((s) => [s.id, s]));
    const planMap = new Map((plans.data ?? []).map((p) => [p.id, p]));
    const teacherMap = new Map((teachers.data ?? []).map((t) => [t.id, t]));
    return { step: (id) => stepMap.get(id), plan: (id) => planMap.get(id), teacher: (id) => teacherMap.get(id) };
  }, [stepsQuery.steps, plans.data, teachers.data]);

  const all = useMemo(() => followUps.data ?? [], [followUps.data]);
  const selected = all.find((f) => f.id === selectedId) ?? null;

  const summary = useMemo(() => ({
    total: all.length,
    pending: all.filter((f) => f.status === 'pending' || f.status === 'needs_revision').length,
    review: all.filter((f) => f.status === 'evidence_submitted').length,
    verified: all.filter((f) => f.status === 'mentor_verified' || f.status === 'closed').length,
  }), [all]);

  const filtered = useMemo(() => {
    const q = searchText.trim().toLowerCase();
    return all
      .filter((f) => activeFilter === 'all' || f.status === activeFilter)
      .filter((f) => {
        if (!q) return true;
        const step = lookups.step(f.action_plan_step_id);
        const plan = step ? lookups.plan(step.action_plan_id) : undefined;
        return [f.description, lookups.teacher(f.teacher_id)?.full_name, step?.title, plan?.title]
          .some((v) => v?.toLowerCase().includes(q));
      })
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  }, [all, activeFilter, searchText, lookups]);

  const refresh = () => {
    void followUps.refetch();
    void plans.refetch();
    void teachers.refetch();
    void stepsQuery.refetch();
  };

  const closeCreate = () => {
    setCreateVisible(false);
    if (params.stepId) router.setParams({ stepId: undefined });
  };

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <View style={styles.page}>
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          refreshControl={<RefreshControl refreshing={followUps.isRefetching} onRefresh={refresh} tintColor={C.teal} />}
        >
          <View style={styles.header}>
            <Pressable style={styles.backButton} onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Go back">
              <Text style={styles.backText}>‹</Text>
            </Pressable>
            <View style={styles.headerContent}>
              <Text style={styles.eyebrow}>MENTOR WORKSPACE</Text>
              <Text style={styles.title} accessibilityRole="header">Follow-ups</Text>
              <Text style={styles.subtitle}>Track teacher progress on action-plan steps and verify evidence.</Text>
            </View>
            <Pressable style={styles.addButton} onPress={() => setCreateVisible(true)} accessibilityRole="button" accessibilityLabel="Create follow-up">
              <Text style={styles.addButtonText}>+ New</Text>
            </Pressable>
          </View>

          {notice ? <InlineNotice tone={notice.tone} text={notice.text} /> : null}

          <QueryView query={followUps} loadingLabel="Loading follow-ups…">
            {() => (
              <>
                <Text style={styles.sectionTitle}>Overview</Text>
                <View style={styles.summaryGrid}>
                  <SummaryCard title="Total" value={summary.total} color={C.navy} />
                  <SummaryCard title="Awaiting teacher" value={summary.pending} color="#B87520" />
                  <SummaryCard title="Evidence review" value={summary.review} color="#9465C5" />
                  <SummaryCard title="Verified / closed" value={summary.verified} color="#16845F" />
                </View>

                <View style={styles.searchBox}>
                  <Text style={styles.searchIcon}>⌕</Text>
                  <TextInput
                    value={searchText}
                    onChangeText={setSearchText}
                    placeholder="Search teacher, plan, step or description..."
                    placeholderTextColor={C.muted}
                    style={styles.searchInput}
                    returnKeyType="search"
                    accessibilityLabel="Search follow-ups"
                  />
                  {searchText.length > 0 ? (
                    <Pressable onPress={() => setSearchText('')} accessibilityRole="button" accessibilityLabel="Clear search">
                      <Text style={styles.clearSearch}>×</Text>
                    </Pressable>
                  ) : null}
                </View>

                <Text style={styles.sectionTitle}>Follow-up status</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterList}>
                  {FU_FILTERS.map((filter) => {
                    const sel = activeFilter === filter.value;
                    return (
                      <Pressable
                        key={filter.value}
                        onPress={() => setActiveFilter(filter.value)}
                        style={[styles.filterChip, sel && styles.filterChipActive]}
                        accessibilityRole="button"
                        accessibilityState={{ selected: sel }}
                      >
                        <Text style={[styles.filterText, sel && styles.filterTextActive]}>{filter.label}</Text>
                      </Pressable>
                    );
                  })}
                </ScrollView>

                <View style={styles.listHeading}>
                  <Text style={styles.sectionTitle}>Follow-up records</Text>
                  <Text style={styles.recordCount}>{filtered.length} records</Text>
                </View>

                {stepsQuery.error ? <InlineNotice tone="warning" text="Some plan steps could not be loaded; step names may be missing." /> : null}

                {filtered.length === 0 ? (
                  <View style={styles.emptyCard}>
                    <Text style={styles.emptyIcon}>⌕</Text>
                    <Text style={styles.emptyTitle}>{all.length === 0 ? 'No follow-ups yet' : 'No follow-ups found'}</Text>
                    <Text style={styles.emptyDescription}>
                      {all.length === 0
                        ? 'Create a follow-up for a step of an approved action plan.'
                        : 'Try another search term or status filter.'}
                    </Text>
                  </View>
                ) : (
                  filtered.map((item) => (
                    <FollowUpCard key={item.id} item={item} lookups={lookups} onPress={() => setSelectedId(item.id)} />
                  ))
                )}

                <View style={styles.infoNotice}>
                  <Text style={styles.infoIcon}>ⓘ</Text>
                  <Text style={styles.infoText}>
                    Teachers do not have app accounts: you record their response and evidence on their behalf. A follow-up
                    can be closed only after you verify it.
                  </Text>
                </View>
              </>
            )}
          </QueryView>
        </ScrollView>
      </View>

      <FollowUpDetailModal
        key={selected ? `${selected.id}:${selected.status}` : 'none'}
        item={selected}
        lookups={lookups}
        onClose={() => setSelectedId(null)}
        onMessage={(tone, text) => setNotice({ tone, text })}
      />

      <FollowUpCreateModal
        visible={showCreate}
        initialStepId={params.stepId}
        plans={plans.data ?? []}
        steps={stepsQuery.steps}
        stepsLoading={plans.isLoading || stepsQuery.isLoading}
        onClose={closeCreate}
        onCreated={(fu) => {
          closeCreate();
          setNotice({ tone: 'success', text: 'Follow-up created.' });
          setSelectedId(fu.id);
        }}
      />
    </SafeAreaView>
  );
}
