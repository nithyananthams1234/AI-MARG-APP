import type { FollowUpResponse, MentorTaskResponse, SchoolResponse, SchoolVisitResponse } from '@/lib/api/generated';

export type CalendarMarker = 'overdue' | 'pending' | 'upcoming';

export interface CalendarActivity {
  id: string;
  type: 'Task' | 'Visit' | 'Follow-up';
  dateKey: string;
  occurredAt: string;
  title: string;
  schoolName?: string;
  status: string;
  markers: CalendarMarker[];
}

const OPEN_TASK_STATUSES = new Set(['pending', 'in_progress']);
const OPEN_FOLLOW_UP_STATUSES = new Set(['pending', 'teacher_responded', 'evidence_submitted', 'needs_revision']);

function dateTime(value: string): Date {
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) {
    const [, year, month, day] = dateOnly;
    return new Date(Number(year), Number(month) - 1, Number(day));
  }
  return new Date(value);
}

export function localDateKey(value?: string | Date | null): string | undefined {
  if (!value) return undefined;
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) return undefined;
    return `${value.getFullYear()}-${`${value.getMonth() + 1}`.padStart(2, '0')}-${`${value.getDate()}`.padStart(2, '0')}`;
  }
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (dateOnly) {
    const [, year, month, day] = dateOnly;
    const date = new Date(Number(year), Number(month) - 1, Number(day));
    if (date.getFullYear() !== Number(year) || date.getMonth() !== Number(month) - 1 || date.getDate() !== Number(day)) return undefined;
    return value;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  return `${date.getFullYear()}-${`${date.getMonth() + 1}`.padStart(2, '0')}-${`${date.getDate()}`.padStart(2, '0')}`;
}

export function calendarMonthDays(month: Date): Date[] {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const mondayOffset = (first.getDay() + 6) % 7;
  const start = new Date(first.getFullYear(), first.getMonth(), first.getDate() - mondayOffset);
  return Array.from({ length: 42 }, (_, index) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + index));
}

export function buildCalendarActivities({
  tasks,
  visits,
  followUps,
  schools,
  now = new Date(),
}: {
  tasks: MentorTaskResponse[];
  visits: SchoolVisitResponse[];
  followUps: FollowUpResponse[];
  schools: SchoolResponse[];
  now?: Date;
}): CalendarActivity[] {
  const schoolNames = new Map(schools.map((school) => [school.id, school.name]));
  const activities: CalendarActivity[] = [];

  for (const task of tasks) {
    const dateKey = localDateKey(task.due_at);
    if (!dateKey) continue;
    const isOpen = OPEN_TASK_STATUSES.has(task.status);
    const isOverdue = isOpen && dateTime(task.due_at!).getTime() < now.getTime();
    activities.push({
      id: task.id,
      type: 'Task',
      dateKey,
      occurredAt: task.due_at!,
      title: task.title,
      schoolName: task.school_id ? schoolNames.get(task.school_id) : undefined,
      status: task.status,
      markers: isOverdue ? ['overdue'] : isOpen ? ['pending'] : [],
    });
  }

  for (const visit of visits) {
    const dateKey = localDateKey(visit.scheduled_at);
    if (!dateKey) continue;
    const scheduledTime = dateTime(visit.scheduled_at).getTime();
    const overdue = visit.status === 'planned' && scheduledTime < now.getTime();
    const upcoming = visit.status === 'planned' && scheduledTime >= now.getTime();
    activities.push({
      id: visit.id,
      type: 'Visit',
      dateKey,
      occurredAt: visit.scheduled_at,
      title: visit.notes?.trim() || 'School visit',
      schoolName: schoolNames.get(visit.school_id),
      status: visit.status,
      markers: overdue ? ['overdue'] : upcoming ? ['upcoming'] : visit.status === 'in_progress' ? ['pending'] : [],
    });
  }

  for (const followUp of followUps) {
    const occurredAt = followUp.responded_at ?? followUp.created_at;
    const dateKey = localDateKey(occurredAt);
    if (!dateKey) continue;
    activities.push({
      id: followUp.id,
      type: 'Follow-up',
      dateKey,
      occurredAt,
      title: followUp.description,
      status: followUp.status,
      markers: OPEN_FOLLOW_UP_STATUSES.has(followUp.status) ? ['pending'] : [],
    });
  }

  return activities.sort((a, b) => a.occurredAt.localeCompare(b.occurredAt));
}

export function activitiesForDate(activities: CalendarActivity[], dateKey: string): CalendarActivity[] {
  return activities.filter((activity) => activity.dateKey === dateKey);
}

export function markersForDate(activities: CalendarActivity[], dateKey: string): CalendarMarker[] {
  const markerSet = new Set<CalendarMarker>();
  for (const activity of activitiesForDate(activities, dateKey)) {
    for (const marker of activity.markers) markerSet.add(marker);
  }
  return (['overdue', 'pending', 'upcoming'] as const).filter((marker) => markerSet.has(marker));
}
