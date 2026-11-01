import { useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, TextInput, View } from 'react-native';

import { InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useCreateSchedule } from '@/hooks/api';
import type { SchoolVisitResponse } from '@/lib/api/generated';
import { formatDateTime, localDateTimeToIso, toDateInput } from '@/lib/format';

import { schStyles as styles } from './schedule-styles';

type Props = {
  visit: SchoolVisitResponse | null;
  schoolName: string;
  onClose: () => void;
  onCreated: () => void;
};

const hhmm = (d: Date) => `${`${d.getHours()}`.padStart(2, '0')}:${`${d.getMinutes()}`.padStart(2, '0')}`;

/** Propose a new time window for a planned visit (accepting it later moves the visit). */
export function ProposalFormModal(props: Props) {
  return props.visit ? <ProposalForm key={props.visit.id} {...props} visit={props.visit} /> : null;
}

function ProposalForm({ visit, schoolName, onClose, onCreated }: Props & { visit: SchoolVisitResponse }) {
  const createSchedule = useCreateSchedule();
  const initialStart = new Date(visit.scheduled_at);
  const [date, setDate] = useState(toDateInput(initialStart));
  const [start, setStart] = useState(hhmm(initialStart));
  const [end, setEnd] = useState(() => hhmm(new Date(initialStart.getTime() + 3 * 60 * 60 * 1000)));
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    const startIso = localDateTimeToIso(date.trim(), start.trim());
    const endIso = localDateTimeToIso(date.trim(), end.trim());
    if (!startIso || !endIso) return setError('Enter the date as YYYY-MM-DD and times as HH:MM.');
    if (new Date(endIso) <= new Date(startIso)) return setError('The end time must be after the start time.');
    if (notes.length > 2000) return setError('Notes can be at most 2000 characters.');
    setError(null);
    try {
      await createSchedule.mutateAsync({
        school_visit_id: visit.id,
        proposed_start_at: startIso,
        proposed_end_at: endIso,
        notes: notes.trim() || null,
      });
      onCreated();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.modalBackdrop}>
        <View style={styles.modalCard}>
          <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle} accessibilityRole="header">Propose visit time</Text>
              <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Close" hitSlop={8}>
                <Text style={styles.closeText}>×</Text>
              </Pressable>
            </View>
            <Text style={styles.schoolName}>{schoolName} · currently {formatDateTime(visit.scheduled_at)}</Text>

            <Text style={styles.inputLabel}>Date (YYYY-MM-DD)</Text>
            <TextInput style={styles.input} value={date} onChangeText={setDate} autoCapitalize="none" placeholder="YYYY-MM-DD" placeholderTextColor={C.muted} accessibilityLabel="Proposed date" />
            <View style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={styles.inputLabel}>Start (HH:MM)</Text>
                <TextInput style={styles.input} value={start} onChangeText={setStart} autoCapitalize="none" placeholder="09:30" placeholderTextColor={C.muted} accessibilityLabel="Proposed start time" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.inputLabel}>End (HH:MM)</Text>
                <TextInput style={styles.input} value={end} onChangeText={setEnd} autoCapitalize="none" placeholder="12:30" placeholderTextColor={C.muted} accessibilityLabel="Proposed end time" />
              </View>
            </View>
            <Text style={styles.inputLabel}>Notes</Text>
            <TextInput style={[styles.input, { minHeight: 70, textAlignVertical: 'top' }]} value={notes} onChangeText={setNotes} multiline placeholder="Reason or travel details" placeholderTextColor={C.muted} accessibilityLabel="Notes" />

            {error ? <View style={{ marginTop: 12 }}><InlineNotice tone="danger" text={error} /></View> : null}

            <Pressable
              style={[styles.saveButton, createSchedule.isPending && styles.disabled]}
              onPress={() => void submit()}
              disabled={createSchedule.isPending}
              accessibilityRole="button"
              accessibilityState={{ disabled: createSchedule.isPending, busy: createSchedule.isPending }}
            >
              {createSchedule.isPending ? <ActivityIndicator color="#FFFFFF" /> : <Text style={styles.saveButtonText}>Create proposal</Text>}
            </Pressable>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}
