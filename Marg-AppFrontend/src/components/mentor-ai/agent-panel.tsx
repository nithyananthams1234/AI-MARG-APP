/**
 * Agent picker + options + run + result for the Mentor AI Assistant.
 * Calls POST /mentor-ai/agents/{agent} through useRunMentorAgent.
 */
import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { pageStyles } from '@/components/reports/page-chrome';
import { Button, Card, EmptyState, InlineNotice } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useRunMentorAgent } from '@/hooks/api';
import type { MentorAgent, MiExecution } from '@/lib/api/services';
import { humanize } from '@/lib/format';

import { AgentResult } from './agent-result';
import type { Lookups } from './lookups';

type Field =
  | { key: string; kind: 'date'; label: string; hint: string }
  | { key: string; kind: 'int'; label: string; min: number; max: number; def: number }
  | { key: string; kind: 'choice'; label: string; choices: { value: string; label: string }[]; def: string };

interface AgentDef {
  id: MentorAgent;
  title: string;
  description: string;
  icon: string;
  fields: Field[];
}

const AGENTS: AgentDef[] = [
  { id: 'daily_plan', title: 'Daily plan', icon: '◷', description: 'Time blocks for a day from your visits and prioritised tasks.', fields: [{ key: 'date', kind: 'date', label: 'Date', hint: 'Today if empty' }] },
  { id: 'weekly_plan', title: 'Weekly plan', icon: '▦', description: 'Visits, deadlines, follow-ups and workload for a week.', fields: [{ key: 'week_start', kind: 'date', label: 'Week starting', hint: 'Today if empty' }] },
  { id: 'task_prioritisation', title: 'Prioritise tasks', icon: '↑', description: 'Ranks open tasks with a transparent priority score.', fields: [] },
  { id: 'workload_analysis', title: 'Workload', icon: '◔', description: 'Workload index per day against your working time.', fields: [{ key: 'days', kind: 'int', label: 'Days', min: 1, max: 31, def: 7 }] },
  { id: 'schedule_analysis', title: 'Schedule check', icon: '⚠', description: 'Finds calendar conflicts and free time; may propose reschedules.', fields: [{ key: 'days', kind: 'int', label: 'Days', min: 1, max: 21, def: 7 }] },
  {
    id: 'visit_planning',
    title: 'Visit planning',
    icon: '⌖',
    description: 'Ranks schools needing attention; may propose visits.',
    fields: [
      { key: 'days', kind: 'int', label: 'Days', min: 1, max: 21, def: 7 },
      { key: 'max_schools', kind: 'int', label: 'Max schools', min: 1, max: 10, def: 3 },
    ],
  },
  { id: 'followup_analysis', title: 'Follow-ups', icon: '↻', description: 'Overdue follow-ups and items awaiting your verification.', fields: [] },
  {
    id: 'report',
    title: 'Activity report',
    icon: '☰',
    description: 'Summary of recorded activity for a day or week.',
    fields: [{ key: 'period', kind: 'choice', label: 'Period', def: 'weekly', choices: [{ value: 'daily', label: 'Daily' }, { value: 'weekly', label: 'Weekly' }] }],
  },
];

function defaults(def: AgentDef): Record<string, string> {
  return Object.fromEntries(def.fields.map((f) => [f.key, f.kind === 'date' ? '' : String(f.def)]));
}

function validate(def: AgentDef, values: Record<string, string>): { options?: Record<string, unknown>; error?: string } {
  const options: Record<string, unknown> = {};
  for (const f of def.fields) {
    const v = (values[f.key] ?? '').trim();
    if (f.kind === 'date') {
      if (!v) continue;
      if (!/^\d{4}-\d{2}-\d{2}$/.test(v) || Number.isNaN(new Date(`${v}T00:00:00`).getTime())) return { error: `${f.label}: use YYYY-MM-DD.` };
      options[f.key] = v;
    } else if (f.kind === 'int') {
      const n = Number(v);
      if (!Number.isInteger(n) || n < f.min || n > f.max) return { error: `${f.label}: enter a whole number from ${f.min} to ${f.max}.` };
      options[f.key] = n;
    } else {
      options[f.key] = v || f.def;
    }
  }
  return { options };
}

function Options({ def, values, onChange, disabled }: { def: AgentDef; values: Record<string, string>; onChange: (v: Record<string, string>) => void; disabled: boolean }) {
  if (!def.fields.length) return null;
  return (
    <View style={styles.fields}>
      {def.fields.map((f) => (
        <View key={f.key} style={styles.field}>
          <Text style={pageStyles.label}>{f.label}</Text>
          {f.kind === 'choice' ? (
            <View style={pageStyles.chipRow} accessibilityRole="radiogroup">
              {f.choices.map((c) => {
                const active = (values[f.key] || f.def) === c.value;
                return (
                  <Pressable
                    key={c.value}
                    onPress={() => onChange({ ...values, [f.key]: c.value })}
                    disabled={disabled}
                    accessibilityRole="radio"
                    accessibilityState={{ checked: active, disabled }}
                    style={[pageStyles.chip, active && pageStyles.chipActive]}
                  >
                    <Text style={[pageStyles.chipText, active && pageStyles.chipTextActive]}>{c.label}</Text>
                  </Pressable>
                );
              })}
            </View>
          ) : (
            <TextInput
              value={values[f.key] ?? ''}
              onChangeText={(t) => onChange({ ...values, [f.key]: t })}
              placeholder={f.kind === 'date' ? `YYYY-MM-DD · ${f.hint}` : `${f.min}–${f.max}`}
              placeholderTextColor={C.muted}
              keyboardType={f.kind === 'int' ? 'number-pad' : 'numbers-and-punctuation'}
              editable={!disabled}
              style={pageStyles.input}
              accessibilityLabel={f.label}
            />
          )}
        </View>
      ))}
    </View>
  );
}

export function AgentPanel({ lookups, available }: { lookups: Lookups; available: boolean | undefined }) {
  const run = useRunMentorAgent();
  const qc = useQueryClient();
  const [selected, setSelected] = useState<MentorAgent>('daily_plan');
  const [values, setValues] = useState<Record<string, Record<string, string>>>(() => Object.fromEntries(AGENTS.map((a) => [a.id, defaults(a)])));
  const [results, setResults] = useState<Partial<Record<MentorAgent, MiExecution>>>({});
  const [errors, setErrors] = useState<Partial<Record<MentorAgent, string>>>({});

  const def = AGENTS.find((a) => a.id === selected)!;
  const running = run.isPending ? run.variables?.agent : undefined;

  const start = () => {
    const { options, error } = validate(def, values[def.id]);
    if (error) {
      setErrors((e) => ({ ...e, [def.id]: error }));
      return;
    }
    setErrors((e) => ({ ...e, [def.id]: undefined }));
    const agent = def.id;
    run.mutate(
      { agent, options },
      {
        onSuccess: (env) => {
          // Agents may record new proposals: refresh the proposals list.
          void qc.invalidateQueries({ queryKey: ['mentor-ai', 'proposals'] });
          if (env.success && env.data) setResults((r) => ({ ...r, [agent]: env.data }));
          else setErrors((e) => ({ ...e, [agent]: env.error?.message ?? 'The assistant returned no result.' }));
        },
        onError: (err) => setErrors((e) => ({ ...e, [agent]: err.message })),
      },
    );
  };

  const result = results[def.id];

  return (
    <View>
      <View style={styles.grid}>
        {AGENTS.map((a) => {
          const active = a.id === selected;
          return (
            <Pressable
              key={a.id}
              onPress={() => setSelected(a.id)}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              accessibilityLabel={`${a.title}. ${a.description}`}
              style={[styles.agent, active && styles.agentActive]}
            >
              <Text style={[styles.agentIcon, active && { color: '#FFF' }]}>{a.icon}</Text>
              <Text style={[styles.agentTitle, active && { color: '#FFF' }]}>{a.title}</Text>
              {running === a.id ? <Text style={[styles.agentState, active && { color: '#DCE6F2' }]}>Running…</Text> : results[a.id] ? <Text style={[styles.agentState, active && { color: '#DCE6F2' }]}>Result ready</Text> : null}
            </Pressable>
          );
        })}
      </View>

      <Card>
        <Text style={pageStyles.itemTitle}>{def.title}</Text>
        <Text style={pageStyles.muted}>{def.description}</Text>
        <Options def={def} values={values[def.id]} onChange={(v) => setValues((all) => ({ ...all, [def.id]: v }))} disabled={!!running} />
        {available === false ? <InlineNotice tone="warning" text="Mentor AI is reported unavailable; the run may fail." /> : null}
        <Button
          label={running === def.id ? 'Analysing…' : result ? 'Run again' : 'Run analysis'}
          onPress={start}
          loading={running === def.id}
          disabled={!!running}
          style={{ marginTop: 12 }}
          accessibilityLabel={`Run ${def.title}`}
        />
        {running && running !== def.id ? <Text style={[pageStyles.muted, { marginTop: 6 }]}>Another analysis is running ({humanize(running)}).</Text> : null}
        {errors[def.id] ? <InlineNotice tone="danger" text={errors[def.id]!} /> : null}
      </Card>

      {result ? (
        <Card>
          <AgentResult agent={def.id} execution={result} lookups={lookups} />
        </Card>
      ) : running !== def.id ? (
        <EmptyState title="No result yet" message="Run the analysis to see results computed from your records." />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  agent: { flexGrow: 1, flexBasis: '22%', minWidth: 130, backgroundColor: C.surface, borderWidth: 1, borderColor: C.border, borderRadius: 14, padding: 12 },
  agentActive: { backgroundColor: C.navy, borderColor: C.navy },
  agentIcon: { color: C.tealDark, fontSize: 18, fontWeight: '800' },
  agentTitle: { color: C.navy, fontSize: 14, fontWeight: '700', marginTop: 4 },
  agentState: { color: C.secondaryText, fontSize: 11, marginTop: 2 },
  fields: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  field: { flexGrow: 1, flexBasis: 160 },
});
