/**
 * Typed functions for every backend operation used by the app.
 * Paths, methods, query names and bodies match the backend OpenAPI schema
 * (types in ./generated.ts are generated from it).
 */
import { AI_TIMEOUT_MS } from '@/lib/config';

import { api } from './client';
import type * as T from './generated';

const get = async <R>(url: string, params?: Record<string, unknown>) => (await api.get<R>(url, { params: clean(params) })).data;
const post = async <R>(url: string, body?: unknown, timeout?: number) => (await api.post<R>(url, body, timeout ? { timeout } : undefined)).data;
const put = async <R>(url: string, body: unknown) => (await api.put<R>(url, body)).data;
const patch = async <R>(url: string, body?: unknown) => (await api.patch<R>(url, body ?? {})).data;
const del = async (url: string) => {
  await api.delete(url);
};

function clean(params?: Record<string, unknown>) {
  if (!params) return undefined;
  return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''));
}

// ---- Auth / profile -------------------------------------------------------
export const authApi = {
  me: () => get<T.CurrentUserResponse>('/auth/me'),
};

// ---- Schools, teachers, classrooms, timetables ----------------------------
export const schoolsApi = {
  list: () => get<T.SchoolResponse[]>('/schools/'),
  get: (id: string) => get<T.SchoolResponse>(`/schools/${id}`),
  teachers: (schoolId: string) => get<T.TeacherResponse[]>(`/schools/${schoolId}/teachers`),
  report: (schoolId: string) => get<T.SchoolReportResponse>(`/reports/schools/${schoolId}`),
};

export const classroomsApi = {
  list: (schoolId?: string) => get<T.ClassroomResponse[]>('/classrooms/', { school_id: schoolId }),
};

export const timetablesApi = {
  list: (classroomId: string, dayOfWeek?: string) =>
    get<T.TimetableResponse[]>('/timetables/', { classroom_id: classroomId, day_of_week: dayOfWeek }),
};

export const teachersApi = {
  list: () => get<T.TeacherResponse[]>('/teachers/'),
};

// ---- Visits & observations --------------------------------------------------
export const visitsApi = {
  list: (p?: { school_id?: string; visit_status?: T.SchoolVisitResponse['status'] }) => get<T.SchoolVisitResponse[]>('/school-visits/', p),
  get: (id: string) => get<T.SchoolVisitResponse>(`/school-visits/${id}`),
  create: (body: T.SchoolVisitCreate) => post<T.SchoolVisitResponse>('/school-visits/', body),
  update: (id: string, body: T.SchoolVisitUpdate) => put<T.SchoolVisitResponse>(`/school-visits/${id}`, body),
  setStatus: (id: string, status: T.SchoolVisitStatusUpdate['status']) =>
    patch<T.SchoolVisitResponse>(`/school-visits/${id}/status`, { status }),
};

export const observationsApi = {
  list: (p?: { school_visit_id?: string; teacher_id?: string; classroom_id?: string; observation_status?: string }) =>
    get<T.ObservationResponse[]>('/observations/', p),
  get: (id: string) => get<T.ObservationResponse>(`/observations/${id}`),
  create: (body: T.ObservationCreate) => post<T.ObservationResponse>('/observations/', body),
  update: (id: string, body: T.ObservationUpdate) => put<T.ObservationResponse>(`/observations/${id}`, body),
  setStatus: (id: string, status: string) => patch<T.ObservationResponse>(`/observations/${id}/status`, { status }),
  remove: (id: string) => del(`/observations/${id}`),
};

export const findingsApi = {
  list: (p?: { observation_id?: string; finding_status?: string }) => get<T.ObservationFindingResponse[]>('/observation-findings/', p),
  create: (body: T.ObservationFindingCreate) => post<T.ObservationFindingResponse>('/observation-findings/', body),
  update: (id: string, body: T.ObservationFindingUpdate) => put<T.ObservationFindingResponse>(`/observation-findings/${id}`, body),
  decide: (id: string, body: T.ObservationFindingStatusUpdate) =>
    patch<T.ObservationFindingResponse>(`/observation-findings/${id}/decision`, body),
  remove: (id: string) => del(`/observation-findings/${id}`),
};

export const gapsApi = {
  list: (p?: { observation_id?: string; severity?: string; status?: string }) => get<T.LearningGapResponse[]>('/learning-gaps/', p),
  get: (id: string) => get<T.LearningGapResponse>(`/learning-gaps/${id}`),
  create: (body: T.LearningGapCreate) => post<T.LearningGapResponse>('/learning-gaps/', body),
  update: (id: string, body: T.LearningGapUpdate) => put<T.LearningGapResponse>(`/learning-gaps/${id}`, body),
  setStatus: (id: string, status: T.LearningGapStatusUpdate['status']) => patch<T.LearningGapResponse>(`/learning-gaps/${id}/status`, { status }),
};

export interface SchoolCoachHistoryRecord {
  visit: T.SchoolVisitResponse;
  observation: T.ObservationResponse | null;
  findings: T.ObservationFindingResponse[];
  gaps: T.LearningGapResponse[];
  teacherName?: string;
  classroomName?: string;
  classroomGrade?: string;
}

function visitDate(visit: T.SchoolVisitResponse) {
  return visit.completed_at ?? visit.started_at ?? visit.scheduled_at;
}

function historyDate(record: SchoolCoachHistoryRecord) {
  return record.observation?.created_at ?? visitDate(record.visit);
}

export const classroomCoachHistoryApi = {
  list: async (schoolId: string): Promise<SchoolCoachHistoryRecord[]> => {
    const [allVisits, teachers, classrooms] = await Promise.all([
      visitsApi.list({ school_id: schoolId }),
      schoolsApi.teachers(schoolId),
      classroomsApi.list(schoolId),
    ]);
    const visits = allVisits
      .filter((visit) => visit.status === 'completed' || visit.status === 'in_progress')
      .sort((a, b) => visitDate(b).localeCompare(visitDate(a)))
      .slice(0, 20);
    const observationsByVisit = await Promise.all(
      visits.map(async (visit) => ({
        visit,
        observations: await observationsApi.list({ school_visit_id: visit.id }),
      })),
    );
    const observations = observationsByVisit
      .flatMap(({ visit, observations: items }) => items.map((observation) => ({ visit, observation })))
      .sort((a, b) => b.observation.created_at.localeCompare(a.observation.created_at))
      .slice(0, 20);

    const records = await Promise.all(
      observations.map(async ({ visit, observation }): Promise<SchoolCoachHistoryRecord> => {
        const [findings, gaps] = await Promise.all([
          findingsApi.list({ observation_id: observation.id }),
          gapsApi.list({ observation_id: observation.id }),
        ]);
        return {
          visit,
          observation,
          findings,
          gaps,
          teacherName: teachers.find((teacher) => teacher.id === observation.teacher_id)?.full_name,
          classroomName: classrooms.find((classroom) => classroom.id === observation.classroom_id)?.name,
          classroomGrade: classrooms.find((classroom) => classroom.id === observation.classroom_id)?.grade,
        };
      }),
    );
    const visitsWithObservations = new Set(
      observationsByVisit.filter(({ observations: items }) => items.length > 0).map(({ visit }) => visit.id),
    );
    const visitsWithoutObservations = visits
      .filter((visit) => !visitsWithObservations.has(visit.id))
      .map((visit) => ({ visit, observation: null, findings: [], gaps: [] }));

    return [...records, ...visitsWithoutObservations].sort((a, b) =>
      historyDate(b).localeCompare(historyDate(a)),
    );
  },
};

export const recommendationsApi = {
  list: (p?: { learning_gap_id?: string; status?: string }) => get<T.RecommendationResponse[]>('/recommendations/', p),
  get: (id: string) => get<T.RecommendationResponse>(`/recommendations/${id}`),
  create: (body: T.RecommendationCreate) => post<T.RecommendationResponse>('/recommendations/', body),
  decide: (id: string, body: T.RecommendationDecision) => patch<T.RecommendationResponse>(`/recommendations/${id}/decision`, body),
};

// ---- Action plans, steps, follow-ups ---------------------------------------
export const plansApi = {
  list: (p?: { recommendation_id?: string; status?: string }) => get<T.ActionPlanResponse[]>('/action-plans/', p),
  get: (id: string) => get<T.ActionPlanResponse>(`/action-plans/${id}`),
  create: (body: T.ActionPlanCreate) => post<T.ActionPlanResponse>('/action-plans/', body),
  update: (id: string, body: T.ActionPlanUpdate) => put<T.ActionPlanResponse>(`/action-plans/${id}`, body),
  setStatus: (id: string, body: T.ActionPlanStatusUpdate) => patch<T.ActionPlanResponse>(`/action-plans/${id}/status`, body),
  remove: (id: string) => del(`/action-plans/${id}`),
};

export const stepsApi = {
  list: (actionPlanId: string) => get<T.ActionPlanStepResponse[]>('/action-plan-steps/', { action_plan_id: actionPlanId }),
  create: (body: T.ActionPlanStepCreate) => post<T.ActionPlanStepResponse>('/action-plan-steps/', body),
  setStatus: (id: string, body: T.ActionPlanStepStatusUpdate) => patch<T.ActionPlanStepResponse>(`/action-plan-steps/${id}/status`, body),
};

export const followUpsApi = {
  list: (p?: { action_plan_step_id?: string; teacher_id?: string; follow_up_status?: string }) => get<T.FollowUpResponse[]>('/follow-ups/', p),
  get: (id: string) => get<T.FollowUpResponse>(`/follow-ups/${id}`),
  create: (body: T.FollowUpCreate) => post<T.FollowUpResponse>('/follow-ups/', body),
  teacherResponse: (id: string, teacher_response: string) => patch<T.FollowUpResponse>(`/follow-ups/${id}/teacher-response`, { teacher_response }),
  evidence: (id: string, teacher_response: string) => patch<T.FollowUpResponse>(`/follow-ups/${id}/evidence`, { teacher_response }),
  mentorDecision: (id: string, body: T.FollowUpMentorDecision) => patch<T.FollowUpResponse>(`/follow-ups/${id}/mentor-decision`, body),
  close: (id: string) => patch<T.FollowUpResponse>(`/follow-ups/${id}/close`, { status: 'closed' }),
};

// ---- Evidence ---------------------------------------------------------------
export interface UploadFile {
  uri: string;
  name: string;
  type: string;
  /** Web only: the File/Blob to send. */
  blob?: Blob;
}

export const evidenceApi = {
  list: (p: { observation_id?: string; follow_up_id?: string }) => get<T.EvidenceResponse[]>('/evidence/', p),
  upload: async (target: { observation_id?: string; follow_up_id?: string }, file: UploadFile, description?: string) => {
    const form = new FormData();
    if (target.observation_id) form.append('observation_id', target.observation_id);
    if (target.follow_up_id) form.append('follow_up_id', target.follow_up_id);
    if (description) form.append('description', description);
    if (file.blob) form.append('file', file.blob, file.name);
    // React Native FormData file descriptor
    else form.append('file', { uri: file.uri, name: file.name, type: file.type } as unknown as Blob);
    return (await api.post<T.EvidenceResponse>('/evidence/', form, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
  },
};

// ---- Tasks & schedules ------------------------------------------------------
export const tasksApi = {
  list: (p?: { school_id?: string; status?: string; priority?: string }) => get<T.MentorTaskResponse[]>('/mentor-tasks/', p),
  create: (body: T.MentorTaskCreate) => post<T.MentorTaskResponse>('/mentor-tasks/', body),
  update: (id: string, body: T.MentorTaskUpdate) => put<T.MentorTaskResponse>(`/mentor-tasks/${id}`, body),
  setStatus: (id: string, status: T.MentorTaskStatusUpdate['status']) => patch<T.MentorTaskResponse>(`/mentor-tasks/${id}/status`, { status }),
  remove: (id: string) => del(`/mentor-tasks/${id}`),
};

export const schedulesApi = {
  list: (p?: { school_id?: string; status?: string; school_visit_id?: string }) => get<T.ScheduleResponse[]>('/schedules/', p),
  create: (body: T.ScheduleCreate) => post<T.ScheduleResponse>('/schedules/', body),
  decide: (id: string, status: T.ScheduleDecision['status']) => patch<T.ScheduleResponse>(`/schedules/${id}/decision`, { status }),
  dailyWorkload: (date: string) =>
    get<{ date: string; total_visits: number; total_minutes: number; total_hours: number }>('/schedules/workload/daily', { workload_date: date }),
};

// ---- Notifications & reports ------------------------------------------------
export const notificationsApi = {
  list: (limit = 50, offset = 0) => get<T.NotificationListResponse>('/notifications/', { limit, offset }),
  unreadCount: () => get<T.NotificationUnreadCountResponse>('/notifications/unread-count'),
  markRead: (id: string) => patch<T.NotificationResponse>(`/notifications/${id}/read`),
  markAllRead: () => patch<{ message: string }>('/notifications/read-all'),
};

export const reportsApi = {
  dashboard: () => get<T.MentorDashboardResponse>('/reports/dashboard'),
  learningGaps: () => get<T.LearningGapReportItem[]>('/reports/learning-gaps'),
  activity: (days = 7) => get<T.ActivityReportResponse>('/reports/activity', { days }),
};

// ---- Classroom Coach (educational LLM + RAG, via backend) ------------------
export const coachApi = {
  status: () => get<{ available: boolean; checks?: Record<string, string>; llm_model?: string; knowledge_chunks?: number }>('/coach/status'),
  chat: (body: T.CoachChatRequest) => post<T.CoachChatResponse>('/coach/chat', body, AI_TIMEOUT_MS),
};

export const aiJobsApi = {
  analyseObservation: (observationId: string) =>
    post<T.AIJobResponse>('/ai/jobs', { job_type: 'observation_analysis', entity_type: 'observation', entity_id: observationId }),
  get: (id: string) => get<T.AIJobResponse>(`/ai/jobs/${id}`),
  list: (status?: string) => get<T.AIJobResponse[]>('/ai/jobs', { status }),
  retry: (id: string) => patch<T.AIJobResponse>(`/ai/jobs/${id}/retry`),
  apply: (id: string, body: T.AIJobApplyRequest) => post<T.AIJobApplyResponse>(`/ai/jobs/${id}/apply`, body),
};

// ---- Mentor AI Assistant (Mentor Intelligence via backend) -----------------
export type MentorAgent =
  | 'task_prioritisation'
  | 'time_analysis'
  | 'schedule_analysis'
  | 'workload_analysis'
  | 'followup_analysis'
  | 'visit_planning'
  | 'daily_plan'
  | 'weekly_plan'
  | 'report'
  | 'teacher_message_draft';

/** Mentor Intelligence response envelope. */
export interface MiEnvelope<D> {
  schema_version: string;
  success: boolean;
  data: D;
  error?: { code: string; message: string } | null;
}

export interface MiExecution {
  execution_id: string;
  agent_id: string;
  status: string;
  ai_status: 'generated' | 'not_needed' | 'unavailable' | 'disabled' | string;
  replayed: boolean;
  created_at: string;
  finished_at: string | null;
  error: string | null;
  result: {
    facts: Record<string, unknown>;
    ai_insights: Record<string, unknown> | null;
    ai_status: string;
    drafts?: unknown[];
    data_source: string;
  } | null;
}

export interface MiProposal {
  proposal_id: string;
  agent_id: string;
  action_type: 'reschedule_visit' | 'schedule_visit' | 'send_teacher_message' | 'update_task_due_date' | string;
  autonomy_level: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired' | 'executed' | 'execution_failed';
  target_type: string;
  target_ref: string;
  payload: Record<string, unknown>;
  rationale: string;
  requires_external_execution: boolean;
  created_at: string;
  expires_at: string;
  execution_result?: Record<string, unknown> | null;
}

export const mentorAiApi = {
  status: () => get<{ available: boolean; details?: unknown }>('/mentor-ai/status'),
  run: (agent: MentorAgent, options: Record<string, unknown> = {}) =>
    post<MiEnvelope<MiExecution>>(`/mentor-ai/agents/${agent}`, { use_ai: true, ...options }, AI_TIMEOUT_MS),
  proposals: (status?: MiProposal['status']) => get<MiEnvelope<MiProposal[]>>('/mentor-ai/proposals', { status }),
  approve: (id: string, note?: string) => post<MiEnvelope<MiProposal>>(`/mentor-ai/proposals/${id}/approve`, { note }, AI_TIMEOUT_MS),
  reject: (id: string, note?: string) => post<MiEnvelope<MiProposal>>(`/mentor-ai/proposals/${id}/reject`, { note }),
  externalResult: (id: string, success: boolean, detail?: string) =>
    post<MiEnvelope<MiProposal>>(`/mentor-ai/proposals/${id}/external-result`, { success, detail }),
};

// ---- Offline sync -------------------------------------------------------------
export const syncApi = {
  push: (body: T.SyncBatchRequest) => post<T.SyncBatchResponse>('/sync/push', body),
};
