import type { MentorTaskResponse } from '@/lib/api/generated';

export type Level = 'low' | 'medium' | 'high';
export const LEVELS: Level[] = ['low', 'medium', 'high'];

/** Simple Low/Medium/High pickers mapped onto the backend's 0-100 scoring factors. */
export const LEVEL_VALUE: Record<Level, number> = { low: 20, medium: 50, high: 85 };

export function valueToLevel(value: number | null | undefined): Level {
  const v = value ?? 50;
  if (v < 35) return 'low';
  if (v < 70) return 'medium';
  return 'high';
}

export const FACTORS = [
  { key: 'urgency', label: 'Urgency' },
  { key: 'impact', label: 'Impact' },
  { key: 'risk', label: 'Risk if delayed' },
  { key: 'deadline_proximity', label: 'Deadline pressure' },
  { key: 'workload_dependency', label: 'Others depend on it' },
] as const;
export type FactorKey = (typeof FACTORS)[number]['key'];

export const CATEGORIES = ['visit', 'reporting', 'follow_up', 'training', 'administration', 'other'];

export const PRIORITY_COLORS: Record<MentorTaskResponse['priority'], string> = {
  low: '#718096',
  medium: '#D69E2E',
  high: '#DD7A35',
  critical: '#D64545',
};

export const isOpen = (t: MentorTaskResponse) => t.status === 'pending' || t.status === 'in_progress';

export function isTaskOverdue(t: MentorTaskResponse): boolean {
  return isOpen(t) && !!t.due_at && new Date(t.due_at).getTime() < Date.now();
}

/** Split an ISO datetime into local YYYY-MM-DD and HH:MM for form fields. */
export function isoToLocalParts(iso: string | null): { date: string; time: string } {
  if (!iso) return { date: '', time: '' };
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return { date: '', time: '' };
  const p = (n: number) => `${n}`.padStart(2, '0');
  return { date: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`, time: `${p(d.getHours())}:${p(d.getMinutes())}` };
}
