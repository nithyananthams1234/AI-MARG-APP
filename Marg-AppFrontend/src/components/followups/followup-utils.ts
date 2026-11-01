import type { ActionPlanResponse, ActionPlanStepResponse, TeacherResponse } from '@/lib/api/generated';

export const FU_STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  teacher_responded: 'Teacher responded',
  evidence_submitted: 'Evidence submitted',
  mentor_verified: 'Mentor verified',
  needs_revision: 'Needs revision',
  closed: 'Closed',
};

export const FU_STATUS_COLORS: Record<string, { background: string; text: string }> = {
  pending: { background: '#FFF4E7', text: '#B87520' },
  teacher_responded: { background: '#EAF3FC', text: '#2878C8' },
  evidence_submitted: { background: '#F3EDFA', text: '#9465C5' },
  mentor_verified: { background: '#E8F7F1', text: '#16845F' },
  needs_revision: { background: '#FDECEC', text: '#C34C4C' },
  closed: { background: '#EEF1F5', text: '#64748B' },
};

export const FU_FILTERS = [
  { label: 'All', value: 'all' },
  { label: 'Pending', value: 'pending' },
  { label: 'Responded', value: 'teacher_responded' },
  { label: 'Evidence', value: 'evidence_submitted' },
  { label: 'Verified', value: 'mentor_verified' },
  { label: 'Revision', value: 'needs_revision' },
  { label: 'Closed', value: 'closed' },
];

/** Lookup data needed to describe a follow-up (step, plan, teacher). */
export interface FollowUpLookups {
  step: (id: string) => ActionPlanStepResponse | undefined;
  plan: (id: string) => ActionPlanResponse | undefined;
  teacher: (id: string) => TeacherResponse | undefined;
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
