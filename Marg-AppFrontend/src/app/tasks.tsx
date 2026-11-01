import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { TaskCard } from '@/components/tasks/task-card';
import { TaskFormModal } from '@/components/tasks/task-form-modal';
import { isTaskOverdue } from '@/components/tasks/task-utils';
import { EmptyState, InlineNotice, QueryView } from '@/components/ui/states';
import { MargColors } from '@/constants/theme';
import { useCreateTask, useSchools, useTaskStatus, useTasks, useUpdateTask } from '@/hooks/api';
import { useDeleteTask } from '@/hooks/api-cycle';
import type { MentorTaskCreate, MentorTaskResponse } from '@/lib/api/generated';
import { confirmAction } from '@/lib/dialogs';
import { humanize } from '@/lib/format';
import { isQueued } from '@/lib/query';

const filters = ['All', 'Pending', 'In progress', 'Completed', 'Overdue', 'Cancelled'] as const;
type Filter = (typeof filters)[number];
const priorityFilters = ['any', 'critical', 'high', 'medium', 'low'] as const;
type PriorityFilter = (typeof priorityFilters)[number];

type Notice = { tone: 'success' | 'danger' | 'info'; text: string };

export default function TasksScreen() {
  const router = useRouter();
  const { status } = useLocalSearchParams<{ status?: string }>();
  const tasks = useTasks();
  const schools = useSchools();
  const createTask = useCreateTask();
  const updateTask = useUpdateTask();
  const taskStatus = useTaskStatus();
  const deleteTask = useDeleteTask();

  const [filterOverride, setFilterOverride] = useState<Filter | null>(null);
  const filter = filterOverride ?? (status === 'pending' ? 'Pending' : 'All');
  const [priority, setPriority] = useState<PriorityFilter>('any');
  const [modalVisible, setModalVisible] = useState(false);
  const [editingTask, setEditingTask] = useState<MentorTaskResponse | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const all = useMemo(() => tasks.data ?? [], [tasks.data]);
  const schoolName = (id: string | null) => (id ? schools.data?.find((s) => s.id === id)?.name ?? 'School' : undefined);

  const counts = useMemo(() => ({
    all: all.filter((t) => t.status !== 'cancelled').length,
    pending: all.filter((t) => t.status === 'pending').length,
    progress: all.filter((t) => t.status === 'in_progress').length,
    completed: all.filter((t) => t.status === 'completed').length,
    overdue: all.filter(isTaskOverdue).length,
  }), [all]);

  const visibleTasks = useMemo(() => {
    return all
      .filter((task) => {
        if (priority !== 'any' && task.priority !== priority) return false;
        switch (filter) {
          case 'Pending': return task.status === 'pending';
          case 'In progress': return task.status === 'in_progress';
          case 'Completed': return task.status === 'completed';
          case 'Overdue': return isTaskOverdue(task);
          case 'Cancelled': return task.status === 'cancelled';
          default: return task.status !== 'cancelled';
        }
      })
      .sort((a, b) => b.priority_score - a.priority_score);
  }, [all, filter, priority]);

  const openCreate = () => {
    setEditingTask(null);
    setFormError(null);
    setModalVisible(true);
  };
  const openEdit = (task: MentorTaskResponse) => {
    setEditingTask(task);
    setFormError(null);
    setModalVisible(true);
  };

  const saving = createTask.isPending || updateTask.isPending;

  const saveTask = async (body: MentorTaskCreate) => {
    setFormError(null);
    try {
      const result = editingTask
        ? await updateTask.mutateAsync({ task: editingTask, body })
        : await createTask.mutateAsync(body);
      setModalVisible(false);
      setNotice(isQueued(result)
        ? { tone: 'info', text: 'Saved offline, will sync when you are back online.' }
        : { tone: 'success', text: editingTask ? 'Task updated.' : 'Task created.' });
    } catch (e) {
      setFormError((e as Error).message);
    }
  };

  const changeStatus = async (task: MentorTaskResponse, status: 'in_progress' | 'completed' | 'cancelled') => {
    setBusyId(task.id);
    setNotice(null);
    try {
      const result = await taskStatus.mutateAsync({ task, status });
      setNotice(isQueued(result)
        ? { tone: 'info', text: 'Saved offline, will sync when you are back online.' }
        : { tone: 'success', text: `“${task.title}” is now ${humanize(status).toLowerCase()}.` });
    } catch (e) {
      setNotice({ tone: 'danger', text: (e as Error).message });
    } finally {
      setBusyId(null);
    }
  };

  const confirmStatus = (task: MentorTaskResponse, status: 'in_progress' | 'completed' | 'cancelled') => {
    if (status === 'cancelled') {
      confirmAction('Cancel task?', 'This task will be moved out of your active list.', () => void changeStatus(task, status), 'Cancel task');
    } else {
      void changeStatus(task, status);
    }
  };

  const removeTask = (task: MentorTaskResponse) => {
    confirmAction('Delete task?', `“${task.title}” will be permanently deleted.`, async () => {
      setBusyId(task.id);
      setNotice(null);
      try {
        await deleteTask.mutateAsync(task.id);
        setNotice({ tone: 'success', text: 'Task deleted.' });
      } catch (e) {
        setNotice({ tone: 'danger', text: (e as Error).message });
      } finally {
        setBusyId(null);
      }
    }, 'Delete');
  };

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={tasks.isRefetching} onRefresh={() => void tasks.refetch()} tintColor={MargColors.teal} />}
      >
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backButton} accessibilityRole="button" accessibilityLabel="Go back">
            <Text style={styles.backText}>‹</Text>
          </Pressable>
          <View style={styles.headerText}>
            <Text style={styles.eyebrow}>MENTOR WORKSPACE</Text>
            <Text style={styles.heading} accessibilityRole="header">My Tasks</Text>
          </View>
          <Pressable style={styles.addButton} onPress={openCreate} accessibilityRole="button" accessibilityLabel="Add task">
            <Text style={styles.addButtonText}>+ Add</Text>
          </Pressable>
        </View>

        {notice ? <InlineNotice tone={notice.tone} text={notice.text} /> : null}

        <QueryView query={tasks} loadingLabel="Loading tasks…">
          {() => (
            <>
              <Text style={styles.sectionTitle}>Task overview</Text>
              <View style={styles.statsGrid}>
                <StatCard label="Active tasks" value={counts.all} />
                <StatCard label="Pending" value={counts.pending} />
                <StatCard label="In progress" value={counts.progress} />
                <StatCard label="Completed" value={counts.completed} />
              </View>

              <Pressable style={styles.overdueBanner} onPress={() => setFilterOverride('Overdue')} accessibilityRole="button" accessibilityLabel={`${counts.overdue} overdue tasks. Show overdue tasks`}>
                <View>
                  <Text style={styles.overdueTitle}>Overdue tasks</Text>
                  <Text style={styles.overdueSubtitle}>Open tasks past their due time</Text>
                </View>
                <Text style={styles.overdueCount}>{counts.overdue}</Text>
              </Pressable>

              <Text style={styles.sectionTitle}>Your task list</Text>
              <ChipRow items={filters} value={filter} onChange={setFilterOverride} label={(f) => f} />
              <ChipRow items={priorityFilters} value={priority} onChange={setPriority} label={(p) => (p === 'any' ? 'Any priority' : humanize(p))} />

              {visibleTasks.length === 0 ? (
                <EmptyState
                  title={all.length === 0 ? 'No tasks yet' : 'No tasks found'}
                  message={all.length === 0 ? 'Create your first task with “+ Add”.' : 'There are no tasks matching these filters.'}
                />
              ) : (
                visibleTasks.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    schoolName={schoolName(task.school_id)}
                    busy={busyId === task.id}
                    onEdit={() => openEdit(task)}
                    onStatus={(s) => confirmStatus(task, s)}
                    onDelete={() => removeTask(task)}
                  />
                ))
              )}
            </>
          )}
        </QueryView>
      </ScrollView>

      <TaskFormModal
        visible={modalVisible}
        task={editingTask}
        saving={saving}
        error={formError}
        onClose={() => setModalVisible(false)}
        onSubmit={(body) => void saveTask(body)}
      />
    </SafeAreaView>
  );
}

function ChipRow<V extends string>({ items, value, onChange, label }: { items: readonly V[]; value: V; onChange: (v: V) => void; label: (v: V) => string }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filterRow}>
      {items.map((item) => (
        <Pressable
          key={item}
          onPress={() => onChange(item)}
          style={[styles.filterChip, value === item && styles.filterChipActive]}
          accessibilityRole="button"
          accessibilityState={{ selected: value === item }}
        >
          <Text style={[styles.filterText, value === item && styles.filterTextActive]}>{label(item)}</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <View style={styles.statCard} accessibilityLabel={`${label}: ${value}`}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: MargColors.background },
  content: { padding: 20, paddingBottom: 40, maxWidth: 900, width: '100%', alignSelf: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 18 },
  backButton: {
    width: 42, height: 42, borderRadius: 14, backgroundColor: '#FFFFFF',
    alignItems: 'center', justifyContent: 'center',
  },
  backText: { fontSize: 32, color: MargColors.navy, marginTop: -5 },
  headerText: { flex: 1, marginLeft: 12 },
  eyebrow: { color: MargColors.teal, fontSize: 10, fontWeight: '800', letterSpacing: 1.2 },
  heading: { color: MargColors.navy, fontSize: 25, fontWeight: '800', marginTop: 2 },
  addButton: {
    backgroundColor: MargColors.navy, paddingHorizontal: 16,
    paddingVertical: 11, borderRadius: 12,
  },
  addButtonText: { color: '#FFFFFF', fontWeight: '700' },
  sectionTitle: { color: MargColors.navy, fontSize: 17, fontWeight: '800', marginBottom: 12 },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 16 },
  statCard: {
    width: '48%', flexGrow: 1, backgroundColor: '#FFFFFF',
    borderRadius: 15, padding: 15, borderWidth: 1, borderColor: MargColors.border,
  },
  statValue: { fontSize: 25, fontWeight: '800', color: MargColors.navy },
  statLabel: { color: MargColors.secondaryText, fontSize: 12, marginTop: 4 },
  overdueBanner: {
    backgroundColor: '#FFF2EF', borderRadius: 15, padding: 16,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 24, borderWidth: 1, borderColor: '#F9D8D1',
  },
  overdueTitle: { color: '#A83D32', fontWeight: '800', fontSize: 15 },
  overdueSubtitle: { color: '#A66A62', fontSize: 11, marginTop: 4 },
  overdueCount: { color: '#B83D32', fontSize: 26, fontWeight: '800' },
  filterRow: { gap: 8, paddingBottom: 12 },
  filterChip: {
    paddingHorizontal: 15, paddingVertical: 9, borderRadius: 20,
    backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: MargColors.border,
  },
  filterChipActive: { backgroundColor: MargColors.navy, borderColor: MargColors.navy },
  filterText: { color: MargColors.secondaryText, fontWeight: '600', fontSize: 12 },
  filterTextActive: { color: '#FFFFFF' },
});
