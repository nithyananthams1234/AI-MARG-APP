/**
 * Suggested actions (Mentor Intelligence proposals): pending list with
 * approve / reject, outcome of execution, WhatsApp hand-off for approved
 * teacher messages, and recent history.
 */
import * as Linking from 'expo-linking';
import { useState } from 'react';
import { StyleSheet, Text, TextInput, View } from 'react-native';

import { pageStyles } from '@/components/reports/page-chrome';
import { Button, Card, EmptyState, InlineNotice, QueryView, StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import { useDecideProposal, useProposalExternalResult, useProposals } from '@/hooks/api';
import type { MiProposal } from '@/lib/api/services';
import { confirmAction, notify } from '@/lib/dialogs';
import { formatDateTime, humanize, relativeTime } from '@/lib/format';

import { obj, str } from './facts';
import type { Lookups } from './lookups';

const ACTION_TITLES: Record<string, string> = {
  reschedule_visit: 'Reschedule a visit',
  schedule_visit: 'Schedule a visit',
  update_task_due_date: 'Change a task due date',
  send_teacher_message: 'Send a message to a teacher',
};

function PayloadSummary({ p, L }: { p: MiProposal; L: Lookups }) {
  const d = obj(p.payload);
  switch (p.action_type) {
    case 'reschedule_visit': {
      const v = L.visit(str(d.visit_ref) ?? p.target_ref);
      return (
        <Text style={styles.body}>
          {v ? (L.schoolName(v.school_id) ?? 'School visit') : 'Visit'}: {formatDateTime(str(d.previous_start))} → <Text style={styles.strong}>{formatDateTime(str(d.new_start))}</Text>
          {str(d.new_end) ? ` – ${formatDateTime(str(d.new_end))}` : ''}
        </Text>
      );
    }
    case 'schedule_visit':
      return (
        <Text style={styles.body}>
          <Text style={styles.strong}>{L.schoolName(str(d.school_ref) ?? p.target_ref) ?? 'School'}</Text>: {formatDateTime(str(d.start))}
          {str(d.end) ? ` – ${formatDateTime(str(d.end))}` : ''}
          {str(d.purpose) ? `\n${str(d.purpose)}` : ''}
        </Text>
      );
    case 'update_task_due_date':
      return (
        <Text style={styles.body}>
          <Text style={styles.strong}>{L.taskTitle(str(d.task_ref) ?? p.target_ref) ?? 'Task'}</Text>: new due date {formatDateTime(str(d.due_at))}
        </Text>
      );
    case 'send_teacher_message':
      return (
        <View>
          <Text style={styles.body}>
            To <Text style={styles.strong}>{L.teacher(str(d.teacher_ref) ?? p.target_ref)?.full_name ?? 'teacher'}</Text> · {humanize(str(d.purpose))} ·{' '}
            {str(d.language) === 'ta' ? 'Tamil' : 'English'}
          </Text>
          {str(d.body) ? (
            <View style={styles.draft}>
              <Text style={styles.draftText} selectable>
                {str(d.body)}
              </Text>
            </View>
          ) : null}
        </View>
      );
    default:
      return <Text style={pageStyles.muted}>{humanize(p.target_type)} {p.target_ref}</Text>;
  }
}

function ExecutionOutcome({ p }: { p: MiProposal }) {
  const r = obj(p.execution_result);
  if (p.status === 'executed') {
    return (
      <InlineNotice
        tone="success"
        text={p.requires_external_execution ? `Reported as sent${str(r.detail) ? `: ${str(r.detail)}` : '.'}` : 'Approved and applied to your records.'}
      />
    );
  }
  if (p.status === 'execution_failed') {
    return <InlineNotice tone="danger" text={`Approved, but it could not be applied: ${str(r.error) ?? str(r.detail) ?? 'no details were returned'}`} />;
  }
  if (p.status === 'rejected') return <InlineNotice tone="info" text="Rejected. No change was made." />;
  if (p.status === 'expired') return <InlineNotice tone="warning" text="Expired before a decision. No change was made." />;
  return null;
}

/** For an approved teacher message: open WhatsApp, then report the outcome. */
function SendMessage({ p, L }: { p: MiProposal; L: Lookups }) {
  const d = obj(p.payload);
  const teacher = L.teacher(str(d.teacher_ref) ?? p.target_ref);
  const [phoneInput, setPhone] = useState<string | undefined>();
  const phone = phoneInput ?? teacher?.phone ?? '';
  const [detail, setDetail] = useState('');
  const [opened, setOpened] = useState(false);
  const report = useProposalExternalResult();
  const digits = phone.replace(/\D/g, '');
  const valid = digits.length >= 8 && digits.length <= 15;
  const body = str(d.body) ?? '';

  const open = async () => {
    try {
      await Linking.openURL(`https://wa.me/${digits}?text=${encodeURIComponent(body)}`);
      setOpened(true);
    } catch {
      notify('WhatsApp unavailable', 'Could not open WhatsApp. Check the phone number and try again.');
    }
  };

  const send = (success: boolean) =>
    confirmAction(
      success ? 'Mark as sent?' : 'Mark as not sent?',
      success ? 'Confirm that you sent this message to the teacher.' : 'Record that the message could not be sent.',
      () => report.mutate({ id: p.proposal_id, success, detail: detail.trim() || undefined }),
      success ? 'Mark as sent' : 'Mark as not sent',
    );

  return (
    <View style={styles.send}>
      <Text style={styles.sendTitle}>Approved — send it yourself</Text>
      <Text style={pageStyles.muted}>Open WhatsApp with this text, send it, then record the outcome here.</Text>
      <Text style={pageStyles.label}>Teacher phone (with country code)</Text>
      <TextInput
        value={phone}
        onChangeText={setPhone}
        keyboardType="phone-pad"
        placeholder="e.g. +91 98765 43210"
        placeholderTextColor={C.muted}
        style={pageStyles.input}
        accessibilityLabel="Teacher phone number"
      />
      {phone.length > 0 && !valid ? <Text style={pageStyles.error}>Enter 8 to 15 digits including the country code.</Text> : null}
      <Button label="Open in WhatsApp" variant="secondary" onPress={() => void open()} disabled={!valid || !body} style={{ marginTop: 10 }} />
      <Text style={pageStyles.label}>Note (optional)</Text>
      <TextInput
        value={detail}
        onChangeText={setDetail}
        maxLength={300}
        placeholder="e.g. Sent on WhatsApp"
        placeholderTextColor={C.muted}
        style={pageStyles.input}
        accessibilityLabel="Optional note about delivery"
      />
      <View style={styles.actions}>
        <Button label="I sent it" onPress={() => send(true)} loading={report.isPending && report.variables?.success === true} disabled={report.isPending} style={{ flex: 1 }} />
        <Button label="Could not send" variant="danger" onPress={() => send(false)} loading={report.isPending && report.variables?.success === false} disabled={report.isPending} style={{ flex: 1 }} />
      </View>
      {!opened ? <Text style={[pageStyles.muted, { marginTop: 6 }]}>This app cannot confirm delivery; only you can.</Text> : null}
      {report.error ? <InlineNotice tone="danger" text={report.error.message} /> : null}
    </View>
  );
}

function ProposalCard({ p, L, onDecided }: { p: MiProposal; L: Lookups; onDecided: (p: MiProposal) => void }) {
  const decide = useDecideProposal();
  const [note, setNote] = useState('');
  const pending = p.status === 'pending';
  const needsSend = p.status === 'approved' && p.requires_external_execution;

  const act = (approve: boolean) =>
    confirmAction(
      approve ? 'Approve this action?' : 'Reject this action?',
      approve
        ? p.requires_external_execution
          ? 'The message will be marked approved. You will send it yourself afterwards.'
          : 'The change will be applied to your records immediately.'
        : 'The suggestion will be dismissed. No change will be made.',
      () =>
        decide.mutate(
          { id: p.proposal_id, approve, note: note.trim() || undefined },
          { onSuccess: (env) => env.data && onDecided(env.data) },
        ),
      approve ? 'Approve' : 'Reject',
    );

  return (
    <Card>
      <View style={pageStyles.rowBetween}>
        <Text style={[pageStyles.itemTitle, { flex: 1 }]}>{ACTION_TITLES[p.action_type] ?? humanize(p.action_type)}</Text>
        <StatusBadge status={p.status} />
      </View>
      <Text style={pageStyles.muted}>
        Suggested by {humanize(p.agent_id)} · {relativeTime(p.created_at)}
        {pending ? ` · expires ${formatDateTime(p.expires_at)}` : ''}
      </Text>
      <View style={{ marginTop: 8 }}>
        <PayloadSummary p={p} L={L} />
      </View>
      {p.rationale ? (
        <Text style={[pageStyles.muted, { marginTop: 6 }]}>
          <Text style={{ fontWeight: '700' }}>Why: </Text>
          {p.rationale}
        </Text>
      ) : null}

      {pending ? (
        <>
          <TextInput
            value={note}
            onChangeText={setNote}
            maxLength={500}
            editable={!decide.isPending}
            placeholder="Note (optional)"
            placeholderTextColor={C.muted}
            style={[pageStyles.input, { marginTop: 10 }]}
            accessibilityLabel="Optional note for your decision"
          />
          <View style={styles.actions}>
            <Button label="Approve" onPress={() => act(true)} loading={decide.isPending && decide.variables?.approve === true} disabled={decide.isPending} style={{ flex: 1 }} />
            <Button label="Reject" variant="danger" onPress={() => act(false)} loading={decide.isPending && decide.variables?.approve === false} disabled={decide.isPending} style={{ flex: 1 }} />
          </View>
          {decide.error ? <InlineNotice tone="danger" text={decide.error.message} /> : null}
        </>
      ) : null}

      {needsSend ? <SendMessage p={p} L={L} /> : <ExecutionOutcome p={p} />}
    </Card>
  );
}

export function Proposals({ lookups }: { lookups: Lookups }) {
  const pending = useProposals('pending');
  const all = useProposals();
  const [decided, setDecided] = useState<MiProposal[]>([]);

  const decidedIds = new Set(decided.map((d) => d.proposal_id));
  const history = (all.data?.data ?? [])
    .filter((p) => p.status !== 'pending' && !decidedIds.has(p.proposal_id))
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 15);
  // Latest server state for proposals decided in this session (e.g. after reporting a send).
  const latest = (p: MiProposal) => all.data?.data.find((x) => x.proposal_id === p.proposal_id) ?? p;

  return (
    <View>
      {decided.map((p) => (
        <ProposalCard key={p.proposal_id} p={latest(p)} L={lookups} onDecided={() => undefined} />
      ))}

      <QueryView query={pending} loadingLabel="Loading suggested actions…">
        {(env) => {
          const list = env.data.filter((p) => !decidedIds.has(p.proposal_id));
          return list.length === 0 ? (
            <EmptyState title="No actions waiting for approval" message="Schedule checks, visit planning and message drafts can suggest actions here." />
          ) : (
            <>
              {list.map((p) => (
                <ProposalCard key={p.proposal_id} p={p} L={lookups} onDecided={(d) => setDecided((x) => [d, ...x.filter((y) => y.proposal_id !== d.proposal_id)])} />
              ))}
            </>
          );
        }}
      </QueryView>

      <Text style={styles.historyTitle} accessibilityRole="header">
        Recent decisions
      </Text>
      <QueryView query={all} loadingLabel="Loading history…">
        {() =>
          history.length === 0 ? (
            <Text style={pageStyles.muted}>No decided actions yet.</Text>
          ) : (
            <>
              {history.map((p) => (
                <ProposalCard key={p.proposal_id} p={p} L={lookups} onDecided={() => undefined} />
              ))}
            </>
          )
        }
      </QueryView>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { color: C.text, fontSize: 14, lineHeight: 20 },
  strong: { fontWeight: '700', color: C.navy },
  draft: { backgroundColor: '#F2FBFA', borderRadius: 12, borderWidth: 1, borderColor: '#BFE7E3', padding: 12, marginTop: 8 },
  draftText: { color: C.text, fontSize: 14, lineHeight: 21 },
  actions: { flexDirection: 'row', gap: 10, marginTop: 10 },
  send: { marginTop: 12, borderTopWidth: 1, borderTopColor: C.border, paddingTop: 10 },
  sendTitle: { color: C.navy, fontSize: 14, fontWeight: '800' },
  historyTitle: { color: C.navy, fontSize: 15, fontWeight: '800', marginTop: 14, marginBottom: 8 },
});
