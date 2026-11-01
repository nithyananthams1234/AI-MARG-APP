/** Resolve backend refs (ids) in Mentor AI results to readable names. */
import { useFollowUps, useSchools, useTasks, useVisits } from '@/hooks/api';
import { useTeachers } from '@/hooks/api-ai';
import { formatDateTime } from '@/lib/format';

export function useLookups() {
  const schools = useSchools();
  const visits = useVisits();
  const tasks = useTasks();
  const teachers = useTeachers();
  const followUps = useFollowUps();

  const schoolName = (ref?: string) => (ref ? schools.data?.find((s) => s.id === ref)?.name : undefined);
  const visit = (ref?: string) => (ref ? visits.data?.find((v) => v.id === ref) : undefined);
  const visitLabel = (ref?: string) => {
    const v = visit(ref);
    if (!v) return undefined;
    return `${schoolName(v.school_id) ?? 'School visit'} · ${formatDateTime(v.scheduled_at)}`;
  };
  const taskTitle = (ref?: string) => (ref ? tasks.data?.find((t) => t.id === ref)?.title : undefined);
  const teacher = (ref?: string) => (ref ? teachers.data?.find((t) => t.id === ref) : undefined);
  const followUp = (ref?: string) => (ref ? followUps.data?.find((f) => f.id === ref) : undefined);

  return { schoolName, visit, visitLabel, taskTitle, teacher, followUp, followUps };
}

export type Lookups = ReturnType<typeof useLookups>;
