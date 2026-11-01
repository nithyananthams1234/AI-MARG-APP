import { useColorScheme as useRNColorScheme } from 'react-native';

/**
 * Returns the current system color scheme on web.
 */
export function useColorScheme() {
  return useRNColorScheme() ?? 'light';
}