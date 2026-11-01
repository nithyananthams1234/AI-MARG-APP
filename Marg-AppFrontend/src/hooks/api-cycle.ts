/**
 * Extra hooks for the improvement-cycle screens (action plans, follow-ups,
 * tasks, schedule). Built on the same services and query keys as '@/hooks/api'.
 */
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import { qk, useGaps, useObservations, useRecommendations, useSchools, useVisits } from '@/hooks/api';
import type * as T from '@/lib/api/generated';
import { plansApi, schedulesApi, stepsApi, tasksApi, teachersApi } from '@/lib/api/services';

/** All teachers in the mentor's assigned schools. */
export const useTeachers = () => useQuery({ queryKey: ['teachers'], queryFn: teachersApi.list });

/** Daily workload summary (visits/minutes) for a local YYYY-MM-DD date. */
export const useDailyWorkload = (date: string) =>
  useQuery({ queryKey: ['schedules', 'workload', date], queryFn: () => schedulesApi.dailyWorkload(date) });

/** Steps of several plans at once (the steps endpoint requires a plan id). */
export function useStepsForPlans(planIds: string[]) {
  return useQueries({
    queries: planIds.map((id) => ({ queryKey: qk.steps(id), queryFn: () => stepsApi.list(id) })),
    // `combine` keeps the returned object stable between renders when nothing changed.
    combine: (results) => ({
      steps: results.flatMap((r) => r.data ?? []),
      isLoading: results.some((r) => r.isLoading),
      error: results.find((r) => r.error)?.error ?? null,
      refetch: () => Promise.all(results.map((r) => r.refetch())),
    }),
  });
}

export interface PlanContext {
  recommendation?: T.RecommendationResponse;
  gap?: T.LearningGapResponse;
  observation?: T.ObservationResponse;
  visit?: T.SchoolVisitResponse;
  school?: T.SchoolResponse;
}

/**
 * Resolves recommendation -> learning gap -> observation -> visit -> school
 * for any recommendation id, using the (small, mentor-scoped) list endpoints.
 */
export function useRecommendationContext() {
  const recs = useRecommendations();
  const gaps = useGaps();
  const observations = useObservations();
  const visits = useVisits();
  const schools = useSchools();

  const resolve = useMemo(() => {
    const recMap = new Map((recs.data ?? []).map((r) => [r.id, r]));
    const gapMap = new Map((gaps.data ?? []).map((g) => [g.id, g]));
    const obsMap = new Map((observations.data ?? []).map((o) => [o.id, o]));
    const visitMap = new Map((visits.data ?? []).map((v) => [v.id, v]));
    const schoolMap = new Map((schools.data ?? []).map((s) => [s.id, s]));
    return (recommendationId?: string): PlanContext => {
      const recommendation = recommendationId ? recMap.get(recommendationId) : undefined;
      const gap = recommendation ? gapMap.get(recommendation.learning_gap_id) : undefined;
      const observation = gap ? obsMap.get(gap.observation_id) : undefined;
      const visit = observation ? visitMap.get(observation.school_visit_id) : undefined;
      const school = visit ? schoolMap.get(visit.school_id) : undefined;
      return { recommendation, gap, observation, visit, school };
    };
  }, [recs.data, gaps.data, observations.data, visits.data, schools.data]);

  return { resolve, isLoading: recs.isLoading || gaps.isLoading };
}

function useInvalidate() {
  const qc = useQueryClient();
  return (...roots: string[]) => Promise.all(roots.map((r) => qc.invalidateQueries({ queryKey: [r] })));
}

export function useUpdatePlan() {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: T.ActionPlanUpdate }) => plansApi.update(id, body),
    onSettled: () => invalidate('plans'),
  });
}

export function useDeletePlan() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => plansApi.remove(id), onSettled: () => invalidate('plans', 'reports') });
}

export function useDeleteTask() {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: (id: string) => tasksApi.remove(id), onSettled: () => invalidate('tasks', 'reports') });
}
