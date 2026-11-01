import { useMemo, useState, type ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { Button, Card, InlineNotice, StatusBadge } from '@/components/ui/states';
import { ChipSelect, fieldStyles, MutationError, SectionTitle } from '@/components/visits/field-ui';
import { MargColors as C } from '@/constants/theme';
import { useAiJob, useAnalyseObservation, useApplyAiJob, useGaps } from '@/hooks/api';
import { useObservationAiJobs } from '@/hooks/api-field';
import type { AIJobApplyRequest, AIJobResponse, ObservationResponse } from '@/lib/api/generated';
import { formatDateTime } from '@/lib/format';

const MIN_NOTES = 20;
const RUNNING = ['queued', 'processing'];

interface AiFinding { title: string; description: string; category?: string; confidence?: number; evidence_reference?: string }
interface AiGap { title: string; description: string; subject?: string | null; grade?: string | null; severity?: string }
interface AiRecommendation { title: string; description: string; rationale?: string; category?: string }
interface AiSource { document: string; title?: string | null; page?: number; relevance?: number | null; excerpt?: string | null }
interface AiResult {
  summary: string;
  findings: AiFinding[];
  learning_gaps: AiGap[];
  recommendations: AiRecommendation[];
  sources: AiSource[];
  provider?: string;
  model?: string;
}

const arr = <X,>(v: unknown): X[] => (Array.isArray(v) ? (v as X[]) : []);
function parseResult(payload: AIJobResponse['result_payload']): AiResult | null {
  if (!payload) return null;
  return {
    summary: typeof payload.summary === 'string' ? payload.summary : '',
    findings: arr<AiFinding>(payload.findings),
    learning_gaps: arr<AiGap>(payload.learning_gaps),
    recommendations: arr<AiRecommendation>(payload.recommendations),
    sources: arr<AiSource>(payload.sources),
    provider: typeof payload.provider === 'string' ? payload.provider : undefined,
    model: typeof payload.model === 'string' ? payload.model : undefined,
  };
}

export function AiAnalysisSection({ observation }: { observation: ObservationResponse }) {
  const history = useObservationAiJobs(observation.id);
  const analyse = useAnalyseObservation();
  const [jobId, setJobId] = useState<string | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});

  const latest = history.data?.[0];
  // Resume a job that is still running (e.g. after leaving the screen).
  const activeJobId = jobId ?? (latest && RUNNING.includes(latest.status) ? latest.id : undefined);
  const job = useAiJob(activeJobId);
  const j = job.data;

  const notesLength = observation.notes?.trim().length ?? 0;
  const running = analyse.isPending || (!!j && RUNNING.includes(j.status));

  const start = () => {
    analyse.mutate(observation.id, {
      onSuccess: (created) => {
        setJobId(created.id);
        void history.refetch();
      },
    });
  };

  return (
    <>
      <SectionTitle title="Classroom Coach analysis" />
      <Card>
        <Text style={fieldStyles.itemText}>
          The Classroom Coach reads your notes and suggests findings, learning gaps and recommendations, grounded in the MARG teacher
          resources. AI suggestions are not official until you approve them.
        </Text>
        {notesLength < MIN_NOTES ? (
          <View style={{ marginTop: 10 }}>
            <InlineNotice tone="warning" text={`Add at least ${MIN_NOTES} characters of observation notes before requesting analysis.`} />
          </View>
        ) : null}
        <View style={[fieldStyles.row, { marginTop: 10 }]}>
          <Button
            label={j?.status === 'completed' || j?.status === 'failed' ? 'Analyse again' : 'Analyse with Classroom Coach'}
            onPress={start}
            loading={analyse.isPending}
            disabled={running || notesLength < MIN_NOTES}
            style={fieldStyles.grow}
          />
          {!activeJobId && latest?.status === 'completed' ? (
            <Button label={`View last analysis (${formatDateTime(latest.completed_at ?? latest.created_at)})`} variant="secondary" onPress={() => setJobId(latest.id)} style={fieldStyles.grow} />
          ) : null}
        </View>
        <MutationError error={analyse.error} />

        {activeJobId && !j && job.isLoading ? <ActivityIndicator color={C.teal} style={{ marginTop: 12 }} /> : null}
        {activeJobId && !j && job.error ? <MutationError error={job.error} /> : null}

        {j && RUNNING.includes(j.status) ? (
          <View style={styles.running} accessibilityRole="progressbar" accessibilityLabel="Analysis in progress">
            <ActivityIndicator color={C.teal} />
            <Text style={fieldStyles.muted}>Analysing… this usually takes 20–60 seconds. You can keep working; results appear here.</Text>
          </View>
        ) : null}

        {j?.status === 'failed' || j?.status === 'cancelled' ? (
          <View style={{ marginTop: 12 }}>
            <InlineNotice tone="danger" text={`Analysis ${j.status}: ${j.error_message ?? 'No details were provided.'}`} />
            <Button label="Try again" variant="secondary" onPress={start} loading={analyse.isPending} disabled={notesLength < MIN_NOTES} />
          </View>
        ) : null}
      </Card>

      {j?.status === 'completed' ? (
        applied[j.id] ? (
          <InlineNotice tone="success" text={applied[j.id]} />
        ) : (
          <SuggestionsReview
            key={j.id}
            job={j}
            observation={observation}
            onApplied={(msg) => setApplied((a) => ({ ...a, [j.id]: msg }))}
          />
        )
      ) : null}
    </>
  );
}

function Check({ checked, onToggle, label, children }: { checked: boolean; onToggle: () => void; label: string; children: ReactNode }) {
  return (
    <Pressable
      onPress={onToggle}
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      accessibilityLabel={label}
      style={[styles.check, checked && styles.checkOn]}
    >
      <View style={[styles.box, checked && styles.boxOn]}>{checked ? <Text style={styles.tick}>✓</Text> : null}</View>
      <View style={{ flex: 1 }}>{children}</View>
    </Pressable>
  );
}

function SuggestionsReview({ job, observation, onApplied }: { job: AIJobResponse; observation: ObservationResponse; onApplied: (msg: string) => void }) {
  const result = useMemo(() => parseResult(job.result_payload), [job.result_payload]);
  const existingGaps = useGaps({ observation_id: observation.id });
  const apply = useApplyAiJob();
  const [findingSel, setFindingSel] = useState<number[]>([]);
  const [gapSel, setGapSel] = useState<number[]>([]);
  const [recSel, setRecSel] = useState<number[]>([]);
  const [recLink, setRecLink] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  if (!result) return <InlineNotice tone="warning" text="The analysis finished without a readable result. Try analysing again." />;

  const toggle = (list: number[], set: (v: number[]) => void, i: number) => set(list.includes(i) ? list.filter((x) => x !== i) : [...list, i].sort((a, b) => a - b));

  const linkOptions = [
    ...gapSel.map((gi) => ({ value: `ai:${gi}`, label: `New: ${result.learning_gaps[gi]?.title ?? `Gap ${gi + 1}`}` })),
    ...(existingGaps.data ?? []).map((g) => ({ value: `gap:${g.id}`, label: `Existing: ${g.title}` })),
  ];
  const linkFor = (ri: number) => {
    const chosen = recLink[ri];
    if (chosen && linkOptions.some((o) => o.value === chosen)) return chosen;
    return linkOptions[0]?.value;
  };

  const isDraft = observation.status === 'draft';
  const nothing = findingSel.length + gapSel.length + recSel.length === 0;

  const submit = () => {
    setError(null);
    const recommendations: NonNullable<AIJobApplyRequest['recommendations']> = [];
    for (const ri of recSel) {
      const link = linkFor(ri);
      if (!link) return setError('Each selected recommendation must be linked to a learning gap. Select a learning gap above.');
      if (link.startsWith('ai:')) recommendations.push({ index: ri, learning_gap_index: gapSel.indexOf(Number(link.slice(3))) });
      else recommendations.push({ index: ri, learning_gap_id: link.slice(4) });
    }
    apply.mutate(
      { id: job.id, body: { finding_indexes: findingSel, learning_gap_indexes: gapSel, recommendations } },
      {
        onSuccess: (res) =>
          onApplied(
            `Added ${res.finding_ids.length} finding(s), ${res.learning_gap_ids.length} learning gap(s) and ${res.recommendation_ids.length} recommendation(s) as suggestions. Review and approve them below to make them official.`,
          ),
      },
    );
  };

  return (
    <Card style={{ borderColor: '#D9C9F0' }}>
      <View style={fieldStyles.rowBetween}>
        <Text style={fieldStyles.formTitle}>AI suggestions</Text>
        <StatusBadge status="ai_suggested" label="Not yet approved" />
      </View>
      <InlineNotice tone="info" text="AI suggestions are not official until you approve them. Tick only what matches what you observed." />
      {result.summary ? <Text style={fieldStyles.itemText}>{result.summary}</Text> : null}

      <Text style={styles.group}>Findings ({result.findings.length})</Text>
      {result.findings.length === 0 ? <Text style={fieldStyles.muted}>No findings suggested.</Text> : null}
      {result.findings.map((f, i) => (
        <Check key={`f${i}`} checked={findingSel.includes(i)} onToggle={() => toggle(findingSel, setFindingSel, i)} label={`Keep finding: ${f.title}`}>
          <Text style={fieldStyles.itemTitle}>{f.title}</Text>
          <Text style={fieldStyles.itemText}>{f.description}</Text>
          <Text style={fieldStyles.muted}>
            {[f.category, f.confidence != null ? `confidence ${Math.round(f.confidence * 100)}%` : null].filter(Boolean).join(' · ')}
          </Text>
          {f.evidence_reference ? <Text style={[fieldStyles.muted, styles.quote]}>“{f.evidence_reference}”</Text> : null}
        </Check>
      ))}

      <Text style={styles.group}>Learning gaps ({result.learning_gaps.length})</Text>
      {result.learning_gaps.length === 0 ? <Text style={fieldStyles.muted}>No learning gaps suggested.</Text> : null}
      {result.learning_gaps.map((g, i) => (
        <Check key={`g${i}`} checked={gapSel.includes(i)} onToggle={() => toggle(gapSel, setGapSel, i)} label={`Keep learning gap: ${g.title}`}>
          <Text style={fieldStyles.itemTitle}>{g.title}</Text>
          <Text style={fieldStyles.itemText}>{g.description}</Text>
          <Text style={fieldStyles.muted}>
            {[g.severity ? `${g.severity} severity` : null, g.subject, g.grade ? `Grade ${g.grade}` : null].filter(Boolean).join(' · ')}
          </Text>
        </Check>
      ))}

      <Text style={styles.group}>Recommendations ({result.recommendations.length})</Text>
      {result.recommendations.length === 0 ? <Text style={fieldStyles.muted}>No recommendations suggested.</Text> : null}
      {result.recommendations.map((r, i) => {
        const selected = recSel.includes(i);
        return (
          <View key={`r${i}`}>
            <Check checked={selected} onToggle={() => toggle(recSel, setRecSel, i)} label={`Keep recommendation: ${r.title}`}>
              <Text style={fieldStyles.itemTitle}>{r.title}</Text>
              <Text style={fieldStyles.itemText}>{r.description}</Text>
              {r.rationale ? <Text style={fieldStyles.muted}>Why: {r.rationale}</Text> : null}
            </Check>
            {selected ? (
              <View style={styles.linkBox}>
                <ChipSelect
                  label="Link to learning gap"
                  options={linkOptions}
                  value={linkFor(i)}
                  onChange={(v) => setRecLink((m) => ({ ...m, [i]: v }))}
                  emptyText="Select a learning gap above (or add one to this observation) to link this recommendation."
                />
              </View>
            ) : null}
          </View>
        );
      })}

      {result.sources.length > 0 ? (
        <>
          <Text style={styles.group}>Supporting references</Text>
          {result.sources.map((s, i) => (
            <View key={`s${i}`} style={styles.source}>
              <Text style={styles.sourceTitle}>
                {s.title || s.document}
                {s.page != null ? `, p. ${s.page}` : ''}
              </Text>
              {s.excerpt ? (
                <Text style={fieldStyles.muted} numberOfLines={3}>
                  {s.excerpt}
                </Text>
              ) : null}
            </View>
          ))}
        </>
      ) : (
        <Text style={[fieldStyles.muted, { marginTop: 10 }]}>No supporting references were returned for this analysis.</Text>
      )}
      {result.model ? <Text style={[fieldStyles.muted, { marginTop: 8 }]}>Generated by {[result.provider, result.model].filter(Boolean).join(' · ')}</Text> : null}

      {isDraft ? (
        <View style={{ marginTop: 12 }}>
          <InlineNotice tone="warning" text="Submit the observation before adding these suggestions." />
        </View>
      ) : null}
      {error ? <InlineNotice tone="danger" text={error} /> : null}
      <MutationError error={apply.error} />
      <Button
        label="Add selected as suggestions"
        onPress={submit}
        loading={apply.isPending}
        disabled={isDraft || nothing}
        style={{ marginTop: 12 }}
      />
    </Card>
  );
}

const styles = StyleSheet.create({
  running: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 12 },
  group: { color: C.navy, fontSize: 15, fontWeight: '800', marginTop: 16, marginBottom: 6 },
  check: { flexDirection: 'row', gap: 10, borderWidth: 1, borderColor: C.border, borderRadius: 12, padding: 12, marginBottom: 8, backgroundColor: C.surface },
  checkOn: { borderColor: C.teal, backgroundColor: '#F2FBFA' },
  box: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: C.muted, alignItems: 'center', justifyContent: 'center', marginTop: 2 },
  boxOn: { backgroundColor: C.teal, borderColor: C.teal },
  tick: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' },
  quote: { fontStyle: 'italic', marginTop: 4 },
  linkBox: { marginLeft: 32, marginBottom: 6 },
  source: { borderLeftWidth: 3, borderLeftColor: C.teal, paddingLeft: 10, marginBottom: 10 },
  sourceTitle: { color: C.navy, fontSize: 13, fontWeight: '700' },
});
