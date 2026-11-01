import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Card, EmptyState, InlineNotice, LoadingState, StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useFollowUps, useSchools, useTasks, useVisits } from '@/hooks/api';
import { formatDateTime, humanize } from '@/lib/format';

import {
  activitiesForDate,
  buildCalendarActivities,
  calendarMonthDays,
  localDateKey,
  markersForDate,
  type CalendarActivity,
  type CalendarMarker,
} from './calendar-utils';

const MARKER_COLORS: Record<CalendarMarker, string> = {
  overdue: '#C43D3D',
  pending: '#176B45',
  upcoming: '#C37A18',
};

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function dateLabel(dateKey: string, options: Intl.DateTimeFormatOptions): string {
  const [year, month, day] = dateKey.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('en-IN', options);
}

function ActivityItem({ activity }: { activity: CalendarActivity }) {
  const time = /^\d{4}-\d{2}-\d{2}$/.test(activity.occurredAt)
    ? 'Time not recorded'
    : formatDateTime(activity.occurredAt);

  return (
    <Card style={styles.activityCard}>
      <View style={styles.activityHeading}>
        <Text style={styles.activityTitle} numberOfLines={2}>{activity.title}</Text>
        <StatusBadge status={activity.status} />
      </View>
      <Text style={styles.activityMeta}>{activity.type} · {time}</Text>
      {activity.schoolName ? <Text style={styles.activityMeta}>{activity.schoolName}</Text> : null}
      {activity.markers.includes('overdue') ? <Text style={styles.overdue}>Overdue based on its recorded date</Text> : null}
    </Card>
  );
}

function MarkerLegend() {
  return (
    <View style={styles.legend}>
      {([
        ['overdue', 'Overdue work'],
        ['pending', 'Pending work'],
        ['upcoming', 'Scheduled activity'],
      ] as const).map(([marker, label]) => (
        <View key={marker} style={styles.legendItem}>
          <View style={[styles.dot, { backgroundColor: MARKER_COLORS[marker] }]} />
          <Text style={styles.legendText}>{label}</Text>
        </View>
      ))}
    </View>
  );
}

export function MentoringCalendar() {
  const tasks = useTasks();
  const visits = useVisits();
  const followUps = useFollowUps();
  const schools = useSchools();
  const todayKey = localDateKey(new Date())!;
  const [month, setMonth] = useState(() => {
    const today = new Date();
    return new Date(today.getFullYear(), today.getMonth(), 1);
  });
  const [selectedDate, setSelectedDate] = useState(todayKey);

  const activities = useMemo(
    () => buildCalendarActivities({
      tasks: tasks.data ?? [],
      visits: visits.data ?? [],
      followUps: followUps.data ?? [],
      schools: schools.data ?? [],
    }),
    [tasks.data, visits.data, followUps.data, schools.data],
  );
  const days = useMemo(() => calendarMonthDays(month), [month]);
  const selectedActivities = activitiesForDate(activities, selectedDate);
  const hasInitialLoading = [tasks, visits, followUps, schools].some((query) => query.isLoading && query.data === undefined);
  const hasUnavailableData = [tasks, visits, followUps, schools].some((query) => query.error);

  const changeMonth = (offset: number) => {
    const next = new Date(month.getFullYear(), month.getMonth() + offset, 1);
    setMonth(next);
    setSelectedDate(localDateKey(next)!);
  };

  return (
    <View style={styles.container}>
      <Card style={styles.calendarCard}>
        <View style={styles.monthHeader}>
          <Pressable
            onPress={() => changeMonth(-1)}
            style={styles.monthButton}
            accessibilityRole="button"
            accessibilityLabel="Previous month"
          >
            <Text style={styles.monthArrow}>‹</Text>
          </Pressable>
          <Text style={styles.monthTitle} accessibilityRole="header">
            {month.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}
          </Text>
          <Pressable
            onPress={() => changeMonth(1)}
            style={styles.monthButton}
            accessibilityRole="button"
            accessibilityLabel="Next month"
          >
            <Text style={styles.monthArrow}>›</Text>
          </Pressable>
        </View>

        <View style={styles.grid}>
          {WEEKDAYS.map((day) => (
            <Text key={day} style={styles.weekday}>{day}</Text>
          ))}
          {days.map((day) => {
            const key = localDateKey(day)!;
            const inMonth = day.getMonth() === month.getMonth();
            const selected = key === selectedDate;
            const markers = markersForDate(activities, key);
            return (
              <Pressable
                key={key}
                onPress={() => setSelectedDate(key)}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                accessibilityLabel={`${dateLabel(key, { weekday: 'long', day: 'numeric', month: 'long' })}${markers.length ? `, ${markers.map(humanize).join(', ')}` : ''}`}
                style={styles.dayCell}
              >
                <View style={[styles.dayNumberWrap, selected && styles.selectedDay]}>
                  <Text style={[styles.dayNumber, !inMonth && styles.outsideMonth, selected && styles.selectedDayText]}>
                    {day.getDate()}
                  </Text>
                </View>
                <View style={styles.dayDots}>
                  {markers.map((marker) => (
                    <View key={marker} style={[styles.dot, { backgroundColor: MARKER_COLORS[marker] }]} />
                  ))}
                </View>
              </Pressable>
            );
          })}
        </View>

        <MarkerLegend />
      </Card>

      {hasInitialLoading ? <LoadingState label="Loading calendar activities…" /> : null}
      {hasUnavailableData ? (
        <InlineNotice tone="warning" text="Some activity data could not be refreshed. Saved records may be shown and calendar indicators may be incomplete." />
      ) : null}

      <View style={styles.selectedHeading}>
        <Text style={styles.selectedTitle} accessibilityRole="header">
          {dateLabel(selectedDate, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
        </Text>
        <Text style={styles.activityCount}>{selectedActivities.length}</Text>
      </View>

      {!hasInitialLoading && selectedActivities.length === 0 ? (
        <EmptyState title="No recorded activities" message="Tasks with due dates, visits and follow-ups for this date will appear here." />
      ) : null}
      {selectedActivities.map((activity) => <ActivityItem key={`${activity.type}-${activity.id}`} activity={activity} />)}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 10 },
  calendarCard: { padding: 14, gap: 10 },
  monthHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  monthButton: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: '#F3F7FA' },
  monthArrow: { color: C.navy, fontSize: 28, lineHeight: 30, fontWeight: '600' },
  monthTitle: { color: C.navy, fontSize: 17, fontWeight: '800' },
  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  weekday: { width: '14.285%', textAlign: 'center', color: C.secondaryText, fontSize: 11, fontWeight: '700', paddingBottom: 8 },
  dayCell: { width: '14.285%', minHeight: 50, alignItems: 'center', paddingTop: 2 },
  dayNumberWrap: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  selectedDay: { backgroundColor: C.navy },
  dayNumber: { color: C.text, fontSize: 13, fontWeight: '600' },
  selectedDayText: { color: '#FFFFFF', fontWeight: '800' },
  outsideMonth: { color: '#AAB4C2' },
  dayDots: { minHeight: 10, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 3, marginTop: 1 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 12, paddingTop: 8, borderTopWidth: 1, borderTopColor: C.border },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 5 },
  legendText: { color: C.secondaryText, fontSize: 11 },
  selectedHeading: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 },
  selectedTitle: { color: C.navy, fontSize: 16, fontWeight: '800', flex: 1 },
  activityCount: { color: C.tealDark, fontSize: 13, fontWeight: '800' },
  activityCard: { gap: 5 },
  activityHeading: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 },
  activityTitle: { color: C.navy, fontSize: 14, fontWeight: '700', flex: 1 },
  activityMeta: { color: C.secondaryText, fontSize: 12, lineHeight: 17 },
  overdue: { color: '#B23B3B', fontSize: 12, fontWeight: '700' },
});
