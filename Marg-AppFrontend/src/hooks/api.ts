/**
 * Data hooks for all screens (React Query). Screens must use these hooks
 * (or the services in '@/lib/api/services') instead of calling URLs directly.
 *
 * Offline-capable writes (visits, observations, tasks, follow-up responses)
 * fall back to the offline outbox when the server is unreachable.
 */
import { useMutation, useQueries, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query';

import type * as T from '@/lib/api/generated';
import {
  aiJobsApi,
  classroomCoachHistoryApi,
  classroomsApi,
  coachApi,
  evidenceApi,
  findingsApi,
  followUpsApi,
  gapsApi,
  mentorAiApi,
  notificationsApi,
  observationsApi,
  plansApi,
  recommendationsApi,
  reportsApi,
  schedulesApi,
  schoolsApi,
  stepsApi,
  tasksApi,
  timetablesApi,
  visitsApi,
  type MentorAgent,
  type MiProposal,
  type UploadFile,
} from '@/lib/api/services';
import { uuid4 } from '@/lib/ids';
import { runOrQueue } from '@/lib/query';

export const qk = {
  me: ['me'] as const,
  dashboard: ['reports', 'dashboard'] as const,
  activity: (days: number) => ['reports', 'activity', days] as const,
  gapReport: ['reports', 'learning-gaps'] as const,
  schools: ['schools'] as const,
  school: (id: string) => ['schools', id] as const,
  schoolReport: (id: string) => ['schools', id, 'report'] as const,
  schoolTeachers: (id: string) => ['schools', id, 'teachers'] as const,
  classrooms: (schoolId?: string) => ['classrooms', schoolId ?? 'all'] as const,
  timetable: (classroomId: string) => ['timetables', classroomId] as const,
  visits: (p?: object) => ['visits', p ?? {}] as const,
  visit: (id: string) => ['visit', id] as const,
  observations: (p?: object) => ['observations', p ?? {}] as const,
  observation: (id: string) => ['observation', id] as const,
  findings: (observationId?: string) => ['findings', observationId ?? 'all'] as const,
  gaps: (p?: object) => ['gaps', p ?? {}] as const,
  recommendations: (p?: object) => ['recommendations', p ?? {}] as const,
  plans: (p?: object) => ['plans', p ?? {}] as const,
  steps: (planId: string) => ['steps', planId] as const,
  followUps: (p?: object) => ['follow-ups', p ?? {}] as const,
  evidence: (p: object) => ['evidence', p] as const,
  tasks: (p?: object) => ['tasks', p ?? {}] as const,
  schedules: (p?: object) => ['schedules', p ?? {}] as const,
  notifications: ['notifications'] as const,
  aiJob: (id: string) => ['ai-job', id] as const,
  coachStatus: ['coach-status'] as const,
  classroomCoachHistory: (schoolId: string) => ['classroom-coach', 'history', schoolId] as const,
  mentorAiStatus: ['mentor-ai', 'status'] as const,
  proposals: (status?: string) => ['mentor-ai', 'proposals', status ?? 'all'] as const,
};

/** Invalidate several query families after a write. */
function useInvalidate() {
  const qc = useQueryClient();
  return (...keys: QueryKey[]) => Promise.all(keys.map((k) => qc.invalidateQueries({ queryKey: k })));
}

const ROOT = {
  visits: ['visits'],
  visit: ['visit'],
  observations: ['observations'],
  observation: ['observation'],
  findings: ['findings'],
  gaps: ['gaps'],
  recs: ['recommendations'],
  plans: ['plans'],
  steps: ['steps'],
  followUps: ['follow-ups'],
  tasks: ['tasks'],
  schedules: ['schedules'],
  reports: ['reports'],
  notifications: ['notifications'],
  evidence: ['evidence'],
};

// ---------------------------------------------------------------- reads
export const useDashboard = () => useQuery({ queryKey: qk.dashboard, queryFn: reportsApi.dashboard });
export const useActivity = (days = 7) => useQuery({ queryKey: qk.activity(days), queryFn: () => reportsApi.activity(days) });
export const useGapReport = () => useQuery({ queryKey: qk.gapReport, queryFn: reportsApi.learningGaps });

export const useSchools = () => useQuery({ queryKey: qk.schools, queryFn: schoolsApi.list });
export const useSchool = (id?: string) => useQuery({ queryKey: qk.school(id ?? ''), queryFn: () => schoolsApi.get(id!), enabled: !!id });
export const useSchoolReport = (id?: string) =>
  useQuery({ queryKey: qk.schoolReport(id ?? ''), queryFn: () => schoolsApi.report(id!), enabled: !!id });
export const useSchoolTeachers = (id?: string) =>
  useQuery({ queryKey: qk.schoolTeachers(id ?? ''), queryFn: () => schoolsApi.teachers(id!), enabled: !!id });
export const useClassrooms = (schoolId?: string) =>
  useQuery({ queryKey: qk.classrooms(schoolId), queryFn: () => classroomsApi.list(schoolId) });
export const useTimetable = (classroomId?: string) =>
  useQuery({ queryKey: qk.timetable(classroomId ?? ''), queryFn: () => timetablesApi.list(classroomId!), enabled: !!classroomId });
export const useSchoolTimetables = (classroomIds: string[]) =>
  useQueries({
    queries: classroomIds.map((classroomId) => ({
      queryKey: qk.timetable(classroomId),
      queryFn: () => timetablesApi.list(classroomId),
    })),
  });

export const useVisits = (p?: Parameters<typeof visitsApi.list>[0]) => useQuery({ queryKey: qk.visits(p), queryFn: () => visitsApi.list(p) });
export const useVisit = (id?: string) => useQuery({ queryKey: qk.visit(id ?? ''), queryFn: () => visitsApi.get(id!), enabled: !!id });

export const useObservations = (p?: Parameters<typeof observationsApi.list>[0]) =>
  useQuery({ queryKey: qk.observations(p), queryFn: () => observationsApi.list(p) });
export const useSchoolCoachHistory = (schoolId?: string) =>
  useQuery({
    queryKey: qk.classroomCoachHistory(schoolId ?? ''),
    queryFn: () => classroomCoachHistoryApi.list(schoolId!),
    enabled: !!schoolId,
  });
export const useObservation = (id?: string) =>
  useQuery({ queryKey: qk.observation(id ?? ''), queryFn: () => observationsApi.get(id!), enabled: !!id });
export const useFindings = (observationId?: string) =>
  useQuery({ queryKey: qk.findings(observationId), queryFn: () => findingsApi.list({ observation_id: observationId }) });
export const useGaps = (p?: Parameters<typeof gapsApi.list>[0]) => useQuery({ queryKey: qk.gaps(p), queryFn: () => gapsApi.list(p) });
export const useRecommendations = (p?: Parameters<typeof recommendationsApi.list>[0]) =>
  useQuery({ queryKey: qk.recommendations(p), queryFn: () => recommendationsApi.list(p) });
export const usePlans = (p?: Parameters<typeof plansApi.list>[0]) => useQuery({ queryKey: qk.plans(p), queryFn: () => plansApi.list(p) });
export const useSteps = (planId?: string) =>
  useQuery({ queryKey: qk.steps(planId ?? ''), queryFn: () => stepsApi.list(planId!), enabled: !!planId });
export const useFollowUps = (p?: Parameters<typeof followUpsApi.list>[0]) =>
  useQuery({ queryKey: qk.followUps(p), queryFn: () => followUpsApi.list(p) });
export const useEvidence = (p: { observation_id?: string; follow_up_id?: string }) =>
  useQuery({ queryKey: qk.evidence(p), queryFn: () => evidenceApi.list(p), enabled: !!(p.observation_id || p.follow_up_id) });
export const useTasks = (p?: Parameters<typeof tasksApi.list>[0]) => useQuery({ queryKey: qk.tasks(p), queryFn: () => tasksApi.list(p) });
export const useSchedules = (p?: Parameters<typeof schedulesApi.list>[0]) =>
  useQuery({ queryKey: qk.schedules(p), queryFn: () => schedulesApi.list(p) });
export const useNotifications = () =>
  useQuery({ queryKey: qk.notifications, queryFn: () => notificationsApi.list(), refetchInterval: 60_000 });

// ---------------------------------------------------------------- visits
export function useCreateVisit() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: T.SchoolVisitCreate) => {
      const id = uuid4();
      return runOrQueue(() => visitsApi.create(body), {
        entity_type: 'school_visit', entity_id: id, operation_type: 'create', payload: { ...body }, client_version: 1,
        label: 'Plan school visit',
      });
    },
    onSettled: () => invalidate(ROOT.visits, ROOT.reports),
  });
}

export function useVisitStatus() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ visit, status }: { visit: T.SchoolVisitResponse; status: T.SchoolVisitStatusUpdate['status'] }) =>
      runOrQueue(() => visitsApi.setStatus(visit.id, status), {
        entity_type: 'school_visit', entity_id: visit.id, operation_type: 'update', payload: { _action: 'status', status },
        client_version: visit.version, label: `Visit → ${status.replace('_', ' ')}`,
      }),
    onSettled: () => invalidate(ROOT.visits, ROOT.visit, ROOT.reports),
  });
}

export function useUpdateVisit() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ visit, body }: { visit: T.SchoolVisitResponse; body: T.SchoolVisitUpdate }) =>
      runOrQueue(() => visitsApi.update(visit.id, body), {
        entity_type: 'school_visit', entity_id: visit.id, operation_type: 'update', payload: { ...body },
        client_version: visit.version, label: 'Edit visit',
      }),
    onSettled: () => invalidate(ROOT.visits, ROOT.visit),
  });
}

// ---------------------------------------------------------------- observations
export function useCreateObservation() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: T.ObservationCreate) => {
      const id = uuid4();
      return runOrQueue(() => observationsApi.create(body), {
        entity_type: 'observation', entity_id: id, operation_type: 'create', payload: { ...body }, client_version: 1,
        label: `Record observation (${body.subject})`,
      });
    },
    onSettled: () => invalidate(ROOT.observations, ROOT.reports),
  });
}

export function useUpdateObservation() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ observation, body }: { observation: T.ObservationResponse; body: T.ObservationUpdate }) =>
      runOrQueue(() => observationsApi.update(observation.id, body), {
        entity_type: 'observation', entity_id: observation.id, operation_type: 'update', payload: { ...body },
        client_version: observation.version ?? 1, label: 'Edit observation notes',
      }),
    onSettled: () => invalidate(ROOT.observations, ROOT.observation),
  });
}

export function useObservationStatus() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ observation, status }: { observation: T.ObservationResponse; status: string }) =>
      runOrQueue(() => observationsApi.setStatus(observation.id, status), {
        entity_type: 'observation', entity_id: observation.id, operation_type: 'update', payload: { _action: 'status', status },
        client_version: observation.version ?? 1, label: `Observation → ${status}`,
      }),
    onSettled: () => invalidate(ROOT.observations, ROOT.observation, ROOT.reports),
  });
}

// ---------------------------------------------------------------- findings / gaps / recommendations (online)
export function useCreateFinding() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: findingsApi.create, onSettled: () => invalidate(ROOT.findings) });
}
export function useDecideFinding() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & T.ObservationFindingStatusUpdate) => findingsApi.decide(id, body),
    onSettled: () => invalidate(ROOT.findings),
  });
}
export function useCreateGap() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: gapsApi.create, onSettled: () => invalidate(ROOT.gaps, ROOT.reports) });
}
export function useGapStatus() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: T.LearningGapStatusUpdate['status'] }) => gapsApi.setStatus(id, status),
    onSettled: () => invalidate(ROOT.gaps, ROOT.reports),
  });
}
export function useCreateRecommendation() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: recommendationsApi.create, onSettled: () => invalidate(ROOT.recs, ROOT.reports) });
}
export function useDecideRecommendation() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & T.RecommendationDecision) => recommendationsApi.decide(id, body),
    onSettled: () => invalidate(ROOT.recs, ROOT.reports),
  });
}

// ---------------------------------------------------------------- action plans / steps / follow-ups
export function useCreatePlan() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: plansApi.create, onSettled: () => invalidate(ROOT.plans, ROOT.reports) });
}
export function usePlanStatus() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & T.ActionPlanStatusUpdate) => plansApi.setStatus(id, body),
    onSettled: () => invalidate(ROOT.plans, ROOT.reports),
  });
}
export function useCreateStep() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: stepsApi.create, onSettled: () => invalidate(ROOT.steps) });
}
export function useStepStatus() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & T.ActionPlanStepStatusUpdate) => stepsApi.setStatus(id, body),
    onSettled: () => invalidate(ROOT.steps),
  });
}
export function useCreateFollowUp() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: followUpsApi.create, onSettled: () => invalidate(ROOT.followUps, ROOT.reports) });
}

type FollowUpAction =
  | { kind: 'teacher_response'; text: string }
  | { kind: 'evidence'; text: string }
  | { kind: 'mentor_decision'; status: 'mentor_verified' | 'needs_revision'; notes?: string }
  | { kind: 'close' };

export function useFollowUpAction() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ followUp, action }: { followUp: T.FollowUpResponse; action: FollowUpAction }) => {
      const version = followUp.version ?? 1;
      switch (action.kind) {
        case 'teacher_response':
          return runOrQueue(() => followUpsApi.teacherResponse(followUp.id, action.text), {
            entity_type: 'follow_up', entity_id: followUp.id, operation_type: 'update',
            payload: { _action: 'teacher_response', teacher_response: action.text }, client_version: version,
            label: 'Record teacher response',
          });
        case 'evidence':
          return runOrQueue(() => followUpsApi.evidence(followUp.id, action.text), {
            entity_type: 'follow_up', entity_id: followUp.id, operation_type: 'update',
            payload: { _action: 'evidence', teacher_response: action.text }, client_version: version,
            label: 'Record evidence submitted',
          });
        case 'mentor_decision':
          return followUpsApi.mentorDecision(followUp.id, { status: action.status, mentor_notes: action.notes ?? null });
        case 'close':
          return followUpsApi.close(followUp.id);
      }
    },
    onSettled: () => invalidate(ROOT.followUps, ROOT.reports, ROOT.notifications),
  });
}

export function useUploadEvidence() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ target, file, description }: { target: { observation_id?: string; follow_up_id?: string }; file: UploadFile; description?: string }) =>
      evidenceApi.upload(target, file, description),
    onSettled: () => invalidate(ROOT.evidence),
  });
}

// ---------------------------------------------------------------- tasks
export function useCreateTask() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: (body: T.MentorTaskCreate) => {
      const id = uuid4();
      return runOrQueue(() => tasksApi.create(body), {
        entity_type: 'mentor_task', entity_id: id, operation_type: 'create', payload: { ...body }, client_version: 1,
        label: `Create task: ${body.title}`,
      });
    },
    onSettled: () => invalidate(ROOT.tasks, ROOT.reports),
  });
}
export function useUpdateTask() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ task, body }: { task: T.MentorTaskResponse; body: T.MentorTaskUpdate }) =>
      runOrQueue(() => tasksApi.update(task.id, body), {
        entity_type: 'mentor_task', entity_id: task.id, operation_type: 'update', payload: { ...body },
        client_version: task.version ?? 1, label: `Edit task: ${task.title}`,
      }),
    onSettled: () => invalidate(ROOT.tasks, ROOT.reports),
  });
}
export function useTaskStatus() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ task, status }: { task: T.MentorTaskResponse; status: T.MentorTaskStatusUpdate['status'] }) =>
      runOrQueue(() => tasksApi.setStatus(task.id, status), {
        entity_type: 'mentor_task', entity_id: task.id, operation_type: 'update', payload: { _action: 'status', status },
        client_version: task.version ?? 1, label: `Task → ${status.replace('_', ' ')}: ${task.title}`,
      }),
    onSettled: () => invalidate(ROOT.tasks, ROOT.reports),
  });
}

// ---------------------------------------------------------------- schedules
export function useCreateSchedule() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: schedulesApi.create, onSettled: () => invalidate(ROOT.schedules) });
}
export function useDecideSchedule() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'accepted' | 'rejected' }) => schedulesApi.decide(id, status),
    onSettled: () => invalidate(ROOT.schedules, ROOT.visits),
  });
}

// ---------------------------------------------------------------- notifications
export function useMarkNotificationRead() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: notificationsApi.markRead, onSettled: () => invalidate(ROOT.notifications, ROOT.reports) });
}
export function useMarkAllNotificationsRead() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: notificationsApi.markAllRead, onSettled: () => invalidate(ROOT.notifications, ROOT.reports) });
}

// ---------------------------------------------------------------- Classroom Coach
export const useCoachStatus = () => useQuery({ queryKey: qk.coachStatus, queryFn: coachApi.status, staleTime: 60_000 });
export const useCoachChat = () => useMutation({ mutationFn: coachApi.chat });

/** Start AI analysis of an observation and poll until it finishes. */
export function useAnalyseObservation() {
  return useMutation({ mutationFn: (observationId: string) => aiJobsApi.analyseObservation(observationId) });
}
export function useAiJob(id?: string) {
  return useQuery({
    queryKey: qk.aiJob(id ?? ''),
    queryFn: () => aiJobsApi.get(id!),
    enabled: !!id,
    refetchInterval: (q) => (q.state.data && ['completed', 'failed', 'cancelled'].includes(q.state.data.status) ? false : 2500),
  });
}
export function useApplyAiJob() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: T.AIJobApplyRequest }) => aiJobsApi.apply(id, body),
    onSettled: () => invalidate(ROOT.findings, ROOT.gaps, ROOT.recs, ROOT.reports),
  });
}

// ---------------------------------------------------------------- Mentor AI Assistant
export const useMentorAiStatus = () => useQuery({ queryKey: qk.mentorAiStatus, queryFn: mentorAiApi.status, staleTime: 60_000 });
export const useRunMentorAgent = () =>
  useMutation({ mutationFn: ({ agent, options }: { agent: MentorAgent; options?: Record<string, unknown> }) => mentorAiApi.run(agent, options) });
export const useProposals = (status?: MiProposal['status']) =>
  useQuery({ queryKey: qk.proposals(status), queryFn: () => mentorAiApi.proposals(status) });
export function useDecideProposal() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, approve, note }: { id: string; approve: boolean; note?: string }) =>
      approve ? mentorAiApi.approve(id, note) : mentorAiApi.reject(id, note),
    onSettled: () => invalidate(['mentor-ai'], ROOT.visits, ROOT.tasks, ROOT.notifications, ROOT.reports),
  });
}
export function useProposalExternalResult() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, success, detail }: { id: string; success: boolean; detail?: string }) => mentorAiApi.externalResult(id, success, detail),
    onSettled: () => invalidate(['mentor-ai']),
  });
}
