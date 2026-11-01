/**
 * Extra data hooks used by the field screens (schools, visits, observations).
 * Built on the shared services and query keys in '@/hooks/api'.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { aiJobsApi, observationsApi, teachersApi } from '@/lib/api/services';

/** All teachers visible to the mentor (used to resolve teacher names in lists). */
export const useAllTeachers = () => useQuery({ queryKey: ['teachers', 'all'], queryFn: teachersApi.list, staleTime: 5 * 60_000 });

/** AI jobs that analysed the given observation, newest first. */
export function useObservationAiJobs(observationId?: string) {
  return useQuery({
    queryKey: ['ai-jobs', 'observation', observationId ?? ''],
    queryFn: async () => {
      const jobs = await aiJobsApi.list();
      return jobs
        .filter((j) => j.entity_type === 'observation' && j.entity_id === observationId && j.job_type === 'observation_analysis')
        .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''));
    },
    enabled: !!observationId,
  });
}

/** Delete a draft observation (online only; the backend rejects non-drafts). */
export function useDeleteObservation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => observationsApi.remove(id),
    onSettled: () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: ['observations'] }),
        qc.invalidateQueries({ queryKey: ['observation'] }),
        qc.invalidateQueries({ queryKey: ['reports'] }),
      ]),
  });
}
