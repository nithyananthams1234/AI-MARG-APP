/**
 * Page chrome shared by the Reports, Notifications, Profile, Mentor AI and
 * Classroom Coach screens: back-button header, section titles and a simple
 * horizontal bar built from Views (no chart library).
 */
import { useRouter } from 'expo-router';
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { MargColors as C } from '@/constants/theme';

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: ReactNode }) {
  const router = useRouter();
  return (
    <View style={styles.header}>
      <Pressable
        style={styles.backButton}
        onPress={() => (router.canGoBack() ? router.back() : router.replace('/dashboard'))}
        accessibilityRole="button"
        accessibilityLabel="Go back"
        hitSlop={6}
      >
        <Text style={styles.backText}>‹</Text>
      </Pressable>
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

export function SectionTitle({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle} accessibilityRole="header">
        {title}
      </Text>
      {right}
    </View>
  );
}

/** Horizontal bar: value relative to max. */
export function Bar({ value, max, color = C.teal, label }: { value: number; max: number; color?: string; label?: string }) {
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  return (
    <View style={styles.barTrack} accessibilityLabel={label} accessible={!!label}>
      <View style={[styles.barFill, { width: `${pct * 100}%`, backgroundColor: color }]} />
    </View>
  );
}

export const pageStyles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: C.background },
  content: { padding: 20, paddingBottom: 48, maxWidth: 900, width: '100%', alignSelf: 'center' },
  muted: { color: C.secondaryText, fontSize: 13, lineHeight: 18 },
  body: { color: C.text, fontSize: 14, lineHeight: 21 },
  itemTitle: { color: C.navy, fontSize: 15, fontWeight: '700' },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
  input: {
    backgroundColor: C.inputBackground,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: C.text,
    fontSize: 15,
  },
  label: { color: C.navy, fontSize: 13, fontWeight: '700', marginBottom: 6, marginTop: 10 },
  chip: { borderWidth: 1, borderColor: C.border, backgroundColor: C.surface, borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7 },
  chipActive: { backgroundColor: '#E8F7F5', borderColor: C.teal },
  chipText: { color: C.navy, fontSize: 13, fontWeight: '600' },
  chipTextActive: { color: C.tealDark },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  error: { color: C.danger, fontSize: 13, fontWeight: '600', marginTop: 6 },
});

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 16 },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backText: { color: C.navy, fontSize: 26, lineHeight: 28, fontWeight: '600' },
  title: { color: C.navy, fontSize: 22, fontWeight: '800' },
  subtitle: { color: C.secondaryText, fontSize: 13, marginTop: 2 },
  section: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 18, marginBottom: 10, gap: 8 },
  sectionTitle: { color: C.navy, fontSize: 17, fontWeight: '800', flex: 1 },
  barTrack: { height: 10, borderRadius: 5, backgroundColor: '#EEF1F5', overflow: 'hidden', flex: 1 },
  barFill: { height: 10, borderRadius: 5 },
});
