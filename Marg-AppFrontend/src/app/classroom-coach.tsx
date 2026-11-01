import { useLocalSearchParams, useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View, type ScrollViewInstance } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { plainAnswer } from '@/components/coach/answer-text';
import { ContextPicker, observationLabel, type ContextMode, type ManualContext } from '@/components/coach/context-picker';
import { ExchangeCard, type Exchange } from '@/components/coach/exchange-card';
import { TeacherFollowUpTracking } from '@/components/coach/teacher-follow-up-tracking';
import { WhatsAppShare } from '@/components/coach/whatsapp-share';
import { PageHeader, pageStyles } from '@/components/reports/page-chrome';
import { Button, Card, EmptyState, ErrorState, InlineNotice, LoadingState } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useCoachChat, useSchoolCoachHistory, useSchools } from '@/hooks/api';
import { toApiError } from '@/lib/api/client';
import type { CoachChatRequest, CoachChatResponse, ObservationResponse, SchoolResponse } from '@/lib/api/generated';
import type { SchoolCoachHistoryRecord } from '@/lib/api/services';
import { formatDateTime } from '@/lib/format';
import { uuid4 } from '@/lib/ids';

const MIN_Q = 3;
const MAX_Q = 2000;

function first(v?: string | string[]) {
  return Array.isArray(v) ? v[0] : v;
}

function historicalNotes(school: SchoolResponse, records: SchoolCoachHistoryRecord[]) {
  const lines = [
    `Selected school: ${school.name}.`,
    'HISTORICAL REFERENCE ONLY: These are past records, not facts about today. Keep them distinct from any new observation in the question.',
  ];
  if (records.length === 0) lines.push('No previous classroom visit or observation records are available for this school.');
  for (const record of records.slice(0, 5)) {
    const observation = record.observation;
    const date = formatDateTime(observation?.created_at ?? record.visit.completed_at ?? record.visit.started_at ?? record.visit.scheduled_at);
    if (!observation) {
      lines.push(`Past visit (${date}, ${record.visit.status})${record.visit.notes ? `: ${record.visit.notes.slice(0, 180)}` : '.'}`);
      continue;
    }

    lines.push(
      `Past observation (${date}; ${[observation.subject, observation.topic, record.classroomGrade ? `Grade ${record.classroomGrade}` : null].filter(Boolean).join(', ') || 'class details not recorded'}; teacher: ${record.teacherName ?? 'not recorded'}; class: ${record.classroomName ?? 'not recorded'}): ${observation.notes?.slice(0, 240) || 'No observation notes recorded.'}`,
    );
    for (const finding of record.findings.slice(0, 2)) {
      lines.push(`Previously recorded teaching finding (${finding.status}): ${finding.title} — ${finding.description.slice(0, 160)}`);
    }
    for (const gap of record.gaps.slice(0, 2)) {
      lines.push(`Previously recorded learning gap (${gap.severity}, ${gap.status}): ${gap.title} — ${gap.description.slice(0, 160)}`);
    }
  }
  return lines.join('\n').slice(0, 3900);
}

export default function ClassroomCoachScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ schoolId?: string; schoolName?: string; visitId?: string }>();
  const initialSchoolId = first(params.schoolId);
  const schoolName = first(params.schoolName);
  const visitId = first(params.visitId);

  const chat = useCoachChat();
  const schools = useSchools();
  const scrollRef = useRef<ScrollViewInstance>(null);

  const [selectedSchoolId, setSelectedSchoolId] = useState<string | undefined>(initialSchoolId);
  const [schoolPickerOpen, setSchoolPickerOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [mode, setMode] = useState<ContextMode>(visitId ? 'observation' : 'none');
  const [observation, setObservation] = useState<ObservationResponse | undefined>();
  const [manual, setManual] = useState<ManualContext>({ subject: '', grade: '', topic: '' });
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const requests = useRef(new Map<string, CoachChatRequest>()).current;
  const [share, setShare] = useState<{ key: string; text: string } | null>(null);
  const selectedSchool = schools.data?.find((school) => school.id === selectedSchoolId);
  const history = useSchoolCoachHistory(selectedSchool?.id);

  const trimmed = question.trim();
  const tooShort = trimmed.length > 0 && trimmed.length < MIN_Q;
  const busy = chat.isPending;
  const historyPending = !!selectedSchool && history.isLoading && !history.data;
  const historyUnavailable = !!selectedSchool && !!history.error && !history.data;
  const canSend =
    !busy &&
    !historyPending &&
    !historyUnavailable &&
    trimmed.length >= MIN_Q &&
    trimmed.length <= MAX_Q &&
    !(mode === 'observation' && !observation);

  const buildRequest = (): { body: CoachChatRequest; label?: string } => {
    const historicalContext = selectedSchool
      ? historicalNotes(selectedSchool, history.data ?? [])
      : undefined;
    if (mode === 'observation' && observation) {
      const currentObservation = [
        `NEW OBSERVATION supplied for this question (${formatDateTime(observation.created_at)}):`,
        observation.notes?.slice(0, 1000) || 'No notes recorded.',
      ].join('\n');
      const notes = [historicalContext, currentObservation].filter(Boolean).join('\n\n').slice(0, 3900);
      return {
        body: {
          question: trimmed,
          observation_id: observation.id,
          ...(notes ? { context: { notes } } : {}),
        },
        label: `Observation: ${observationLabel(observation)}`,
      };
    }
    if (mode === 'manual') {
      const ctx = { subject: manual.subject.trim() || null, grade: manual.grade.trim() || null, topic: manual.topic.trim() || null };
      if (ctx.subject || ctx.grade || ctx.topic) {
        const label = [ctx.subject, ctx.grade ? `Grade ${ctx.grade}` : null, ctx.topic].filter(Boolean).join(' · ');
        return {
          body: { question: trimmed, context: { ...ctx, ...(historicalContext ? { notes: historicalContext } : {}) } },
          label,
        };
      }
    }
    return {
      body: { question: trimmed, ...(historicalContext ? { context: { notes: historicalContext } } : {}) },
      label: selectedSchool?.name,
    };
  };

  const run = (id: string, body: CoachChatRequest) => {
    setExchanges((list) => list.map((e) => (e.id === id ? { ...e, status: 'pending', error: undefined, startedAt: Date.now() } : e)));
    chat.mutate(body, {
      onSuccess: (response) => setExchanges((list) => list.map((e) => (e.id === id ? { ...e, status: 'done', response } : e))),
      onError: (err) => {
        const e = toApiError(err);
        setExchanges((list) => list.map((x) => (x.id === id ? { ...x, status: 'error', error: { message: e.message, status: e.status } } : x)));
      },
    });
  };

  const send = () => {
    if (!canSend) return;
    const { body, label } = buildRequest();
    const id = uuid4();
    requests.set(id, body);
    setExchanges((list) => [...list, { id, question: trimmed, contextLabel: label, startedAt: Date.now(), status: 'pending' }]);
    setQuestion('');
    run(id, body);
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
  };

  const startShare = (r: CoachChatResponse) => {
    setShare({ key: uuid4(), text: plainAnswer(r.answer) });
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 100);
  };

  return (
    <SafeAreaView style={pageStyles.safeArea} edges={['top']}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView ref={scrollRef} contentContainerStyle={pageStyles.content} keyboardShouldPersistTaps="handled">
          <PageHeader
            title="Classroom Coach"
            subtitle="Teaching support grounded in the MARG knowledge base"
            right={<Button label="Analyse an observation" variant="secondary" onPress={() => router.push('/observations')} />}
          />

          {schoolName || initialSchoolId || visitId ? (
            <View style={styles.contextChip} accessible accessibilityLabel={`Opened from ${schoolName ? schoolName : 'a school visit'}`}>
              <Text style={styles.contextChipText}>
                {schoolName ? `School: ${schoolName}` : initialSchoolId ? 'School context selected' : 'From a school visit'}
                {visitId ? ' · visit observations shown first' : ''}
              </Text>
            </View>
          ) : null}

          <Card>
            <Text style={pageStyles.itemTitle}>Select School</Text>
            {schools.isLoading && !schools.data ? (
              <LoadingState label="Loading assigned schools…" />
            ) : !schools.data ? (
              <ErrorState error={schools.error} onRetry={() => void schools.refetch()} />
            ) : schools.data.length === 0 ? (
              <EmptyState title="No assigned schools" message="No schools are currently assigned to your account." />
            ) : (
              <>
                <Pressable
                  accessibilityRole="button"
                  accessibilityState={{ expanded: schoolPickerOpen }}
                  accessibilityLabel={`Select school. ${selectedSchool?.name ?? 'No school selected'}`}
                  onPress={() => setSchoolPickerOpen((open) => !open)}
                  style={styles.schoolSelect}
                >
                  <Text style={styles.schoolSelectText}>{selectedSchool?.name ?? 'Choose a school'}</Text>
                  <Text style={styles.schoolSelectArrow}>{schoolPickerOpen ? '▴' : '▾'}</Text>
                </Pressable>
                {schoolPickerOpen ? (
                  <View style={styles.schoolOptions}>
                    {[...schools.data].sort((a, b) => a.name.localeCompare(b.name)).map((school) => (
                      <Pressable
                        key={school.id}
                        accessibilityRole="button"
                        accessibilityState={{ selected: school.id === selectedSchoolId }}
                        onPress={() => {
                          setSelectedSchoolId(school.id);
                          setSchoolPickerOpen(false);
                        }}
                        style={styles.schoolOption}
                      >
                        <Text style={[styles.schoolOptionText, school.id === selectedSchoolId && styles.schoolOptionSelected]}>
                          {school.name}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                ) : null}
                {schools.error ? <InlineNotice tone="warning" text="Could not refresh the assigned school list." /> : null}
              </>
            )}
          </Card>

          <View style={styles.historySection}>
            <Text style={pageStyles.itemTitle}>Previous Records &amp; Observations</Text>
            {!selectedSchool ? (
              <EmptyState title="Select a school" message="Choose a school to view its previous visits and classroom records." />
            ) : history.isLoading && !history.data ? (
              <LoadingState label="Loading previous records…" />
            ) : !history.data ? (
              <ErrorState error={history.error} onRetry={() => void history.refetch()} />
            ) : history.data.length === 0 ? (
              <EmptyState title="No previous records" message="No previous classroom visits or observations are recorded for this school." />
            ) : (
              <>
                {history.error ? <InlineNotice tone="warning" text="Could not refresh this school's records; showing the last loaded data." /> : null}
                <View style={{ gap: 8 }}>
                  {history.data.map((record) => (
                    <Card key={`${record.visit.id}-${record.observation?.id ?? 'visit'}`} style={styles.historyCard}>
                      <Text style={styles.recordTitle}>
                        {record.observation
                          ? [record.observation.subject, record.observation.topic].filter(Boolean).join(' · ') || 'Classroom observation'
                          : 'Previous classroom visit'}
                      </Text>
                      <Text style={styles.recordMeta}>
                        {formatDateTime(record.observation?.created_at ?? record.visit.completed_at ?? record.visit.started_at ?? record.visit.scheduled_at)}
                        {record.teacherName ? ` · ${record.teacherName}` : ''}
                        {record.classroomName ? ` · ${record.classroomName}` : ''}
                      </Text>
                      {record.observation?.notes ? (
                        <Text style={styles.recordText} numberOfLines={3}>{record.observation.notes}</Text>
                      ) : record.visit.notes ? (
                        <Text style={styles.recordText} numberOfLines={2}>{record.visit.notes}</Text>
                      ) : null}
                      {record.findings.length > 0 ? (
                        <View style={styles.recordDetails}>
                          <Text style={styles.recordLabel}>Teaching findings</Text>
                          {record.findings.slice(0, 3).map((finding) => (
                            <Text key={finding.id} style={styles.recordText} numberOfLines={2}>• {finding.title}: {finding.description}</Text>
                          ))}
                        </View>
                      ) : null}
                      {record.gaps.length > 0 ? (
                        <View style={styles.recordDetails}>
                          <Text style={styles.recordLabel}>Learning gaps</Text>
                          {record.gaps.slice(0, 3).map((gap) => (
                            <Text key={gap.id} style={styles.recordText} numberOfLines={2}>• {gap.title} ({gap.severity}): {gap.description}</Text>
                          ))}
                        </View>
                      ) : null}
                      {!record.observation && !record.visit.notes ? (
                        <Text style={styles.recordMeta}>Visit status: {record.visit.status}. No observation recorded.</Text>
                      ) : null}
                    </Card>
                  ))}
                </View>
              </>
            )}
          </View>

          {exchanges.length > 0 ? (
            <View style={{ marginTop: 4 }}>
              {exchanges.map((e) => (
                <ExchangeCard
                  key={e.id}
                  exchange={e}
                  retryDisabled={busy}
                  onRetry={() => {
                    const body = requests.get(e.id);
                    if (body) run(e.id, body);
                  }}
                  onShare={startShare}
                />
              ))}
            </View>
          ) : null}

          <Card>
            <Text style={pageStyles.label}>Your question</Text>
            <TextInput
              value={question}
              onChangeText={setQuestion}
              placeholder="Type your teaching question"
              placeholderTextColor={C.muted}
              multiline
              maxLength={MAX_Q}
              editable={!busy}
              style={[pageStyles.input, styles.questionInput]}
              accessibilityLabel="Question for the Classroom Coach"
              accessibilityHint={`Between ${MIN_Q} and ${MAX_Q} characters`}
            />
            <View style={pageStyles.rowBetween}>
              <Text style={tooShort ? pageStyles.error : pageStyles.muted}>
                {tooShort ? `At least ${MIN_Q} characters.` : `${trimmed.length}/${MAX_Q}`}
              </Text>
            </View>

            <ContextPicker
              mode={mode}
              onModeChange={setMode}
              observationId={observation?.id}
              onObservationChange={setObservation}
              manual={manual}
              onManualChange={setManual}
              visitId={visitId}
              disabled={busy}
            />
            {mode === 'observation' && !observation ? <Text style={pageStyles.muted}>Select an observation to use as context.</Text> : null}

            <Button
              label={historyPending ? 'Loading school records…' : busy ? 'Waiting for the Coach…' : 'Ask the Coach'}
              onPress={send}
              disabled={!canSend}
              loading={busy || historyPending}
              style={{ marginTop: 14 }}
            />
          </Card>

          {share ? <WhatsAppShare key={share.key} initialText={share.text} onClose={() => setShare(null)} /> : null}
          <TeacherFollowUpTracking schoolId={selectedSchool?.id} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  contextChip: { alignSelf: 'flex-start', backgroundColor: '#E8F7F5', borderRadius: 999, paddingHorizontal: 12, paddingVertical: 6, marginBottom: 12 },
  contextChipText: { color: C.tealDark, fontSize: 13, fontWeight: '700' },
  schoolSelect: { marginTop: 10, borderWidth: 1, borderColor: C.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 12, backgroundColor: C.surface, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  schoolSelectText: { color: C.text, fontSize: 15, flex: 1 },
  schoolSelectArrow: { color: C.tealDark, fontSize: 16, marginLeft: 8 },
  schoolOptions: { marginTop: 6, borderWidth: 1, borderColor: C.border, borderRadius: 10, overflow: 'hidden' },
  schoolOption: { paddingHorizontal: 12, paddingVertical: 10, backgroundColor: C.surface, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: C.border },
  schoolOptionText: { color: C.text, fontSize: 14 },
  schoolOptionSelected: { color: C.tealDark, fontWeight: '700' },
  historySection: { gap: 8 },
  historyCard: { gap: 5 },
  recordTitle: { color: C.navy, fontSize: 14, fontWeight: '700' },
  recordMeta: { color: C.secondaryText, fontSize: 12 },
  recordText: { color: C.text, fontSize: 13, lineHeight: 18 },
  recordDetails: { marginTop: 4, gap: 3 },
  recordLabel: { color: C.tealDark, fontSize: 12, fontWeight: '700' },
  questionInput: { minHeight: 90, textAlignVertical: 'top' },
});
