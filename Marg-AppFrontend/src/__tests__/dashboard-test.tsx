import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Stack } from 'expo-router';
import { renderRouter } from 'expo-router/testing-library';
import { Text } from 'react-native';

import Dashboard from '@/app/dashboard';
import LearningGaps from '@/app/learning-gaps';
import Tasks from '@/app/tasks';
import { MentoringCalendar } from '@/components/dashboard/mentoring-calendar';

jest.mock('@/stores/auth', () => ({
  useAuth: (selector: (state: { user: { full_name: string } }) => unknown) => selector({ user: { full_name: 'Mentor Fixture' } }),
}));

jest.mock('@/hooks/api', () => {
  const ready = (data: unknown) => ({ data, isLoading: false, isRefetching: false, error: null, refetch: jest.fn() });
  const localTimestamp = (offset: number, hour: number) => {
    const date = new Date();
    date.setDate(date.getDate() + offset);
    date.setHours(hour, 0, 0, 0);
    return date.toISOString();
  };
  const taskRecords = [
    { id: 'pending', school_id: 'school-1', title: 'Pending task fixture', description: null, due_at: localTimestamp(1, 10), status: 'pending', priority: 'medium', urgency: 50, impact: 50, risk: 50, deadline_proximity: 50, workload_dependency: 50, priority_score: 50, completed_at: null, created_at: localTimestamp(-1, 10), updated_at: localTimestamp(-1, 10) },
    { id: 'in-progress', school_id: 'school-1', title: 'In-progress task fixture', description: null, due_at: localTimestamp(1, 12), status: 'in_progress', priority: 'high', urgency: 80, impact: 80, risk: 80, deadline_proximity: 80, workload_dependency: 50, priority_score: 80, completed_at: null, created_at: localTimestamp(-1, 10), updated_at: localTimestamp(-1, 10) },
    { id: 'completed', school_id: 'school-1', title: 'Completed task fixture', description: null, due_at: localTimestamp(-2, 10), status: 'completed', priority: 'low', urgency: 20, impact: 20, risk: 20, deadline_proximity: 20, workload_dependency: 20, priority_score: 20, completed_at: localTimestamp(-1, 10), created_at: localTimestamp(-3, 10), updated_at: localTimestamp(-1, 10) },
    { id: 'overdue', school_id: 'school-1', title: 'Overdue task fixture', description: null, due_at: localTimestamp(-1, 10), status: 'pending', priority: 'critical', urgency: 90, impact: 90, risk: 90, deadline_proximity: 90, workload_dependency: 50, priority_score: 90, completed_at: null, created_at: localTimestamp(-2, 10), updated_at: localTimestamp(-2, 10) },
  ];
  const visits = [
    { id: 'visit-1', school_id: 'school-1', scheduled_at: localTimestamp(2, 10), started_at: null, completed_at: null, status: 'planned', notes: 'Upcoming school visit', created_at: localTimestamp(-1, 10), updated_at: localTimestamp(-1, 10), version: 1 },
  ];
  const followUps = [
    { id: 'follow-up-1', action_plan_step_id: 'step-1', teacher_id: 'teacher-1', description: 'Pending follow-up fixture', status: 'pending', teacher_response: null, mentor_notes: null, responded_at: null, verified_at: null, created_at: localTimestamp(0, 10), updated_at: localTimestamp(0, 10) },
  ];
  const schools = [
    { id: 'school-1', name: 'Fictional Government Higher Secondary School', code: 'FGHSS', address: null, district: 'Sample district', state: 'Tamil Nadu', is_active: true, created_at: localTimestamp(-30, 10), updated_at: localTimestamp(-30, 10), version: 1 },
  ];
  const observations = [
    { id: 'observation-1', school_visit_id: 'visit-1', teacher_id: 'teacher-1', classroom_id: 'classroom-1', subject: 'Mathematics', topic: 'Fractions', notes: 'Several learners need more practice comparing equivalent fractions.', status: 'completed', created_at: localTimestamp(-2, 10), updated_at: localTimestamp(-2, 10) },
  ];
  const gaps = [
    { id: 'gap-1', observation_id: 'observation-1', observation_finding_id: 'finding-1', title: 'Comparing equivalent fractions', description: 'Learners need support explaining why two fractions have the same value.', subject: 'Mathematics', grade: '6', severity: 'high', status: 'identified', created_at: localTimestamp(-2, 10), updated_at: localTimestamp(-2, 10) },
  ];
  const findings = [
    { id: 'finding-1', observation_id: 'observation-1', title: 'Limited fraction comparison strategies', description: 'Learners relied on numerator size rather than equivalent values.', category: 'learning_gap', status: 'mentor_approved', mentor_comment: 'Verified during the lesson discussion.', created_at: localTimestamp(-2, 10), updated_at: localTimestamp(-2, 10), version: 1 },
  ];
  const recommendations = [
    { id: 'recommendation-1', learning_gap_id: 'gap-1', title: 'Use fraction strips', description: 'Compare equivalent fractions with visual models.', rationale: 'Visual comparison was recorded as a next instructional step.', category: 'instruction', status: 'mentor_approved', mentor_comment: null, created_at: localTimestamp(-1, 10), updated_at: localTimestamp(-1, 10), version: 1 },
  ];
  return {
    useDashboard: () => ready({ total_schools: 1, total_visits: 1, completed_visits: 0, pending_tasks: 3, completed_tasks: 1, total_learning_gaps: 1, total_action_plans: 0, upcoming_visits: 1, unread_notifications: 0 }),
    useSchools: () => ready(schools),
    useVisits: () => ready(visits),
    useTasks: () => ready(taskRecords),
    useFollowUps: () => ready(followUps),
    useCoachStatus: () => ready({ available: true, knowledge_chunks: 33624 }),
    useMentorAiStatus: () => ready({ available: true }),
    useCreateTask: () => ({ mutateAsync: jest.fn(), isPending: false }),
    useUpdateTask: () => ({ mutateAsync: jest.fn(), isPending: false }),
    useTaskStatus: () => ({ mutateAsync: jest.fn(), isPending: false }),
    useGaps: () => ready(gaps),
    useObservations: () => ready(observations),
    useFindings: () => ready(findings),
    useRecommendations: () => ready(recommendations),
    useEvidence: () => ready([]),
  };
});

jest.mock('@/hooks/api-cycle', () => ({
  useDeleteTask: () => ({ mutateAsync: jest.fn(), isPending: false }),
}));

function TestLayout() {
  return (
    <QueryClientProvider client={new QueryClient()}>
      <Stack screenOptions={{ headerShown: false }} />
    </QueryClientProvider>
  );
}

function Destination({ label }: { label: string }) {
  return <Text>{label}</Text>;
}

const app = {
  _layout: TestLayout,
  dashboard: Dashboard,
  calendar: MentoringCalendar,
  schools: () => <Destination label="Schools destination" />,
  visits: () => <Destination label="Visits destination" />,
  'classroom-coach': () => <Destination label="Classroom Coach destination" />,
  'mentor-ai': () => <Destination label="Mentor AI Assistant destination" />,
  tasks: Tasks,
  'learning-gaps': LearningGaps,
};

describe('MARG Home Dashboard', () => {
  it.each([
    ['Assigned Schools', '/schools', 'Schools destination'],
    ['Upcoming Visits', '/visits', 'Visits destination'],
    ['Classroom Coach', '/classroom-coach', 'Classroom Coach destination'],
  ])('navigates %s to %s', async (label, path, destination) => {
    await renderRouter(app, { initialUrl: '/dashboard' });
    await fireEvent.press(screen.getByRole('button', { name: new RegExp(label) }));
    await waitFor(() => expect(screen).toHavePathname(path));
    expect(screen.getByText(destination)).toBeTruthy();
  });

  it('opens the Tasks screen filtered to pending tasks', async () => {
    await renderRouter(app, { initialUrl: '/dashboard' });
    await fireEvent.press(screen.getByRole('button', { name: /Pending Tasks/ }));
    await waitFor(() => expect(screen).toHavePathname('/tasks'));
    expect(await screen.findByText('Pending task fixture')).toBeTruthy();
    expect(screen.queryByText('In-progress task fixture')).toBeNull();
    expect(screen.queryByText('Completed task fixture')).toBeNull();
  });

  it('opens the dedicated learning-gap analysis screen', async () => {
    await renderRouter(app, { initialUrl: '/dashboard' });
    await fireEvent.press(screen.getByText('Learning Gap Analysis'));
    await waitFor(() => expect(screen).toHavePathname('/learning-gaps'));
    expect(screen.getByText('Report Analysis')).toBeTruthy();
    expect(screen.getByText('Total identified learning gaps')).toBeTruthy();
    expect(screen.getByText('Learning Gap Distribution')).toBeTruthy();
    expect(screen.getByText('School-wise Comparison')).toBeTruthy();
    expect(screen.getByText('Progress Trend')).toBeTruthy();
    expect(screen.getByText('Gap Severity')).toBeTruthy();
    expect(screen.getByText('A trend is not available yet. Dated learning-gap records from at least two different months are required.')).toBeTruthy();
    expect(screen.getByText('Comparing equivalent fractions')).toBeTruthy();
    await fireEvent.press(screen.getByText('View source and evidence'));
    expect(screen.getByText('Mentor-verified finding')).toBeTruthy();
    expect(screen.getAllByText('Fictional Government Higher Secondary School').length).toBeGreaterThan(1);
    expect(screen.getByText('Use fraction strips')).toBeTruthy();
    expect(screen.getByText('No evidence files are recorded for this observation.')).toBeTruthy();
  });

  it('keeps only the four workspace cards and does not show the Classroom Coach collection count', async () => {
    await renderRouter(app, { initialUrl: '/dashboard' });

    const workspaceLabels = ['Assigned Schools', 'Upcoming Visits', 'Classroom Coach', 'Pending Tasks'];
    const workspaceButtons = screen.getAllByRole('button').filter((button) =>
      workspaceLabels.some((label) => String(button.props.accessibilityLabel).startsWith(label)),
    );
    expect(workspaceButtons).toHaveLength(4);
    expect(screen.getByRole('button', { name: /Assigned Schools/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Upcoming Visits/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Classroom Coach/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Pending Tasks/ })).toBeTruthy();
    expect(screen.queryByText('33624')).toBeNull();
  });

  it('shows the interactive calendar markers, selected-date activities and month controls', async () => {
    await renderRouter(app, { initialUrl: '/calendar' });

    expect(screen.getByText('Overdue work')).toBeTruthy();
    expect(screen.getByText('Pending work')).toBeTruthy();
    expect(screen.getByText('Scheduled activity')).toBeTruthy();
    expect(screen.getByLabelText(/Overdue/)).toBeTruthy();
    expect(screen.getAllByLabelText(/Pending/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/Upcoming/)).toBeTruthy();
    expect(screen.getByText('Pending follow-up fixture')).toBeTruthy();

    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowLabel = tomorrow.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });
    await fireEvent.press(screen.getByLabelText(new RegExp(tomorrowLabel)));
    expect(screen.getByText('Pending task fixture')).toBeTruthy();
    expect(screen.queryByText('Pending follow-up fixture')).toBeNull();

    const visitDate = new Date();
    visitDate.setDate(visitDate.getDate() + 2);
    const visitDateLabel = visitDate.toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });
    await fireEvent.press(screen.getByLabelText(new RegExp(visitDateLabel)));
    expect(screen.getByText('Upcoming school visit')).toBeTruthy();
    expect(screen.getByText('Fictional Government Higher Secondary School')).toBeTruthy();

    const nextMonth = new Date();
    nextMonth.setMonth(nextMonth.getMonth() + 1);
    const nextMonthPattern = new RegExp(nextMonth.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Next month' }));
    await waitFor(() => expect(screen.getAllByText(nextMonthPattern).length).toBeGreaterThan(0));
    await fireEvent.press(screen.getByRole('button', { name: 'Previous month' }));
    const currentMonthPattern = new RegExp(new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' }));
    await waitFor(() => expect(screen.getAllByText(currentMonthPattern).length).toBeGreaterThan(0));
  });

  it('keeps Mentor AI service status and links to the existing full planner', async () => {
    await renderRouter(app, { initialUrl: '/dashboard' });
    expect(await screen.findByText('MENTOR AI PLANNER')).toBeTruthy();
    expect(screen.getByText('Available')).toBeTruthy();
    expect(screen.queryByText('Daily plan')).toBeNull();
    expect(screen.queryByText('Teacher message')).toBeNull();
    expect(screen.queryByText('AI-generated recommendations')).toBeNull();
    expect(screen.queryByText('Recent decisions')).toBeNull();
    expect(screen.queryByText('No result yet')).toBeNull();
    expect(screen.queryByText('Try again')).toBeNull();

    await fireEvent.press(screen.getByRole('link', { name: 'Open Mentor AI Planner' }));
    await waitFor(() => expect(screen).toHavePathname('/mentor-ai'));
    expect(screen.getByText('Mentor AI Assistant destination')).toBeTruthy();
  });
});
