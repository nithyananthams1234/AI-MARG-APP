/**
 * Shared loading / error / empty states and small UI primitives used by all
 * data-driven screens, so every screen handles these states consistently.
 */
import type { ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type ViewStyle } from 'react-native';

import { MargColors as C } from '@/constants/theme';
import { humanize } from '@/lib/format';

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <View style={styles.center} accessibilityRole="progressbar" accessibilityLabel={label}>
      <ActivityIndicator color={C.teal} />
      <Text style={styles.muted}>{label}</Text>
    </View>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : 'Something went wrong.';
  return (
    <View style={styles.card} accessibilityRole="alert">
      <Text style={styles.errorTitle}>Could not load data</Text>
      <Text style={styles.muted}>{message}</Text>
      {onRetry ? <Button label="Try again" variant="secondary" onPress={onRetry} style={{ marginTop: 12 }} /> : null}
    </View>
  );
}

export function EmptyState({ title, message, action }: { title: string; message?: string; action?: ReactNode }) {
  return (
    <View style={[styles.card, styles.centerText]}>
      <Text style={styles.emptyTitle}>{title}</Text>
      {message ? <Text style={[styles.muted, styles.centerText]}>{message}</Text> : null}
      {action}
    </View>
  );
}

/** Renders the right state for a React Query result, or the children when data is ready. */
export function QueryView<D>({
  query,
  children,
  loadingLabel,
}: {
  query: { data: D | undefined; isLoading: boolean; error: unknown; refetch: () => unknown };
  children: (data: D) => ReactNode;
  loadingLabel?: string;
}) {
  const { data, isLoading, error, refetch } = query;
  if (isLoading && data === undefined) return <LoadingState label={loadingLabel} />;
  if (data === undefined) return <ErrorState error={error} onRetry={() => void refetch()} />;
  return (
    <>
      {error ? <InlineNotice tone="warning" text="Showing saved data — could not refresh from the server." /> : null}
      {children(data)}
    </>
  );
}

export function InlineNotice({ text, tone = 'info' }: { text: string; tone?: 'info' | 'warning' | 'success' | 'danger' }) {
  const palette = {
    info: { bg: '#EAF3FC', fg: '#2462A8' },
    warning: { bg: '#FFF4E7', fg: '#9A5B12' },
    success: { bg: '#E7F7F0', fg: '#0F7A57' },
    danger: { bg: '#FDECEC', fg: '#B23B3B' },
  }[tone];
  return (
    <View style={[styles.notice, { backgroundColor: palette.bg }]}>
      <Text style={[styles.noticeText, { color: palette.fg }]}>{text}</Text>
    </View>
  );
}

const STATUS_COLORS: Record<string, { bg: string; fg: string }> = {
  planned: { bg: '#EAF3FC', fg: '#2462A8' },
  pending: { bg: '#FFF4E7', fg: '#9A5B12' },
  proposed: { bg: '#FFF4E7', fg: '#9A5B12' },
  draft: { bg: '#EEF1F5', fg: '#4A5568' },
  in_progress: { bg: '#E8F7F5', fg: '#0D8982' },
  submitted: { bg: '#E8F7F5', fg: '#0D8982' },
  teacher_responded: { bg: '#E8F7F5', fg: '#0D8982' },
  evidence_submitted: { bg: '#F3EDFA', fg: '#6B3FA0' },
  pending_approval: { bg: '#F3EDFA', fg: '#6B3FA0' },
  ai_suggested: { bg: '#F3EDFA', fg: '#6B3FA0' },
  identified: { bg: '#FFF4E7', fg: '#9A5B12' },
  addressed: { bg: '#E8F7F5', fg: '#0D8982' },
  approved: { bg: '#E7F7F0', fg: '#0F7A57' },
  mentor_approved: { bg: '#E7F7F0', fg: '#0F7A57' },
  accepted: { bg: '#E7F7F0', fg: '#0F7A57' },
  completed: { bg: '#E7F7F0', fg: '#0F7A57' },
  processed: { bg: '#E7F7F0', fg: '#0F7A57' },
  reviewed: { bg: '#E7F7F0', fg: '#0F7A57' },
  resolved: { bg: '#E7F7F0', fg: '#0F7A57' },
  mentor_verified: { bg: '#E7F7F0', fg: '#0F7A57' },
  closed: { bg: '#EEF1F5', fg: '#4A5568' },
  executed: { bg: '#E7F7F0', fg: '#0F7A57' },
  needs_revision: { bg: '#FDECEC', fg: '#B23B3B' },
  overdue: { bg: '#FDECEC', fg: '#B23B3B' },
  rejected: { bg: '#FDECEC', fg: '#B23B3B' },
  cancelled: { bg: '#EEF1F5', fg: '#718096' },
  critical: { bg: '#FDECEC', fg: '#B23B3B' },
  high: { bg: '#FFF4E7', fg: '#9A5B12' },
  medium: { bg: '#EAF3FC', fg: '#2462A8' },
  low: { bg: '#EEF1F5', fg: '#4A5568' },
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const c = STATUS_COLORS[status] ?? { bg: '#EEF1F5', fg: '#4A5568' };
  return (
    <View style={[styles.badge, { backgroundColor: c.bg }]}>
      <Text style={[styles.badgeText, { color: c.fg }]}>{label ?? humanize(status)}</Text>
    </View>
  );
}

export function Button({
  label,
  onPress,
  variant = 'primary',
  disabled,
  loading,
  style,
  accessibilityLabel,
}: {
  label: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  disabled?: boolean;
  loading?: boolean;
  style?: ViewStyle;
  accessibilityLabel?: string;
}) {
  const v = {
    primary: { bg: C.teal, fg: '#FFFFFF', border: C.teal },
    secondary: { bg: C.surface, fg: C.navy, border: C.border },
    danger: { bg: C.surface, fg: C.danger, border: '#F3C4C4' },
    ghost: { bg: 'transparent', fg: C.tealDark, border: 'transparent' },
  }[variant];
  const inactive = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ disabled: !!inactive, busy: !!loading }}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: v.bg, borderColor: v.border, opacity: inactive ? 0.55 : pressed ? 0.85 : 1 },
        style,
      ]}
    >
      {loading ? <ActivityIndicator color={v.fg} size="small" /> : <Text style={[styles.buttonText, { color: v.fg }]}>{label}</Text>}
    </Pressable>
  );
}

export function ScreenHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  return (
    <View style={styles.header}>
      <View style={{ flex: 1 }}>
        <Text style={styles.title} accessibilityRole="header">
          {title}
        </Text>
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
      </View>
      {right}
    </View>
  );
}

export function Card({ children, style, onPress }: { children: ReactNode; style?: ViewStyle; onPress?: () => void }) {
  if (onPress) {
    return (
      <Pressable onPress={onPress} accessibilityRole="button" style={({ pressed }) => [styles.card, style, pressed && { opacity: 0.9 }]}>
        {children}
      </Pressable>
    );
  }
  return <View style={[styles.card, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  center: { padding: 32, alignItems: 'center', gap: 10 },
  centerText: { alignItems: 'center', textAlign: 'center' },
  card: {
    backgroundColor: C.surface,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: C.border,
    padding: 16,
    marginBottom: 12,
  },
  muted: { color: C.secondaryText, fontSize: 14, lineHeight: 20 },
  errorTitle: { color: C.danger, fontSize: 16, fontWeight: '700', marginBottom: 4 },
  emptyTitle: { color: C.navy, fontSize: 16, fontWeight: '700', marginBottom: 4 },
  notice: { borderRadius: 12, paddingVertical: 10, paddingHorizontal: 12, marginBottom: 12 },
  noticeText: { fontSize: 13, fontWeight: '600', lineHeight: 18 },
  badge: { alignSelf: 'flex-start', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4 },
  badgeText: { fontSize: 12, fontWeight: '700' },
  button: { minHeight: 44, borderRadius: 12, borderWidth: 1, paddingHorizontal: 16, alignItems: 'center', justifyContent: 'center' },
  buttonText: { fontSize: 15, fontWeight: '700' },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 16, gap: 12 },
  title: { color: C.navy, fontSize: 24, fontWeight: '800' },
  subtitle: { color: C.secondaryText, fontSize: 14, marginTop: 4 },
});
