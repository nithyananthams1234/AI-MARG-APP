import { fireEvent, render } from '@testing-library/react-native';
import { jest } from '@jest/globals';

import { SchoolDetail } from '@/components/schools/school-detail';
import { SchoolList } from '@/components/schools/school-list';
import { VisitDetail } from '@/components/visits/visit-detail';

const mockSchool = {
  id: 'school-1',
  name: 'Fictional Government Higher Secondary School',
  code: 'FGHSS',
  address: 'Example locality',
  district: 'Example district',
  block: 'Example block',
  state: 'Tamil Nadu',
  is_active: true,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  version: 1,
};
const mockVisit = {
  id: 'visit-1',
  school_id: 'school-1',
  scheduled_at: '2030-02-10T09:30:00Z',
  started_at: null,
  completed_at: null,
  status: 'planned',
  notes: 'Review formative assessment practice.',
  created_at: '2030-02-01T09:30:00Z',
  updated_at: '2030-02-01T09:30:00Z',
  version: 1,
};
const mockObservation = {
  id: 'observation-1',
  school_visit_id: 'visit-1',
  teacher_id: 'teacher-1',
  classroom_id: 'classroom-1',
  subject: 'Mathematics',
  topic: 'Fractions',
  notes: 'Learners compared equivalent fractions using visual models.',
  status: 'submitted',
  created_at: '2030-02-10T10:00:00Z',
  updated_at: '2030-02-10T10:00:00Z',
};
const mockGap = {
  id: 'gap-1',
  observation_id: 'observation-1',
  observation_finding_id: null,
  title: 'Equivalent fraction reasoning',
  description: 'Some learners need support explaining equivalent values.',
  subject: 'Mathematics',
  grade: '6',
  severity: 'medium',
  status: 'identified',
  created_at: '2030-02-10T10:00:00Z',
  updated_at: '2030-02-10T10:00:00Z',
};
const mockRecommendation = {
  id: 'recommendation-1',
  learning_gap_id: 'gap-1',
  title: 'Use fraction strips',
  description: 'Compare equivalent fractions with visual models.',
  rationale: 'Visual comparison supports explanation.',
  category: 'instruction',
  status: 'mentor_approved',
  mentor_comment: null,
  created_at: '2030-02-10T10:00:00Z',
  updated_at: '2030-02-10T10:00:00Z',
  version: 1,
};
const mockPlan = {
  id: 'plan-1',
  recommendation_id: 'recommendation-1',
  title: 'Strengthen fraction reasoning',
  description: 'Use visual models in weekly practice.',
  responsible_person: 'Teacher',
  start_date: '2030-02-11',
  due_date: '2030-03-01',
  status: 'in_progress',
  mentor_comment: null,
  created_at: '2030-02-10T10:00:00Z',
  updated_at: '2030-02-10T10:00:00Z',
  version: 1,
};
const mockTeacher = {
  id: 'teacher-1',
  full_name: 'Fictional Teacher',
  employee_code: 'T-001',
  email: null,
  phone: null,
  is_active: true,
  created_at: '2030-01-01T00:00:00Z',
  updated_at: '2030-01-01T00:00:00Z',
  version: 1,
};
const mockClassroom = {
  id: 'classroom-1',
  school_id: 'school-1',
  name: 'Grade 6 A',
  grade: '6',
  section: 'A',
  academic_year: '2030',
  capacity: 35,
  created_at: '2030-01-01T00:00:00Z',
  updated_at: '2030-01-01T00:00:00Z',
  version: 1,
};

jest.mock('@/hooks/api', () => {
  const ready = (data: unknown) => ({ data, isLoading: false, isRefetching: false, error: null, refetch: jest.fn() });
  return {
    useSchools: () => ready([mockSchool, { ...mockSchool, id: 'school-2', name: 'Fictional Middle School', code: 'FMS', district: 'Other district', is_active: false }]),
    useClassrooms: () => ready([mockClassroom, { ...mockClassroom, id: 'classroom-2', school_id: 'school-2' }]),
    useVisits: () => ready([mockVisit, { ...mockVisit, id: 'visit-old', status: 'completed', scheduled_at: '2029-12-01T09:30:00Z' }]),
    useObservations: () => ready([mockObservation]),
    useGaps: () => ready([mockGap]),
    useRecommendations: () => ready([mockRecommendation]),
    usePlans: () => ready([mockPlan]),
    useSchoolTeachers: () => ready([mockTeacher]),
    useSchool: () => ready(mockSchool),
    useSchoolReport: () => ready({
      school_id: 'school-1',
      school_name: mockSchool.name,
      total_visits: 2,
      completed_visits: 1,
      total_observations: 1,
      total_learning_gaps: 1,
      open_learning_gaps: 1,
      total_action_plans: 1,
      completed_action_plans: 0,
      open_follow_ups: 1,
    }),
    useTimetable: () => ready([]),
    useSchoolTimetables: () => [],
    useSteps: () => ready([{
      id: 'step-1',
      action_plan_id: 'plan-1',
      title: 'Model fraction comparison',
      description: 'Use fraction strips during group practice.',
      responsible_person: 'Teacher',
      due_date: '2030-02-20',
      status: 'in_progress',
      completion_notes: null,
      created_at: '2030-02-10T10:00:00Z',
      updated_at: '2030-02-10T10:00:00Z',
      version: 1,
    }]),
    useFollowUps: () => ready([{
      id: 'follow-up-1',
      action_plan_step_id: 'step-1',
      teacher_id: 'teacher-1',
      description: 'Share progress after the next lesson.',
      status: 'teacher_responded',
      teacher_response: 'I used fraction strips in group practice.',
      mentor_notes: null,
      responded_at: '2030-02-18T10:00:00Z',
      verified_at: null,
      created_at: '2030-02-10T10:00:00Z',
      updated_at: '2030-02-18T10:00:00Z',
      version: 1,
    }]),
    useEvidence: () => ready([]),
    useVisit: () => ready(mockVisit),
    useVisitStatus: () => ({ mutate: jest.fn(), isPending: false, error: null, variables: undefined }),
  };
});

describe('MARG Schools workflow', () => {
  it('shows API-derived directory counts and filters schools by status and district', async () => {
    const view = await render(<SchoolList onOpen={jest.fn()} onBack={jest.fn()} />);

    expect(view.getAllByText('Teachers: 1')).toHaveLength(2);
    expect(view.getAllByText('Classrooms: 1')).toHaveLength(2);
    expect(view.getByText('Pending action plans: 1')).toBeTruthy();

    await fireEvent.press(view.getByRole('tab', { name: /Inactive/ }));
    expect(view.getByText('Fictional Middle School')).toBeTruthy();
    expect(view.queryByText(mockSchool.name)).toBeNull();
  });

  it('shows linked observation, approved recommendation, teacher response, and separate mentor verification state', async () => {
    const view = await render(
      <SchoolDetail
        schoolId="school-1"
        onBack={jest.fn()}
        onPlanVisit={jest.fn()}
        onAskCoach={jest.fn()}
        onOpenVisit={jest.fn()}
        onOpenObservation={jest.fn()}
      />,
    );

    expect(view.getByText('Equivalent fraction reasoning')).toBeTruthy();
    expect(view.getAllByText('Use fraction strips').length).toBeGreaterThan(0);
    expect(view.getByText('Teacher response: I used fraction strips in group practice.')).toBeTruthy();
    expect(view.getByText('Not verified')).toBeTruthy();
  });

  it('opens Classroom Coach with the current visit and school context', async () => {
    const onOpenCoach = jest.fn();
    const view = await render(
      <VisitDetail
        visitId="visit-1"
        onBack={jest.fn()}
        onRecordObservation={jest.fn()}
        onOpenObservation={jest.fn()}
        onOpenSchool={jest.fn()}
        onOpenCoach={onOpenCoach}
      />,
    );

    fireEvent.press(view.getByRole('button', { name: 'Open Classroom Coach for this visit' }));
    expect(onOpenCoach).toHaveBeenCalledWith('visit-1', 'school-1', mockSchool.name);
  });
});
