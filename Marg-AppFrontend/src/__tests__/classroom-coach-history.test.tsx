import { fireEvent, render } from '@testing-library/react-native';

import ClassroomCoachScreen from '@/app/classroom-coach';

jest.mock('expo-router', () => ({
  useLocalSearchParams: () => ({}),
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock('@/hooks/api', () => {
  const schools = [
    { id: 'school-a', name: 'North School' },
    { id: 'school-b', name: 'South School' },
  ];
  const records = {
    'school-a': [
      {
        visit: { id: 'visit-a', scheduled_at: '2026-10-10T09:00:00Z', started_at: null, completed_at: null, status: 'completed', notes: null },
        observation: {
          id: 'observation-a',
          created_at: '2026-10-10T09:00:00Z',
          subject: 'Mathematics',
          topic: 'Fractions',
          notes: 'Learners compared equivalent fractions.',
        },
        teacherName: 'Teacher A',
        classroomName: 'Grade 6',
        classroomGrade: '6',
        findings: [{ id: 'finding-a', status: 'mentor_approved', title: 'Use visual models', description: 'Learners benefited from concrete examples.' }],
        gaps: [{ id: 'gap-a', severity: 'medium', status: 'identified', title: 'Fraction equivalence', description: 'Some learners need more practice.' }],
      },
    ],
    'school-b': [
      {
        visit: { id: 'visit-b', scheduled_at: '2026-10-11T09:00:00Z', started_at: null, completed_at: null, status: 'completed', notes: null },
        observation: {
          id: 'observation-b',
          created_at: '2026-10-11T09:00:00Z',
          subject: 'Science',
          topic: 'Plants',
          notes: 'Learners classified leaves.',
        },
        teacherName: 'Teacher B',
        classroomName: 'Grade 5',
        classroomGrade: '5',
        findings: [],
        gaps: [],
      },
    ],
  };
  const mockCoachChat = { mutate: jest.fn() };
  const mockHistorySelections: (string | undefined)[] = [];
  return {
    __esModule: true,
    useSchools: () => ({ data: schools, isLoading: false, error: null, refetch: jest.fn() }),
    useSchoolCoachHistory: (schoolId?: string) => {
      mockHistorySelections.push(schoolId);
      return { data: schoolId ? records[schoolId as keyof typeof records] : undefined, isLoading: false, error: null, refetch: jest.fn() };
    },
    useCoachChat: () => mockCoachChat,
    mockHistorySelections,
  };
});

jest.mock('@/components/coach/context-picker', () => ({
  ContextPicker: () => null,
  observationLabel: () => 'Selected observation',
}));

jest.mock('@/components/coach/teacher-follow-up-tracking', () => ({
  TeacherFollowUpTracking: () => null,
}));

describe('Classroom Coach school history', () => {
  it('loads records per selected school and sends explicitly historical context with a chat question', async () => {
    const view = await render(<ClassroomCoachScreen />);
    const hooks = jest.requireMock('@/hooks/api') as {
      __esModule: boolean;
      useCoachChat: () => { mutate: jest.Mock };
      mockHistorySelections: (string | undefined)[];
    };

    expect(view.getByText('Select School')).toBeTruthy();
    expect(view.getByText('Previous Records & Observations')).toBeTruthy();
    expect(view.queryByText('Ask your first question')).toBeNull();
    expect(view.getByText('Choose a school')).toBeTruthy();

    await fireEvent.press(view.getByLabelText('Select school. No school selected'));
    await fireEvent.press(view.getByText('North School'));
    expect(view.getByText('Learners compared equivalent fractions.')).toBeTruthy();
    expect(view.getByText(/Teacher A/)).toBeTruthy();
    expect(view.getByText(/Fraction equivalence/)).toBeTruthy();

    await fireEvent.press(view.getByLabelText('Select school. North School'));
    await fireEvent.press(view.getByText('South School'));
    expect(view.getByText('Learners classified leaves.')).toBeTruthy();
    expect(view.queryByText('Learners compared equivalent fractions.')).toBeNull();
    expect(hooks.mockHistorySelections).toContain('school-a');
    expect(hooks.mockHistorySelections).toContain('school-b');

    await fireEvent.changeText(view.getByLabelText('Question for the Classroom Coach'), 'How can I support this class?');
    await fireEvent.press(view.getByLabelText('Ask the Coach'));
    const mutation = hooks.useCoachChat().mutate;
    const request = mutation.mock.calls.at(-1)?.[0] as { question: string; context?: { notes?: string } };
    expect(request.question).toBe('How can I support this class?');
    expect(request.context?.notes).toContain('Selected school: South School.');
    expect(request.context?.notes).toContain('HISTORICAL REFERENCE ONLY');
    expect(request.context?.notes).toContain('Past observation');
  });
});
