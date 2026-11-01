/**
 * Extra read hooks used by the AI assistant, coach and report screens.
 * Thin wrappers over '@/lib/api/services' (no URLs here).
 */
import { useQuery } from '@tanstack/react-query';

import { teachersApi } from '@/lib/api/services';

export const useTeachers = () => useQuery({ queryKey: ['teachers'], queryFn: teachersApi.list, staleTime: 5 * 60_000 });
