/**
 * Optional context for a Coach question: one of the mentor's observations
 * (the backend adds its subject / grade / topic / notes) or manual fields.
 */
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { pageStyles } from '@/components/reports/page-chrome';
import { Button, EmptyState, ErrorState, LoadingState } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useObservations } from '@/hooks/api';
import { useTeachers } from '@/hooks/api-ai';
import type { ObservationResponse } from '@/lib/api/generated';
import { formatDate } from '@/lib/format';

export type ContextMode = 'none' | 'observation' | 'manual';
export interface ManualContext {
  subject: string;
  grade: string;
  topic: string;
}

const MODES: { key: ContextMode; label: string }[] = [
  { key: 'none', label: 'No context' },
  { key: 'observation', label: 'From an observation' },
  { key: 'manual', label: 'Subject / grade / topic' },
];

export function observationLabel(o: ObservationResponse, teacherName?: string) {
  return [o.subject, o.topic, teacherName, formatDate(o.created_at)].filter(Boolean).join(' · ');
}

export function ContextPicker({
  mode,
  onModeChange,
  observationId,
  onObservationChange,
  manual,
  onManualChange,
  visitId,
  disabled,
}: {
  mode: ContextMode;
  onModeChange: (m: ContextMode) => void;
  observationId?: string;
  onObservationChange: (o: ObservationResponse | undefined) => void;
  manual: ManualContext;
  onManualChange: (m: ManualContext) => void;
  visitId?: string;
  disabled?: boolean;
}) {
  const [onlyVisit, setOnlyVisit] = useState(!!visitId);
  const observations = useObservations(onlyVisit && visitId ? { school_visit_id: visitId } : undefined);
  const teachers = useTeachers();
  const teacherName = (id: string) => teachers.data?.find((t) => t.id === id)?.full_name;
  const sorted = useMemo(
    () => [...(observations.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 20),
    [observations.data],
  );

  return (
    <View>
      <Text style={pageStyles.label}>Context (optional)</Text>
      <View style={pageStyles.chipRow} accessibilityRole="radiogroup">
        {MODES.map((m) => (
          <Pressable
            key={m.key}
            onPress={() => onModeChange(m.key)}
            disabled={disabled}
            accessibilityRole="radio"
            accessibilityState={{ checked: mode === m.key, disabled }}
            style={[pageStyles.chip, mode === m.key && pageStyles.chipActive]}
          >
            <Text style={[pageStyles.chipText, mode === m.key && pageStyles.chipTextActive]}>{m.label}</Text>
          </Pressable>
        ))}
      </View>

      {mode === 'observation' ? (
        <View style={{ marginTop: 10 }}>
          {visitId ? (
            <Pressable
              onPress={() => setOnlyVisit((v) => !v)}
              accessibilityRole="switch"
              accessibilityState={{ checked: onlyVisit }}
              style={styles.toggle}
            >
              <Text style={styles.toggleText}>{onlyVisit ? '☑' : '☐'} Only observations from this visit</Text>
            </Pressable>
          ) : null}
          {observations.isLoading && !observations.data ? (
            <LoadingState label="Loading your observations…" />
          ) : !observations.data ? (
            <ErrorState error={observations.error} onRetry={() => void observations.refetch()} />
          ) : sorted.length === 0 ? (
            <EmptyState title="No observations" message="Record an observation first, or set the subject and topic manually." />
          ) : (
            <View style={{ gap: 6 }}>
              {sorted.map((o) => {
                const selected = o.id === observationId;
                return (
                  <Pressable
                    key={o.id}
                    onPress={() => onObservationChange(selected ? undefined : o)}
                    disabled={disabled}
                    accessibilityRole="radio"
                    accessibilityState={{ checked: selected, disabled }}
                    style={[styles.obs, selected && styles.obsSelected]}
                  >
                    <Text style={[styles.obsText, selected && { color: C.tealDark }]} numberOfLines={2}>
                      {selected ? '● ' : '○ '}
                      {observationLabel(o, teacherName(o.teacher_id))}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          )}
        </View>
      ) : null}

      {mode === 'manual' ? (
        <View style={styles.manualRow}>
          {(
            [
              ['subject', 'Subject', 'e.g. Mathematics'],
              ['grade', 'Grade', 'e.g. 4'],
              ['topic', 'Topic', 'e.g. Fractions'],
            ] as const
          ).map(([key, label, placeholder]) => (
            <View key={key} style={styles.manualField}>
              <Text style={pageStyles.label}>{label}</Text>
              <TextInput
                value={manual[key]}
                onChangeText={(v) => onManualChange({ ...manual, [key]: v })}
                placeholder={placeholder}
                placeholderTextColor={C.muted}
                editable={!disabled}
                maxLength={key === 'grade' ? 20 : 120}
                style={pageStyles.input}
                accessibilityLabel={label}
              />
            </View>
          ))}
          {manual.subject || manual.grade || manual.topic ? (
            <Button label="Clear" variant="ghost" onPress={() => onManualChange({ subject: '', grade: '', topic: '' })} />
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  toggle: { paddingVertical: 6, marginBottom: 4 },
  toggleText: { color: C.navy, fontSize: 13, fontWeight: '600' },
  obs: { borderWidth: 1, borderColor: C.border, borderRadius: 10, padding: 10, backgroundColor: C.surface },
  obsSelected: { borderColor: C.teal, backgroundColor: '#F2FBFA' },
  obsText: { color: C.text, fontSize: 13 },
  manualRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, alignItems: 'flex-end' },
  manualField: { flexGrow: 1, flexBasis: 160 },
});
