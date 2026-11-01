import type { ActionPlanResponse, ActionPlanStatusUpdate } from '@/lib/api/generated';
import { toDateInput } from '@/lib/format';

export type PlanStatus = 'draft' | ActionPlanStatusUpdate['status'];
export type PlanTarget = ActionPlanStatusUpdate['status'];

export const PLAN_STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  pending_approval: 'Pending approval',
  approved: 'Approved',
  in_progress: 'In progress',
  completed: 'Completed',
  overdue: 'Overdue',
  cancelled: 'Cancelled',
};

export const PLAN_STATUS_COLORS: Record<string, string> = {
  draft: '#718096',
  pending_approval: '#D18A24',
  approved: '#2878C8',
  in_progress: '#0D9488',
  completed: '#16A477',
  overdue: '#DC5555',
  cancelled: '#8B929D',
};

/** Allowed plan status transitions (enforced by the backend). */
export const PLAN_TRANSITIONS: Record<string, PlanTarget[]> = {
  draft: ['pending_approval', 'cancelled'],
  pending_approval: ['approved', 'cancelled'],
  approved: ['in_progress', 'cancelled'],
  in_progress: ['completed', 'overdue', 'cancelled'],
  overdue: ['in_progress', 'completed', 'cancelled'],
  completed: [],
  cancelled: [],
};

export const TRANSITION_LABELS: Record<PlanTarget, string> = {
  pending_approval: 'Submit for approval',
  approved: 'Approve',
  in_progress: 'Start',
  completed: 'Mark completed',
  overdue: 'Mark overdue',
  cancelled: 'Cancel plan',
};

/** Statuses in which steps may be added. */
export const STEP_EDITABLE_PLAN_STATUSES = ['approved', 'in_progress', 'overdue'];

export const isPlanEditable = (p: ActionPlanResponse) => p.status === 'draft';
export const isPlanDeletable = (p: ActionPlanResponse) => p.status === 'draft' || p.status === 'cancelled';

/** Today's local date as YYYY-MM-DD (never hardcoded). */
export const todayLocal = (): string => toDateInput(new Date());

export function isPlanPastDue(p: ActionPlanResponse): boolean {
  return !['completed', 'cancelled'].includes(p.status) && p.due_date < todayLocal();
}

export function isValidDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [y, m, d] = value.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d;
}
