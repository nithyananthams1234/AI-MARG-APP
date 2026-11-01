import { useQueryClient } from '@tanstack/react-query';
import { useRouter, type Href } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { MentoringCalendar } from '@/components/dashboard/mentoring-calendar';
import { MentorAiPlanner } from '@/components/dashboard/mentor-ai-planner';
import { Card, InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useCoachStatus, useDashboard, useSchools, useTasks } from '@/hooks/api';
import { useAuth } from '@/stores/auth';

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function WorkspaceCard({
  title,
  value,
  detail,
  icon,
  tint,
  onPress,
}: {
  title: string;
  value: string | number;
  detail: string;
  icon: string;
  tint: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${title}. ${value}. ${detail}`}
      style={({ pressed }) => [styles.workspaceCard, pressed && styles.pressed]}
    >
      <View style={[styles.workspaceIconWrap, { backgroundColor: tint }]}>
        <Text style={styles.workspaceIcon}>{icon}</Text>
      </View>
      <Text style={styles.workspaceValue} numberOfLines={1}>{value}</Text>
      <Text style={styles.workspaceTitle}>{title}</Text>
      <Text style={styles.workspaceDetail} numberOfLines={2}>{detail}</Text>
    </Pressable>
  );
}

function SectionHeading({ title, action, onPress }: { title: string; action?: string; onPress?: () => void }) {
  return (
    <View style={styles.sectionHeading}>
      <Text style={styles.sectionTitle} accessibilityRole="header">{title}</Text>
      {action && onPress ? (
        <Pressable onPress={onPress} accessibilityRole="link" hitSlop={8}>
          <Text style={styles.sectionAction}>{action}</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export default function DashboardScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const user = useAuth((state) => state.user);
  const dashboard = useDashboard();
  const schools = useSchools();
  const tasks = useTasks();
  const coachStatus = useCoachStatus();
  const [refreshing, setRefreshing] = useState(false);

  const upcomingVisitCount = dashboard.data?.upcoming_visits;
  const pendingTaskCount = tasks.data
    ? tasks.data.filter((task) => task.status === 'pending').length
    : undefined;
  const coachAvailability = coachStatus.isLoading && !coachStatus.data
    ? '—'
    : coachStatus.data?.available
      ? 'Ready'
      : coachStatus.data
        ? 'Offline'
        : '—';
  const unread = dashboard.data?.unread_notifications;

  const refresh = async () => {
    setRefreshing(true);
    try {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['reports'] }),
        queryClient.invalidateQueries({ queryKey: ['schools'] }),
        queryClient.invalidateQueries({ queryKey: ['visits'] }),
        queryClient.invalidateQueries({ queryKey: ['tasks'] }),
        queryClient.invalidateQueries({ queryKey: ['follow-ups'] }),
        queryClient.invalidateQueries({ queryKey: ['coach-status'] }),
        queryClient.invalidateQueries({ queryKey: ['mentor-ai'] }),
      ]);
    } finally {
      setRefreshing(false);
    }
  };
  const go = (path: Href) => () => router.push(path);

  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={C.teal} />}
      >
        <View style={styles.header}>
          <View style={styles.headerText}>
            <Text style={styles.greeting}>{greeting()},</Text>
            <Text style={styles.name} numberOfLines={1}>{user?.full_name ?? 'Mentor'}</Text>
            <Text style={styles.date}>
              {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
            </Text>
          </View>
          <View style={styles.headerActions}>
            <Pressable
              onPress={go('/notifications')}
              style={styles.headerIconButton}
              accessibilityRole="button"
              accessibilityLabel={`Notifications${unread == null ? '' : `, ${unread} unread`}`}
            >
              <Text style={styles.headerIcon}>🔔</Text>
              {unread ? (
                <View style={styles.notificationBadge}>
                  <Text style={styles.notificationBadgeText}>{unread > 9 ? '9+' : unread}</Text>
                </View>
              ) : null}
            </Pressable>
            <Pressable
              onPress={go('/profile')}
              style={styles.headerIconButton}
              accessibilityRole="button"
              accessibilityLabel="Profile"
            >
              <Text style={styles.headerIcon}>◉</Text>
            </Pressable>
          </View>
        </View>

        {dashboard.error && !dashboard.data ? (
          <InlineNotice tone="warning" text="Dashboard summary is unavailable. Workspace figures will use available service records where possible." />
        ) : null}

        <SectionHeading title="YOUR WORKSPACE" />
        <View style={styles.workspaceGrid}>
          <WorkspaceCard
            title="Assigned Schools"
            value={dashboard.data?.total_schools ?? schools.data?.length ?? '—'}
            detail={schools.isLoading && !schools.data ? 'Loading school records' : 'View your school list'}
            icon="▦"
            tint="#EAF3FC"
            onPress={go('/schools')}
          />
          <WorkspaceCard
            title="Upcoming Visits"
            value={upcomingVisitCount ?? '—'}
            detail={dashboard.isLoading && !dashboard.data ? 'Loading scheduled visits' : 'View your visit schedule'}
            icon="◷"
            tint="#E8F7F5"
            onPress={go('/visits')}
          />
          <WorkspaceCard
            title="Classroom Coach"
            value={coachAvailability}
            detail={
              coachStatus.isLoading && !coachStatus.data
                ? 'Checking service status'
                : coachStatus.data?.available
                  ? 'Knowledge passages · Available'
                  : coachStatus.data
                    ? 'Service unavailable'
                    : 'Service status unknown'
            }
            icon="✦"
            tint="#F0ECF8"
            onPress={go('/classroom-coach')}
          />
          <WorkspaceCard
            title="Pending Tasks"
            value={pendingTaskCount ?? '—'}
            detail={tasks.isLoading && !tasks.data ? 'Loading task records' : 'Tasks awaiting a start'}
            icon="✓"
            tint="#FFF4E7"
            onPress={() => router.push({ pathname: '/tasks', params: { status: 'pending' } })}
          />
        </View>

        <SectionHeading title="MENTORING CALENDAR" />
        <MentoringCalendar />

        <SectionHeading
          title="MENTOR AI PLANNER"
          action="Full assistant"
          onPress={go('/mentor-ai')}
        />
        <MentorAiPlanner onOpenFullAssistant={go('/mentor-ai')} />

        <SectionHeading title="REPORT ANALYSIS" />
        <Card onPress={go('/learning-gaps')} style={styles.learningGapsCard}>
          <View style={styles.gapIconWrap}>
            <Text style={styles.gapIcon}>◎</Text>
          </View>
          <View style={styles.gapText}>
            <Text style={styles.gapTitle}>Learning Gap Analysis</Text>
            <Text style={styles.gapDescription}>
              Explore recorded challenges, severity, recommendations and their observation sources.
            </Text>
          </View>
          <View style={styles.gapCountWrap}>
            <Text style={styles.gapCount}>{dashboard.data?.total_learning_gaps ?? '—'}</Text>
            <Text style={styles.gapCountLabel}>identified</Text>
          </View>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: C.background },
  content: { paddingHorizontal: 18, paddingTop: 10, paddingBottom: 36, maxWidth: 900, width: '100%', alignSelf: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 18 },
  headerText: { flex: 1 },
  greeting: { color: C.secondaryText, fontSize: 14, fontWeight: '600' },
  name: { color: C.navy, fontSize: 23, fontWeight: '800', marginTop: 2 },
  date: { color: C.secondaryText, fontSize: 12, marginTop: 4 },
  headerActions: { flexDirection: 'row', gap: 8 },
  headerIconButton: {
    width: 42, height: 42, borderRadius: 14, backgroundColor: C.surface, borderWidth: 1, borderColor: C.border,
    alignItems: 'center', justifyContent: 'center',
  },
  headerIcon: { color: C.navy, fontSize: 21, fontWeight: '700' },
  notificationBadge: {
    position: 'absolute', top: -4, right: -4, minWidth: 18, height: 18, borderRadius: 9, backgroundColor: C.danger,
    alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4,
  },
  notificationBadgeText: { color: '#FFFFFF', fontSize: 10, fontWeight: '800' },
  sectionHeading: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, marginBottom: 10 },
  sectionTitle: { color: C.navy, fontSize: 15, fontWeight: '800', letterSpacing: 0.7 },
  sectionAction: { color: C.tealDark, fontSize: 13, fontWeight: '700' },
  workspaceGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  workspaceCard: {
    width: '48%', minWidth: 135, flexGrow: 1, minHeight: 144, padding: 14, borderRadius: 18,
    backgroundColor: C.surface, borderWidth: 1, borderColor: C.border,
    shadowColor: '#142B4A', shadowOpacity: 0.05, shadowRadius: 8, shadowOffset: { width: 0, height: 3 }, elevation: 2,
  },
  pressed: { opacity: 0.85 },
  workspaceIconWrap: { width: 34, height: 34, borderRadius: 11, alignItems: 'center', justifyContent: 'center', marginBottom: 10 },
  workspaceIcon: { color: C.navy, fontSize: 18, fontWeight: '800' },
  workspaceValue: { color: C.navy, fontSize: 23, fontWeight: '800' },
  workspaceTitle: { color: C.navy, fontSize: 13, fontWeight: '700', marginTop: 2 },
  workspaceDetail: { color: C.secondaryText, fontSize: 11, lineHeight: 15, marginTop: 4 },
  learningGapsCard: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  gapIconWrap: { width: 42, height: 42, borderRadius: 13, backgroundColor: '#FDECEC', alignItems: 'center', justifyContent: 'center' },
  gapIcon: { color: '#B23B3B', fontSize: 22, fontWeight: '800' },
  gapText: { flex: 1 },
  gapTitle: { color: C.navy, fontSize: 15, fontWeight: '800' },
  gapDescription: { color: C.secondaryText, fontSize: 12, lineHeight: 17, marginTop: 3 },
  gapCountWrap: { minWidth: 50, alignItems: 'center' },
  gapCount: { color: C.navy, fontSize: 20, fontWeight: '800' },
  gapCountLabel: { color: C.secondaryText, fontSize: 10, fontWeight: '600' },
});
