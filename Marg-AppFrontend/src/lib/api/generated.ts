// AUTO-GENERATED from the MARG backend OpenAPI schema.
// Do not edit by hand: run `python scripts/generate_ts_types.py` in Marg-AppBackend.

export interface AIJobApplyRequest {
  finding_indexes?: number[];
  learning_gap_indexes?: number[];
  recommendations?: AIRecommendationSelection[];
}

export interface AIJobApplyResponse {
  finding_ids: string[];
  learning_gap_ids: string[];
  recommendation_ids: string[];
}

export interface AIJobCreate {
  job_type: 'observation_analysis' | 'learning_gap_analysis' | 'recommendation_generation' | 'action_plan_suggestion';
  entity_type: string;
  entity_id: string;
  input_payload?: Record<string, unknown>;
}

export interface AIJobResponse {
  id: string;
  job_type: string;
  entity_type: string | null;
  entity_id: string | null;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  result_payload: Record<string, unknown> | null;
  error_message: string | null;
  created_at?: string | null;
  completed_at?: string | null;
}

export interface AIRecommendationSelection {
  index: number;
  learning_gap_index?: number | null;
  learning_gap_id?: string | null;
}

export interface ActionPlanCreate {
  recommendation_id: string;
  title: string;
  description: string;
  responsible_person: string;
  start_date: string;
  due_date: string;
}

export interface ActionPlanResponse {
  id: string;
  recommendation_id: string;
  title: string;
  description: string;
  responsible_person: string;
  start_date: string;
  due_date: string;
  status: string;
  mentor_comment: string | null;
  created_at: string;
  updated_at: string;
  version?: number;
}

export interface ActionPlanStatusUpdate {
  status: 'pending_approval' | 'approved' | 'in_progress' | 'completed' | 'overdue' | 'cancelled';
  mentor_comment?: string | null;
}

export interface ActionPlanStepCreate {
  action_plan_id: string;
  title: string;
  description: string;
  responsible_person: string;
  due_date: string;
}

export interface ActionPlanStepResponse {
  id: string;
  action_plan_id: string;
  title: string;
  description: string;
  responsible_person: string;
  due_date: string;
  status: string;
  completion_notes: string | null;
  created_at: string;
  updated_at: string;
  version?: number;
}

export interface ActionPlanStepStatusUpdate {
  status: 'in_progress' | 'completed' | 'cancelled';
  completion_notes?: string | null;
}

export interface ActionPlanStepUpdate {
  title?: string | null;
  description?: string | null;
  responsible_person?: string | null;
  due_date?: string | null;
}

export interface ActionPlanUpdate {
  title?: string | null;
  description?: string | null;
  responsible_person?: string | null;
  start_date?: string | null;
  due_date?: string | null;
}

export interface ActivityDay {
  day: string;
  visits_completed: number;
  observations_recorded: number;
  tasks_completed: number;
}

export interface ActivityReportResponse {
  start_date: string;
  end_date: string;
  days: ActivityDay[];
}

export interface AgentRunRequest {
  use_ai?: boolean;
}

export interface AssignedSchoolSummary {
  id: string;
  name: string;
  code: string;
  district?: string | null;
}

export interface Body_login_api_v1_auth_login_post {
  grant_type?: string | null;
  username: string;
  password: string;
  scope?: string;
  client_id?: string | null;
  client_secret?: string | null;
}

export interface Body_upload_evidence_api_v1_evidence__post {
  observation_id?: string | null;
  follow_up_id?: string | null;
  description?: string | null;
  file: string;
}

export interface ClassroomCreate {
  school_id: string;
  name: string;
  grade: string;
  section?: string | null;
  academic_year: string;
  capacity?: number | null;
}

export interface ClassroomResponse {
  id: string;
  school_id: string;
  name: string;
  grade: string;
  section: string | null;
  academic_year: string;
  capacity: number | null;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface ClassroomUpdate {
  name?: string | null;
  grade?: string | null;
  section?: string | null;
  academic_year?: string | null;
  capacity?: number | null;
}

export interface CoachChatRequest {
  question: string;
  observation_id?: string | null;
  context?: CoachContext | null;
}

export interface CoachChatResponse {
  question: string;
  answer: string;
  sources: CoachSource[];
  grounded: boolean;
  model?: string | null;
}

export interface CoachContext {
  subject?: string | null;
  grade?: string | null;
  topic?: string | null;
  notes?: string | null;
}

export interface CoachSource {
  document: string;
  title?: string | null;
  page: number;
  relevance?: number | null;
  excerpt?: string | null;
}

export interface CurrentUserResponse {
  id: string;
  full_name: string;
  email: string;
  role: string;
  roles: string[];
  assigned_schools: AssignedSchoolSummary[];
}

export interface EvidenceResponse {
  id: string;
  observation_id: string | null;
  follow_up_id: string | null;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  checksum_sha256: string | null;
  description: string | null;
  created_at: string;
}

export interface ExternalResult {
  success: boolean;
  detail?: string | null;
}

export interface FollowUpCreate {
  action_plan_step_id: string;
  teacher_id: string;
  description: string;
}

export interface FollowUpEvidenceSubmission {
  teacher_response: string;
}

export interface FollowUpMentorDecision {
  status: 'mentor_verified' | 'needs_revision';
  mentor_notes?: string | null;
}

export interface FollowUpResponse {
  id: string;
  action_plan_step_id: string;
  teacher_id: string;
  description: string;
  status: string;
  teacher_response: string | null;
  mentor_notes: string | null;
  responded_at: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
  version?: number;
}

export interface FollowUpStatusUpdate {
  status: 'closed';
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

export interface LearningGapCreate {
  observation_id: string;
  observation_finding_id?: string | null;
  title: string;
  description: string;
  subject: string;
  grade?: string | null;
  severity?: 'low' | 'medium' | 'high' | 'critical';
}

export interface LearningGapReportItem {
  school_id: string;
  school_name: string;
  total_learning_gaps: number;
  critical_severity?: number;
  high_severity: number;
  medium_severity: number;
  low_severity: number;
  resolved?: number;
}

export interface LearningGapResponse {
  id: string;
  observation_id: string;
  observation_finding_id: string | null;
  title: string;
  description: string;
  subject: string;
  grade: string | null;
  severity: string;
  status: string;
  created_at: string;
  updated_at: string;
  version?: number;
}

export interface LearningGapStatusUpdate {
  status: 'addressed' | 'resolved';
}

export interface LearningGapUpdate {
  observation_finding_id?: string | null;
  title?: string | null;
  description?: string | null;
  subject?: string | null;
  grade?: string | null;
  severity?: 'low' | 'medium' | 'high' | 'critical' | null;
}

export interface LogoutRequest {
  refresh_token?: string | null;
  all_devices?: boolean;
}

export interface MentorDashboardResponse {
  total_schools: number;
  total_visits: number;
  completed_visits: number;
  pending_tasks: number;
  completed_tasks: number;
  total_learning_gaps: number;
  total_action_plans: number;
  upcoming_visits?: number;
  overdue_tasks?: number;
  total_observations?: number;
  recommendations_awaiting_review?: number;
  active_action_plans?: number;
  open_follow_ups?: number;
  follow_ups_awaiting_verification?: number;
  unread_notifications?: number;
}

export interface MentorSchoolCreate {
  user_id: string;
  school_id: string;
  assigned_from?: string | null;
  assigned_until?: string | null;
  is_active?: boolean;
}

export interface MentorSchoolResponse {
  id: string;
  user_id: string;
  school_id: string;
  assigned_from: string | null;
  assigned_until: string | null;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface MentorSchoolUpdate {
  assigned_from?: string | null;
  assigned_until?: string | null;
  is_active?: boolean | null;
}

export interface MentorTaskCreate {
  school_id?: string | null;
  title: string;
  description?: string | null;
  due_at?: string | null;
  urgency?: number;
  impact?: number;
  risk?: number;
  deadline_proximity?: number;
  workload_dependency?: number;
  category?: string | null;
  estimated_minutes?: number | null;
}

export interface MentorTaskResponse {
  mentor_id?: string | null;
  id: string;
  school_id: string | null;
  title: string;
  description: string | null;
  due_at: string | null;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  priority: 'low' | 'medium' | 'high' | 'critical';
  urgency: number;
  impact: number;
  risk: number;
  deadline_proximity: number;
  workload_dependency: number;
  category?: string | null;
  estimated_minutes?: number | null;
  priority_score: number;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  version?: number;
}

export interface MentorTaskStatusUpdate {
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
}

export interface MentorTaskUpdate {
  school_id?: string | null;
  title?: string | null;
  description?: string | null;
  due_at?: string | null;
  urgency?: number | null;
  impact?: number | null;
  risk?: number | null;
  deadline_proximity?: number | null;
  workload_dependency?: number | null;
  category?: string | null;
  estimated_minutes?: number | null;
}

export interface NotificationListResponse {
  notifications: NotificationResponse[];
  total: number;
  unread_count: number;
}

export interface NotificationResponse {
  id: string;
  user_id: string;
  title: string;
  message: string;
  notification_type: string;
  reference_entity_type: string | null;
  reference_entity_id: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

export interface NotificationUnreadCountResponse {
  unread_count: number;
}

export interface ObservationCreate {
  school_visit_id: string;
  teacher_id: string;
  classroom_id: string;
  subject: string;
  topic?: string | null;
  notes?: string | null;
}

export interface ObservationFindingCreate {
  observation_id: string;
  title: string;
  description: string;
  category?: string | null;
}

export interface ObservationFindingResponse {
  id: string;
  observation_id: string;
  title: string;
  description: string;
  category: string | null;
  status: 'ai_suggested' | 'mentor_approved' | 'rejected';
  mentor_comment: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface ObservationFindingStatusUpdate {
  status: 'mentor_approved' | 'rejected';
  mentor_comment?: string | null;
}

export interface ObservationFindingUpdate {
  title?: string | null;
  description?: string | null;
  category?: string | null;
  mentor_comment?: string | null;
}

export interface ObservationResponse {
  id: string;
  school_visit_id: string;
  teacher_id: string;
  classroom_id: string;
  subject: string;
  topic: string | null;
  notes: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  version?: number;
}

export interface ObservationStatusUpdate {
  status: string;
}

export interface ObservationUpdate {
  subject?: string | null;
  topic?: string | null;
  notes?: string | null;
}

export interface ProposalDecision {
  note?: string | null;
}

export interface RecommendationCreate {
  learning_gap_id: string;
  title: string;
  description: string;
  rationale: string;
  category: string;
}

export interface RecommendationDecision {
  status: 'mentor_approved' | 'rejected';
  mentor_comment?: string | null;
}

export interface RecommendationResponse {
  id: string;
  learning_gap_id: string;
  title: string;
  description: string;
  rationale: string;
  category: string;
  status: string;
  mentor_comment: string | null;
  created_at: string;
  updated_at: string;
  version?: number;
}

export interface RecommendationUpdate {
  title?: string | null;
  description?: string | null;
  rationale?: string | null;
  category?: string | null;
}

export interface RefreshRequest {
  refresh_token: string;
}

export interface RescheduleVisitRequest {
  start: string;
  end: string;
  proposal_ref?: string | null;
}

export interface ScheduleCreate {
  school_visit_id: string;
  proposed_start_at: string;
  proposed_end_at: string;
  notes?: string | null;
}

export interface ScheduleDecision {
  status: 'accepted' | 'rejected';
}

export interface ScheduleResponse {
  id: string;
  school_visit_id: string;
  school_id: string;
  proposed_start_at: string;
  proposed_end_at: string;
  estimated_travel_minutes: number | null;
  estimated_distance_km: string | null;
  status: 'proposed' | 'accepted' | 'rejected';
  notes: string | null;
  created_at: string;
  updated_at: string;
  version?: number;
}

export interface ScheduleVisitRequest {
  school_ref: string;
  start: string;
  end: string;
  purpose: string;
  proposal_ref?: string | null;
}

export interface SchoolCreate {
  name: string;
  code: string;
  address?: string | null;
  district?: string | null;
  state?: string | null;
  block?: string | null;
  travel_minutes_from_base?: number | null;
}

export interface SchoolReportResponse {
  school_id: string;
  school_name: string;
  total_visits: number;
  completed_visits: number;
  total_observations: number;
  total_learning_gaps: number;
  open_learning_gaps?: number;
  total_action_plans: number;
  completed_action_plans: number;
  open_follow_ups?: number;
}

export interface SchoolResponse {
  id: string;
  name: string;
  code: string;
  address: string | null;
  district: string | null;
  state: string | null;
  block?: string | null;
  travel_minutes_from_base?: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface SchoolUpdate {
  name?: string | null;
  code?: string | null;
  address?: string | null;
  district?: string | null;
  state?: string | null;
  block?: string | null;
  travel_minutes_from_base?: number | null;
  is_active?: boolean | null;
}

export interface SchoolVisitCreate {
  school_id: string;
  scheduled_at: string;
  notes?: string | null;
}

export interface SchoolVisitResponse {
  mentor_id?: string | null;
  id: string;
  school_id: string;
  scheduled_at: string;
  started_at: string | null;
  completed_at: string | null;
  status: 'planned' | 'in_progress' | 'completed' | 'cancelled';
  notes: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface SchoolVisitStatusUpdate {
  status: 'planned' | 'in_progress' | 'completed' | 'cancelled';
}

export interface SchoolVisitUpdate {
  scheduled_at?: string | null;
  notes?: string | null;
}

export interface SyncBatchRequest {
  operations: SyncOperationCreate[];
}

export interface SyncBatchResponse {
  accepted: number;
  already_received: number;
  synced?: number;
  conflicts?: number;
  failed?: number;
  operations: SyncOperationResponse[];
}

export interface SyncChangeResponse {
  id: string;
  entity_type: string;
  entity_id: string;
  operation_type: 'create' | 'update' | 'delete';
  payload: Record<string, unknown>;
  version: number;
  updated_at: string;
}

export interface SyncOperationCreate {
  idempotency_key: string;
  device_id: string;
  entity_type: 'school' | 'teacher' | 'school_teacher' | 'classroom' | 'timetable' | 'school_visit' | 'observation' | 'observation_finding' | 'learning_gap' | 'recommendation' | 'action_plan' | 'action_plan_step' | 'follow_up' | 'mentor_task' | 'schedule';
  entity_id: string;
  operation_type: 'create' | 'update' | 'delete';
  payload: Record<string, unknown>;
  client_version: number;
}

export interface SyncOperationResponse {
  id: string;
  idempotency_key: string;
  device_id: string;
  entity_type: string;
  entity_id: string;
  operation_type: string;
  client_version: number;
  server_version: number | null;
  status: 'pending' | 'syncing' | 'synced' | 'conflict' | 'failed';
  error_message: string | null;
}

export interface SyncPullRequest {
  cursor_updated_at?: string | null;
  cursor_entity_type?: string | null;
  cursor_entity_id?: string | null;
  limit?: number;
}

export interface SyncPullResponse {
  changes: SyncChangeResponse[];
  next_cursor_updated_at: string | null;
  next_cursor_entity_type: string | null;
  next_cursor_entity_id: string | null;
  has_more: boolean;
}

export interface TaskDueDateRequest {
  due_at: string;
  proposal_ref?: string | null;
}

export interface TeacherCreate {
  full_name: string;
  employee_code?: string | null;
  email?: string | null;
  phone?: string | null;
}

export interface TeacherFollowUpResponse {
  teacher_response: string;
}

export interface TeacherResponse {
  id: string;
  full_name: string;
  employee_code: string | null;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface TeacherSchoolAssign {
  school_id: string;
  assigned_from?: string | null;
  assigned_until?: string | null;
}

export interface TeacherSchoolResponse {
  id: string;
  teacher_id: string;
  school_id: string;
  assigned_from: string | null;
  assigned_until: string | null;
  is_active: boolean;
}

export interface TeacherUpdate {
  full_name?: string | null;
  employee_code?: string | null;
  email?: string | null;
  phone?: string | null;
  is_active?: boolean | null;
}

export interface TimetableCreate {
  classroom_id: string;
  day_of_week: string;
  period_number: number;
  subject: string;
  start_time: string;
  end_time: string;
  teacher_id?: string | null;
}

export interface TimetableResponse {
  id: string;
  classroom_id: string;
  day_of_week: string;
  period_number: number;
  subject: string;
  start_time: string;
  end_time: string;
  teacher_id: string | null;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface TimetableUpdate {
  day_of_week?: string | null;
  period_number?: number | null;
  subject?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  teacher_id?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type?: string;
  expires_in: number;
  refresh_token?: string | null;
  refresh_expires_in?: number | null;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}

export interface WhatsAppMessageCreate {
  recipient: string;
  message_type: 'text' | 'template';
  content?: string | null;
  template_name?: string | null;
  idempotency_key: string;
}

export interface WhatsAppMessageResponse {
  id: string;
  direction: string;
  recipient: string;
  message_type: string;
  content: string | null;
  template_name: string | null;
  provider_message_id: string | null;
  idempotency_key: string;
  status: string;
  error_message: string | null;
}
