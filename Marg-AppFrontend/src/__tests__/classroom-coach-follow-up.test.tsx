import { fireEvent, render } from '@testing-library/react-native';

import { TeacherFollowUpTracking } from '@/components/coach/teacher-follow-up-tracking';

jest.mock('@/components/followups/followup-evidence', () => ({
  FollowUpEvidence: () => null,
}));

jest.mock('@/hooks/api', () => {
  const plans = [
    { id: 'plan-a', recommendation_id: 'rec-a', title: 'North reading plan' },
    { id: 'plan-b', recommendation_id: 'rec-b', title: 'South maths plan' },
  ];
  const followUps = [
    {
      id: 'follow-up-new',
      action_plan_step_id: 'step-a',
      teacher_id: 'teacher-a',
      description: 'Most recent follow-up',
      status: 'teacher_responded',
      teacher_response: 'Teacher reported using paired reading.',
      mentor_notes: null,
      responded_at: '2026-10-21T11:00:00Z',
      verified_at: null,
      created_at: '2026-10-20T11:00:00Z',
      updated_at: '2026-10-21T11:00:00Z',
    },
    {
      id: 'follow-up-old',
      action_plan_step_id: 'step-a',
      teacher_id: 'teacher-a',
      description: 'Earlier follow-up',
      status: 'mentor_verified',
      teacher_response: 'Evidence was reviewed.',
      mentor_notes: 'The approach was confirmed during the visit.',
      responded_at: '2026-10-19T10:00:00Z',
      verified_at: '2026-10-20T10:00:00Z',
      created_at: '2026-10-18T10:00:00Z',
      updated_at: '2026-10-20T10:00:00Z',
    },
    {
      id: 'follow-up-other-school',
      action_plan_step_id: 'step-b',
      teacher_id: 'teacher-b',
      description: 'Other school follow-up',
      status: 'pending',
      teacher_response: null,
      mentor_notes: null,
      responded_at: null,
      verified_at: null,
      created_at: '2026-10-22T10:00:00Z',
      updated_at: '2026-10-22T10:00:00Z',
    },
  ];
  const query = <T,>(data: T) => ({ data, isLoading: false, error: null, refetch: jest.fn() });
  const mockSetStepStatus = jest.fn().mockResolvedValue({});

  return {
    __esModule: true,
    usePlans: () => query(plans),
    useRecommendations: () => query([
      { id: 'rec-a', learning_gap_id: 'gap-a' },
      { id: 'rec-b', learning_gap_id: 'gap-b' },
    ]),
    useGaps: () => query([
      { id: 'gap-a', observation_id: 'observation-a' },
      { id: 'gap-b', observation_id: 'observation-b' },
    ]),
    useObservations: () => query([
      { id: 'observation-a', school_visit_id: 'visit-a' },
      { id: 'observation-b', school_visit_id: 'visit-b' },
    ]),
    useVisits: () => query([
      { id: 'visit-a', school_id: 'school-a' },
      { id: 'visit-b', school_id: 'school-b' },
    ]),
    useSchools: () => query([
      { id: 'school-a', name: 'North School' },
      { id: 'school-b', name: 'South School' },
    ]),
    useFollowUps: () => query(followUps),
    useSchoolTeachers: (schoolId?: string) => query(
      schoolId === 'school-a'
        ? [{ id: 'teacher-a', full_name: 'Teacher A' }]
        : [{ id: 'teacher-b', full_name: 'Teacher B' }],
    ),
    useStepStatus: () => ({ mutateAsync: mockSetStepStatus }),
    useFollowUpAction: () => ({ mutateAsync: jest.fn(), isPending: false }),
    __mockSetStepStatus: mockSetStepStatus,
  };
});

jest.mock('@/hooks/api-cycle', () => ({
  useStepsForPlans: (planIds: string[]) => {
    const steps = [
      { id: 'step-a', action_plan_id: 'plan-a', title: 'Guided reading', status: 'in_progress', due_date: '2026-10-25' },
      { id: 'step-b', action_plan_id: 'plan-b', title: 'Number lines', status: 'pending', due_date: '2026-10-26' },
    ];
    return {
      steps: steps.filter((step) => planIds.includes(step.action_plan_id)),
      isLoading: false,
      error: null,
      refetch: jest.fn(),
    };
  },
}));

describe('Classroom Coach teacher follow-up tracking', () => {
  it('shows only this school’s persisted follow-ups, newest first, with reported and verified states distinct', async () => {
    const view = await render(<TeacherFollowUpTracking schoolId="school-a" />);

    expect(view.getByText('Most recent follow-up')).toBeTruthy();
    expect(view.getByText('Earlier follow-up')).toBeTruthy();
    expect(view.queryByText('Other school follow-up')).toBeNull();
    expect(view.getAllByText('Responded')).toHaveLength(2);
    expect(view.getAllByText('In Progress')).toHaveLength(2);
    expect(view.getAllByText(/Mentor verified/)).toHaveLength(2);

    const rendered = JSON.stringify(view.toJSON());
    expect(rendered.indexOf('Most recent follow-up')).toBeLessThan(rendered.indexOf('Earlier follow-up'));

    await fireEvent.press(view.getAllByLabelText('Update follow-up for Teacher A')[0]);
    expect(view.getByText('Record evidence submitted')).toBeTruthy();

    await fireEvent.press(view.getAllByLabelText('Mark action Completed')[0]);
    const hooks = jest.requireMock('@/hooks/api') as { __mockSetStepStatus: jest.Mock };
    expect(hooks.__mockSetStepStatus).toHaveBeenCalledWith({ id: 'step-a', status: 'completed' });
  });
});
