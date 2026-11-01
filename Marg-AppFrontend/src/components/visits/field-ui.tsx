/**
 * Small layout and form primitives shared by the Schools, Visits and
 * Observations screens (same visual language: navy titles, white rounded
 * cards, teal primary).
 */
import type { ReactNode } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View, type KeyboardTypeOptions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { notify } from '@/lib/dialogs';
import { isQueued } from '@/lib/query';

export function ScreenShell({
  title,
  subtitle,
  icon,
  onBack,
  refreshing,
  onRefresh,
  children,
}: {
  title: string;
  subtitle?: string;
  icon?: string;
  onBack?: () => void;
  refreshing?: boolean;
  onRefresh?: () => void;
  children: ReactNode;
}) {
  return (
    <SafeAreaView style={styles.safeArea} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={C.teal} /> : undefined}
      >
        <View style={styles.header}>
          {onBack ? (
            <Pressable onPress={onBack} style={styles.iconButton} accessibilityRole="button" accessibilityLabel="Go back" hitSlop={6}>
              <Text style={styles.backText}>‹</Text>
            </Pressable>
          ) : null}
          <View style={styles.headerText}>
            <Text style={styles.headerTitle} accessibilityRole="header" numberOfLines={2}>
              {title}
            </Text>
            {subtitle ? <Text style={styles.headerSubtitle}>{subtitle}</Text> : null}
          </View>
          {icon ? (
            <View style={styles.headerIcon} importantForAccessibility="no-hide-descendants">
              <Text style={styles.headerIconText}>{icon}</Text>
            </View>
          ) : null}
        </View>
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}

export function SectionTitle({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <View style={styles.sectionHeading}>
      <Text style={styles.sectionTitle} accessibilityRole="header">
        {title}
      </Text>
      {right}
    </View>
  );
}

export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  multiline,
  keyboardType,
  maxLength,
  hint,
  editable = true,
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  placeholder?: string;
  multiline?: boolean;
  keyboardType?: KeyboardTypeOptions;
  maxLength?: number;
  hint?: string;
  editable?: boolean;
}) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={[styles.input, multiline && styles.textArea, !editable && styles.inputDisabled]}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={C.muted}
        multiline={multiline}
        textAlignVertical={multiline ? 'top' : 'center'}
        keyboardType={keyboardType}
        maxLength={maxLength}
        editable={editable}
        accessibilityLabel={label}
        accessibilityHint={hint}
      />
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
}

export interface ChipOption<V extends string> {
  value: V;
  label: string;
  detail?: string;
}

/** Single-choice selector rendered as wrapping chips. */
export function ChipSelect<V extends string>({
  label,
  options,
  value,
  onChange,
  emptyText,
  disabled,
}: {
  label?: string;
  options: ChipOption<V>[];
  value: V | null | undefined;
  onChange: (v: V) => void;
  emptyText?: string;
  disabled?: boolean;
}) {
  return (
    <View style={styles.field}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      {options.length === 0 ? (
        <Text style={styles.hint}>{emptyText ?? 'No options available.'}</Text>
      ) : (
        <View style={styles.chips} accessibilityRole="radiogroup" accessibilityLabel={label}>
          {options.map((o) => {
            const selected = o.value === value;
            return (
              <Pressable
                key={o.value}
                onPress={() => onChange(o.value)}
                disabled={disabled}
                accessibilityRole="radio"
                accessibilityState={{ selected, disabled: !!disabled }}
                accessibilityLabel={o.detail ? `${o.label}, ${o.detail}` : o.label}
                style={[styles.chip, selected && styles.chipSelected, disabled && { opacity: 0.6 }]}
              >
                <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{o.label}</Text>
                {o.detail ? <Text style={[styles.chipDetail, selected && styles.chipTextSelected]}>{o.detail}</Text> : null}
              </Pressable>
            );
          })}
        </View>
      )}
    </View>
  );
}

/** Horizontal filter tabs with counts. */
export function FilterTabs<V extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: V; label: string; count?: number }[];
  value: V;
  onChange: (v: V) => void;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filters}>
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <Pressable
            key={o.value}
            onPress={() => onChange(o.value)}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            style={[styles.filterButton, selected && styles.filterButtonSelected]}
          >
            <Text style={[styles.filterText, selected && styles.filterTextSelected]}>
              {o.label}
              {o.count !== undefined ? ` (${o.count})` : ''}
            </Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

export function InfoRow({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value === undefined || value === null || value === '' ? '—' : String(value)}</Text>
    </View>
  );
}

export function MutationError({ error }: { error: unknown }) {
  if (!error) return null;
  return <InlineNotice tone="danger" text={error instanceof Error ? error.message : 'The action could not be completed.'} />;
}

/** After an offline-capable write: tell the user if it was queued. Returns true if queued. */
export function reportQueued(result: unknown): boolean {
  if (isQueued(result)) {
    notify('Saved offline, will sync', 'You appear to be offline. The change is queued and will be sent when you are back online.');
    return true;
  }
  return false;
}

export const fieldStyles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 4 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 4 },
  itemTitle: { color: C.navy, fontSize: 15, fontWeight: '700', flex: 1 },
  itemText: { color: C.text, fontSize: 14, marginTop: 4, lineHeight: 20 },
  muted: { color: C.secondaryText, fontSize: 13, marginTop: 2 },
  formTitle: { color: C.navy, fontSize: 18, fontWeight: '800', marginBottom: 12 },
  label: { color: C.navy, fontSize: 13, fontWeight: '700', marginBottom: 6 },
  chevron: { color: C.muted, fontSize: 26, marginLeft: 8 },
  grow: { flexGrow: 1 },
});

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: C.background },
  content: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 40, maxWidth: 900, width: '100%', alignSelf: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', marginBottom: 18, gap: 12 },
  iconButton: {
    width: 42,
    height: 42,
    borderRadius: 13,
    backgroundColor: C.surface,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: C.border,
  },
  backText: { color: C.navy, fontSize: 32, lineHeight: 36, marginTop: -3 },
  headerText: { flex: 1 },
  headerTitle: { color: C.navy, fontSize: 23, fontWeight: '800' },
  headerSubtitle: { color: C.secondaryText, fontSize: 13, marginTop: 3 },
  headerIcon: { width: 42, height: 42, borderRadius: 13, backgroundColor: '#E7F5F3', alignItems: 'center', justifyContent: 'center' },
  headerIconText: { color: C.tealDark, fontSize: 22 },
  sectionHeading: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 14, marginBottom: 10, gap: 8 },
  sectionTitle: { color: C.navy, fontSize: 18, fontWeight: '800', flex: 1 },
  field: { marginBottom: 14 },
  label: { color: C.navy, fontSize: 13, fontWeight: '700', marginBottom: 6 },
  input: {
    minHeight: 46,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.inputBackground,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: C.text,
    fontSize: 15,
  },
  inputDisabled: { opacity: 0.6 },
  textArea: { minHeight: 110 },
  hint: { color: C.secondaryText, fontSize: 12, marginTop: 4 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { borderWidth: 1, borderColor: C.border, backgroundColor: C.surface, borderRadius: 12, paddingVertical: 8, paddingHorizontal: 12, maxWidth: '100%' },
  chipSelected: { backgroundColor: C.teal, borderColor: C.teal },
  chipText: { color: C.navy, fontSize: 14, fontWeight: '700' },
  chipDetail: { color: C.secondaryText, fontSize: 12, marginTop: 2 },
  chipTextSelected: { color: '#FFFFFF' },
  filters: { gap: 8, paddingBottom: 12 },
  filterButton: { paddingHorizontal: 14, paddingVertical: 9, borderRadius: 999, backgroundColor: C.surface, borderWidth: 1, borderColor: C.border },
  filterButtonSelected: { backgroundColor: C.navy, borderColor: C.navy },
  filterText: { color: C.secondaryText, fontSize: 13, fontWeight: '700' },
  filterTextSelected: { color: '#FFFFFF' },
  infoRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, gap: 12, borderBottomWidth: 1, borderBottomColor: C.border },
  infoLabel: { color: C.secondaryText, fontSize: 13 },
  infoValue: { color: C.navy, fontSize: 14, fontWeight: '700', flexShrink: 1, textAlign: 'right' },
});
