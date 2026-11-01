/**
 * Result of one Mentor Intelligence agent run: AI narrative (clearly
 * labelled, only when ai_status === 'generated') and the computed analysis.
 */
import { StyleSheet, Text, View } from 'react-native';

import { pageStyles } from '@/components/reports/page-chrome';
import { InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import type { MentorAgent, MiExecution } from '@/lib/api/services';
import { formatDateTime, humanize } from '@/lib/format';

import { FactsView } from './fact-views';
import { arr, obj, str, strs, type Obj } from './facts';
import type { Lookups } from './lookups';

const AI_STATUS_TEXT: Record<string, string> = {
  disabled: 'AI narrative is turned off on the server.',
  unavailable: 'The AI service could not be reached.',
  not_needed: 'No AI narrative was needed for this analysis.',
  failed: 'The AI narrative could not be produced.',
  rejected: 'The AI narrative did not pass validation and was discarded.',
};

function refName(o: Obj, L: Lookups): string | undefined {
  return (
    L.taskTitle(str(o.task_ref)) ??
    L.followUp(str(o.followup_ref))?.description ??
    L.schoolName(str(o.school_ref)) ??
    (str(o.ref) ? L.taskTitle(str(o.ref)) ?? L.visitLabel(str(o.ref)) : undefined)
  );
}

function AiInsights({ insights, L }: { insights: Obj; L: Lookups }) {
  const content = obj(insights.content);
  return (
    <View style={styles.ai} accessibilityLabel="AI-generated suggestions">
      <Text style={styles.aiTag}>✦ AI-generated</Text>
      <Text style={styles.aiLabel}>{str(insights.label) ?? 'AI-generated suggestions. Not records, not decisions.'}</Text>
      {Object.entries(content).map(([key, value]) => {
        if (typeof value === 'string') {
          return (
            <Text key={key} style={styles.aiText}>
              {value}
            </Text>
          );
        }
        if (Array.isArray(value) && value.length) {
          const asStrings = strs(value);
          return (
            <View key={key} style={{ marginTop: 6 }}>
              <Text style={styles.aiHeading}>{humanize(key)}</Text>
              {asStrings.length
                ? asStrings.map((s, i) => (
                    <Text key={i} style={styles.aiText}>
                      • {s}
                    </Text>
                  ))
                : arr(value).map((o, i) => {
                    const name = refName(o, L);
                    const texts = Object.entries(o)
                      .filter(([k, v]) => !k.endsWith('ref') && (typeof v === 'string' || Array.isArray(v)))
                      .map(([, v]) => (Array.isArray(v) ? strs(v).join('; ') : (v as string)));
                    return (
                      <Text key={i} style={styles.aiText}>
                        • {name ? <Text style={{ fontWeight: '700' }}>{name}: </Text> : null}
                        {texts.join(' — ')}
                      </Text>
                    );
                  })}
            </View>
          );
        }
        return null;
      })}
    </View>
  );
}

export function AgentResult({ agent, execution, lookups }: { agent: MentorAgent; execution: MiExecution; lookups: Lookups }) {
  const result = execution.result;
  if (!result) {
    return <InlineNotice tone="danger" text={execution.error ?? `The analysis did not complete (status: ${humanize(execution.status)}).`} />;
  }
  const r = result as typeof result & { is_demo_data?: boolean; missing_data?: unknown; proposals?: unknown };
  const aiStatus = execution.ai_status ?? result.ai_status;
  const missing = arr(r.missing_data);
  const proposals = arr(r.proposals);

  return (
    <View>
      <Text style={pageStyles.muted}>
        Run {formatDateTime(execution.finished_at ?? execution.created_at)}
        {execution.replayed ? ' · previous result replayed' : ''}
      </Text>
      {r.is_demo_data ? <InlineNotice tone="warning" text="The server reports that this analysis used demonstration data." /> : null}

      {aiStatus === 'generated' && result.ai_insights ? (
        <AiInsights insights={obj(result.ai_insights)} L={lookups} />
      ) : (
        <View style={styles.noAi}>
          <Text style={styles.noAiText}>
            AI narrative unavailable — {AI_STATUS_TEXT[aiStatus] ?? `AI status: ${humanize(aiStatus)}.`} The computed analysis below is complete.
          </Text>
        </View>
      )}

      <View style={styles.computed}>
        <Text style={styles.computedTag}>Computed from your records</Text>
        <FactsView agent={agent} facts={obj(result.facts)} lookups={lookups} />
      </View>

      {missing.length ? (
        <View style={{ marginTop: 10 }}>
          <Text style={styles.missingTitle}>Data gaps affecting this analysis</Text>
          {missing.map((m, i) => (
            <Text key={i} style={pageStyles.muted}>
              • {lookups.schoolName(str(m.entity_ref)) ?? humanize(str(m.entity_type))}: {humanize(str(m.field))} missing. {str(m.impact)}
            </Text>
          ))}
        </View>
      ) : null}

      {proposals.length ? (
        <InlineNotice
          tone="info"
          text={`${proposals.length} suggested action${proposals.length === 1 ? '' : 's'} added to “Suggested actions” below. Nothing changes until you approve.`}
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  ai: { backgroundColor: '#F3EDFA', borderRadius: 12, padding: 12, marginTop: 10, gap: 4 },
  aiTag: { color: '#6B3FA0', fontSize: 12, fontWeight: '800' },
  aiLabel: { color: '#6B3FA0', fontSize: 12, fontStyle: 'italic', marginBottom: 4 },
  aiHeading: { color: C.navy, fontSize: 13, fontWeight: '800' },
  aiText: { color: C.text, fontSize: 14, lineHeight: 20 },
  noAi: { backgroundColor: '#EEF1F5', borderRadius: 12, padding: 10, marginTop: 10 },
  noAiText: { color: '#4A5568', fontSize: 13, lineHeight: 18 },
  computed: { marginTop: 12 },
  computedTag: { color: C.tealDark, fontSize: 12, fontWeight: '800', marginBottom: 4 },
  missingTitle: { color: C.navy, fontSize: 13, fontWeight: '800', marginBottom: 2 },
});
