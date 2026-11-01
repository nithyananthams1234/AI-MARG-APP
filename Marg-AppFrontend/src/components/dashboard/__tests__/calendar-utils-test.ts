import type { FollowUpResponse, MentorTaskResponse, SchoolResponse, SchoolVisitResponse } from '@/lib/api/generated';

import {
  activitiesForDate,
  buildCalendarActivities,
  calendarMonthDays,
  localDateKey,
  markersForDate,
} from '../calendar-utils';

const school: SchoolResponse = {
  id: 'school-1',
  name: 'Fictional Government Higher Secondary School',
  code: 'FGHSS',
  address: null,
  district: 'Sample district',
  state: 'Tamil Nadu',
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  version: 1,
};

function task(id: string, dueAt: string, status: MentorTaskResponse['status']): MentorTaskResponse {
  return {
    id,
    school_id: school.id,
    title: `Task ${id}`,
    description: null,
    due_at: dueAt,
    status,
    priority: 'medium',
    urgency: 0,
    impact: 0,
    risk: 0,
    deadline_proximity: 0,
    workload_dependency: 0,
    priority_score: 1,
    completed_at: null,
    created_at: dueAt,
    updated_at: dueAt,
  };
}

function visit(id: string, scheduledAt: string, status: SchoolVisitResponse['status']): SchoolVisitResponse {
  return {
    id,
    school_id: school.id,
    scheduled_at: scheduledAt,
    started_at: null,
    completed_at: null,
    status,
    notes: `Visit ${id}`,
    created_at: scheduledAt,
    updated_at: scheduledAt,
    version: 1,
  };
}

function followUp(createdAt: string): FollowUpResponse {
  return {
  id: 'follow-up-1',
  action_plan_step_id: 'step-1',
  teacher_id: 'teacher-1',
  description: 'Review the formative assessment plan',
  status: 'pending',
  teacher_response: null,
  mentor_notes: null,
  responded_at: null,
  verified_at: null,
  created_at: createdAt,
  updated_at: createdAt,
  };
}

describe('dashboard calendar data', () => {
  it('keeps date-only values local and converts timestamps to the device-local date', () => {
    expect(localDateKey('2030-01-10')).toBe('2030-01-10');
    expect(localDateKey('not-a-date')).toBeUndefined();
    const timestamp = new Date('2030-01-10T00:30:00Z');
    expect(localDateKey(timestamp.toISOString())).toBe(localDateKey(timestamp));
  });

  it('builds a Monday-first six-week month grid', () => {
    const days = calendarMonthDays(new Date(2026, 1, 1));
    expect(days).toHaveLength(42);
    expect(days[0].getDay()).toBe(1);
    expect(days.some((day) => localDateKey(day) === '2026-02-01')).toBe(true);
  });

  it('marks actual overdue, pending and upcoming records and filters selected dates', () => {
    const now = new Date(2030, 0, 10, 12);
    const dateKey = localDateKey(now)!;
    const overdueAt = new Date(2030, 0, 10, 8).toISOString();
    const pendingAt = new Date(2030, 0, 10, 15).toISOString();
    const upcomingVisitAt = new Date(2030, 0, 10, 16).toISOString();
    const activities = buildCalendarActivities({
      tasks: [
        task('overdue', overdueAt, 'pending'),
        task('pending', pendingAt, 'in_progress'),
        task('completed', overdueAt, 'completed'),
      ],
      visits: [visit('upcoming', upcomingVisitAt, 'planned')],
      followUps: [followUp(new Date(2030, 0, 10, 13).toISOString())],
      schools: [school],
      now,
    });

    expect(markersForDate(activities, dateKey)).toEqual(['overdue', 'pending', 'upcoming']);
    expect(new Set(activitiesForDate(activities, dateKey).map((activity) => activity.id))).toEqual(
      new Set(['overdue', 'pending', 'follow-up-1', 'upcoming', 'completed']),
    );
    expect(activities.find((activity) => activity.id === 'upcoming')?.schoolName).toBe(school.name);
    expect(activities.find((activity) => activity.id === 'completed')?.markers).toEqual([]);
    expect(activitiesForDate(activities, '2030-01-11')).toEqual([]);
  });
});
