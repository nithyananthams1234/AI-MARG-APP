import { useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { InlineNotice } from '@/components/ui/states';
import { MargColors } from '@/constants/theme';
import { useSchools } from '@/hooks/api';
import type { MentorTaskCreate, MentorTaskResponse } from '@/lib/api/generated';
import { humanize, localDateTimeToIso } from '@/lib/format';

import { CATEGORIES, FACTORS, LEVEL_VALUE, LEVELS, isoToLocalParts, valueToLevel, type FactorKey, type Level } from './task-utils';

type Props = {
  visible: boolean;
  task: MentorTaskResponse | null;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (body: MentorTaskCreate) => void;
};

const defaultLevels = (): Record<FactorKey, Level> => ({
  urgency: 'medium', impact: 'medium', risk: 'medium', deadline_proximity: 'medium', workload_dependency: 'low',
});

/** Mounted only while open, so every opening starts from fresh initial state. */
export function TaskFormModal(props: Props) {
  return props.visible ? <TaskForm key={props.task?.id ?? 'new'} {...props} /> : null;
}

function TaskForm({ task, saving, error, onClose, onSubmit }: Props) {
  const schools = useSchools();
  const parts = isoToLocalParts(task?.due_at ?? null);
  const [title, setTitle] = useState(task?.title ?? '');
  const [description, setDescription] = useState(task?.description ?? '');
  const [schoolId, setSchoolId] = useState<string | null>(task?.school_id ?? null);
  const [dueDate, setDueDate] = useState(parts.date);
  const [dueTime, setDueTime] = useState(parts.time || '17:00');
  const [category, setCategory] = useState<string | null>(task?.category ?? null);
  const [minutes, setMinutes] = useState(task?.estimated_minutes ? `${task.estimated_minutes}` : '');
  const [levels, setLevels] = useState<Record<FactorKey, Level>>(() =>
    task
      ? {
          urgency: valueToLevel(task.urgency),
          impact: valueToLevel(task.impact),
          risk: valueToLevel(task.risk),
          deadline_proximity: valueToLevel(task.deadline_proximity),
          workload_dependency: valueToLevel(task.workload_dependency),
        }
      : defaultLevels(),
  );
  const [formError, setFormError] = useState<string | null>(null);

  const submit = () => {
    const t = title.trim();
    if (t.length < 2 || t.length > 255) return setFormError('Title must be between 2 and 255 characters.');
    let due_at: string | null = null;
    if (dueDate.trim()) {
      due_at = localDateTimeToIso(dueDate.trim(), dueTime.trim() || '17:00');
      if (!due_at) return setFormError('Enter the due date as YYYY-MM-DD and time as HH:MM.');
    }
    let estimated_minutes: number | null = null;
    if (minutes.trim()) {
      const n = Number(minutes.trim());
      if (!Number.isInteger(n) || n < 1 || n > 1440) return setFormError('Estimated minutes must be a whole number from 1 to 1440.');
      estimated_minutes = n;
    }
    setFormError(null);
    onSubmit({
      title: t,
      description: description.trim() || null,
      school_id: schoolId,
      due_at,
      category,
      estimated_minutes,
      urgency: LEVEL_VALUE[levels.urgency],
      impact: LEVEL_VALUE[levels.impact],
      risk: LEVEL_VALUE[levels.risk],
      deadline_proximity: LEVEL_VALUE[levels.deadline_proximity],
      workload_dependency: LEVEL_VALUE[levels.workload_dependency],
    });
  };

  const shownError = formError ?? error;

  return (
    <Modal visible animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <ScrollView showsVerticalScrollIndicator={false} keyboardShouldPersistTaps="handled">
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle} accessibilityRole="header">{task ? 'Edit task' : 'Create task'}</Text>
              <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" hitSlop={8}>
                <Text style={styles.closeText}>×</Text>
              </Pressable>
            </View>

            <Text style={styles.inputLabel}>Task title *</Text>
            <TextInput value={title} onChangeText={setTitle} placeholder="Enter task title" placeholderTextColor={MargColors.muted} style={styles.input} accessibilityLabel="Task title" maxLength={255} />

            <Text style={styles.inputLabel}>Description</Text>
            <TextInput value={description} onChangeText={setDescription} placeholder="Enter task details" placeholderTextColor={MargColors.muted} style={[styles.input, styles.multilineInput]} multiline accessibilityLabel="Description" />

            <Text style={styles.inputLabel}>School (optional)</Text>
            {schools.isLoading ? (
              <ActivityIndicator color={MargColors.teal} />
            ) : schools.error && !schools.data ? (
              <Text style={styles.hint}>Could not load schools: {(schools.error as Error).message}</Text>
            ) : (
              <View style={styles.options}>
                <Chip label="No school" active={schoolId === null} onPress={() => setSchoolId(null)} />
                {(schools.data ?? []).map((s) => (
                  <Chip key={s.id} label={s.name} active={schoolId === s.id} onPress={() => setSchoolId(s.id)} />
                ))}
              </View>
            )}

            <View style={styles.row}>
              <View style={{ flex: 2 }}>
                <Text style={styles.inputLabel}>Due date (YYYY-MM-DD)</Text>
                <TextInput value={dueDate} onChangeText={setDueDate} placeholder="YYYY-MM-DD" placeholderTextColor={MargColors.muted} style={styles.input} autoCapitalize="none" accessibilityLabel="Due date" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.inputLabel}>Time</Text>
                <TextInput value={dueTime} onChangeText={setDueTime} placeholder="HH:MM" placeholderTextColor={MargColors.muted} style={styles.input} autoCapitalize="none" accessibilityLabel="Due time" />
              </View>
            </View>

            <Text style={styles.inputLabel}>Category</Text>
            <View style={styles.options}>
              {CATEGORIES.map((c) => (
                <Chip key={c} label={humanize(c)} active={category === c} onPress={() => setCategory(category === c ? null : c)} />
              ))}
            </View>

            <Text style={styles.inputLabel}>Estimated minutes</Text>
            <TextInput value={minutes} onChangeText={setMinutes} placeholder="e.g. 60" placeholderTextColor={MargColors.muted} style={styles.input} keyboardType="number-pad" accessibilityLabel="Estimated minutes" />

            <Text style={styles.sectionLabel}>Priority factors</Text>
            <Text style={styles.hint}>The priority is calculated by the server from these factors.</Text>
            {FACTORS.map((f) => (
              <View key={f.key} style={styles.factorRow}>
                <Text style={styles.factorLabel}>{f.label}</Text>
                <View style={styles.factorOptions} accessibilityRole="radiogroup" accessibilityLabel={f.label}>
                  {LEVELS.map((l) => (
                    <Chip key={l} label={humanize(l)} active={levels[f.key] === l} onPress={() => setLevels((cur) => ({ ...cur, [f.key]: l }))} small />
                  ))}
                </View>
              </View>
            ))}

            {shownError ? <View style={{ marginTop: 14 }}><InlineNotice tone="danger" text={shownError} /></View> : null}

            <Pressable
              style={[styles.saveButton, saving && { opacity: 0.6 }]}
              onPress={submit}
              disabled={saving}
              accessibilityRole="button"
              accessibilityState={{ disabled: saving, busy: saving }}
            >
              {saving ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.saveButtonText}>{task ? 'Save changes' : 'Create task'}</Text>}
            </Pressable>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

function Chip({ label, active, onPress, small }: { label: string; active: boolean; onPress: () => void; small?: boolean }) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.option, small && styles.optionSmall, active && styles.optionActive]}
      accessibilityRole="radio"
      accessibilityState={{ selected: active }}
      accessibilityLabel={label}
    >
      <Text style={[styles.optionText, active && styles.optionTextActive]} numberOfLines={1}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(10,25,45,0.55)', justifyContent: 'flex-end' },
  modalCard: {
    backgroundColor: '#FFFFFF', borderTopLeftRadius: 24, borderTopRightRadius: 24,
    padding: 22, maxHeight: '92%', width: '100%', maxWidth: 900, alignSelf: 'center',
  },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 },
  modalTitle: { color: MargColors.navy, fontSize: 20, fontWeight: '800' },
  closeText: { color: MargColors.secondaryText, fontSize: 28 },
  inputLabel: { color: MargColors.navy, fontSize: 12, fontWeight: '700', marginBottom: 7, marginTop: 12 },
  sectionLabel: { color: MargColors.navy, fontSize: 14, fontWeight: '800', marginTop: 18 },
  hint: { color: MargColors.secondaryText, fontSize: 11, marginTop: 4, marginBottom: 4 },
  input: {
    borderWidth: 1, borderColor: MargColors.border, borderRadius: 11,
    paddingHorizontal: 13, paddingVertical: 12, color: MargColors.text,
    backgroundColor: '#FAFBFD', fontSize: 13,
  },
  multilineInput: { minHeight: 75, textAlignVertical: 'top' },
  row: { flexDirection: 'row', gap: 10 },
  options: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 },
  option: { borderWidth: 1, borderColor: MargColors.border, borderRadius: 9, paddingHorizontal: 12, paddingVertical: 9, maxWidth: '100%' },
  optionSmall: { paddingHorizontal: 10, paddingVertical: 7 },
  optionActive: { backgroundColor: MargColors.navy, borderColor: MargColors.navy },
  optionText: { color: MargColors.secondaryText, fontSize: 11, fontWeight: '700' },
  optionTextActive: { color: '#FFFFFF' },
  factorRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  factorLabel: { color: MargColors.text, fontSize: 12, fontWeight: '600', flexShrink: 1 },
  factorOptions: { flexDirection: 'row', gap: 6 },
  saveButton: { backgroundColor: MargColors.tealDark, padding: 15, borderRadius: 12, alignItems: 'center', marginTop: 22, marginBottom: 15, minHeight: 48 },
  saveButtonText: { color: '#FFFFFF', fontWeight: '800', fontSize: 14 },
});
