import '@/global.css';

import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#172B4D',
    background: '#F5F7FB',
    backgroundElement: '#FFFFFF',
    backgroundSelected: '#E8F3F5',
    textSecondary: '#718096',
  },
  dark: {
    text: '#F4F7FC',
    background: '#101827',
    backgroundElement: '#1C293B',
    backgroundSelected: '#263B50',
    textSecondary: '#A5B4C7',
  },
} as const;

export const MargColors = {
  navy: '#142B4A',
  navyLight: '#203F65',
  teal: '#13A89E',
  tealDark: '#0D8982',
  background: '#F5F7FB',
  surface: '#FFFFFF',
  text: '#172B4D',
  secondaryText: '#718096',
  muted: '#A0AEC0',
  border: '#E5EAF1',
  inputBackground: '#F8FAFC',
  success: '#16A477',
  danger: '#DC5555',
} as const;

export type ThemeColor = keyof typeof Colors.light &
  keyof typeof Colors.dark;

export const Fonts = Platform.select({
  ios: {
    sans: 'system-ui',
    serif: 'ui-serif',
    rounded: 'ui-rounded',
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: 'var(--font-display)',
    serif: 'var(--font-serif)',
    rounded: 'var(--font-rounded)',
    mono: 'var(--font-mono)',
  },
});

export const Spacing = {
  half: 2,
  one: 4,
  two: 8,
  three: 16,
  four: 24,
  five: 32,
  six: 64,
} as const;

export const BottomTabInset = Platform.select({
  ios: 50,
  android: 80,
}) ?? 0;

export const MaxContentWidth = 800;