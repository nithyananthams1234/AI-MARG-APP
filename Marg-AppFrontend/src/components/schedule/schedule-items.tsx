import { Pressable, Text, View } from 'react-native';

import { StatusBadge } from '@/components/ui/states';
import type { MentorTaskResponse, ScheduleResponse, SchoolVisitResponse } from '@/lib/api/generated';
import { formatDateTime, humanize, isOverdue } from '@/lib/format';

import { schStyles as styles } from './schedule-styles';
import { timeLabel } from './schedule-utils';

const VISIT_COLORS: Record<string, string> = {
  planned: '#2475C7',
  in_progress: '#0D9C91',
  completed: '#16A477',
  cancelled: '#8B929D',
};

export function VisitAgendaItem({ visit, schoolName, pendingProposals, onPropose }: {
  visit: SchoolVisitResponse;
  schoolName: string;
  pendingProposals: number;
  onPropose: () => void;
}) {
  const color = VISIT_COLORS[visit.status] ?? '#2475C7';
  return (
    <View style={styles.eventCard} accessibilityLabel={`Visit to ${schoolName} at ${timeLabel(visit.scheduled_at)}, ${humanize(visit.status)}`}>
      <View style={styles.eventTop}>
        <View style={[styles.typeIndicator, { backgroundColor: color }]} />
        <View style={styles.eventMain}>
          <Text style={styles.eventTitle}>{schoolName}</Text>
          <Text style={styles.schoolName}>{visit.notes || 'School visit'}</Text>
        </View>
        <StatusBadge status={visit.status} />
      </View>
      <View style={styles.eventDetails}>
        <Text style={styles.detailText}>◷  {timeLabel(visit.scheduled_at)}</Text>
        {pendingProposals > 0 ? (
          <Text style={styles.detailText}>↻  {pendingProposals} time proposal{pendingProposals === 1 ? '' : 's'} awaiting decision</Text>
        ) : null}
      </View>
      {visit.status === 'planned' ? (
        <View style={styles.eventBottom}>
          <View style={[styles.typeBadge, { backgroundColor: `${color}15` }]}>
            <Text style={[styles.typeBadgeText, { color }]}>School visit</Text>
          </View>
          <Pressable style={styles.completeButton} onPress={onPropose} accessibilityRole="button" accessibilityLabel={`Propose a new time for the visit to ${schoolName}`}>
            <Text style={styles.completeButtonText}>Propose time</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

export function ProposalCard({ proposal, schoolName, busy, onDecide }: {
  proposal: ScheduleResponse;
  schoolName: string;
  busy: boolean;
  onDecide: (status: 'accepted' | 'rejected') => void;
}) {
  return (
    <View style={styles.eventCard}>
      <View style={styles.eventTop}>
        <View style={[styles.typeIndicator, { backgroundColor: '#8B5CC7' }]} />
        <View style={styles.eventMain}>
          <Text style={styles.eventTitle}>{schoolName}</Text>
          <Text style={styles.schoolName}>
            {formatDateTime(proposal.proposed_start_at)} – {timeLabel(proposal.proposed_end_at)}
          </Text>
        </View>
        <StatusBadge status={proposal.status} />
      </View>
      <View style={styles.eventDetails}>
        {proposal.estimated_travel_minutes != null ? (
          <Text style={styles.detailText}>⌖  ~{proposal.estimated_travel_minutes} min travel</Text>
        ) : null}
        {proposal.notes ? <Text style={styles.detailText}>✎  {proposal.notes}</Text> : null}
      </View>
      {proposal.status === 'proposed' ? (
        <View style={[styles.eventBottom, styles.actionRow, { justifyContent: 'flex-end' }]}>
          <Pressable
            style={[styles.dangerButton, busy && styles.disabled]}
            onPress={() => onDecide('rejected')}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel="Reject proposal"
            accessibilityState={{ disabled: busy }}
          >
            <Text style={styles.dangerButtonText}>Reject</Text>
          </Pressable>
          <Pressable
            style={[styles.completeButton, busy && styles.disabled]}
            onPress={() => onDecide('accepted')}
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel="Accept proposal and move the visit to this time"
            accessibilityState={{ disabled: busy }}
          >
            <Text style={styles.completeButtonText}>Accept</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

export function TaskDueItem({ task, schoolName }: { task: MentorTaskResponse; schoolName?: string }) {
  const overdue = isOverdue(task.due_at);
  return (
    <View style={styles.eventCard} accessibilityLabel={`Task ${task.title} due ${formatDateTime(task.due_at)}`}>
      <View style={styles.eventTop}>
        <View style={[styles.typeIndicator, { backgroundColor: '#D58A28', height: 32 }]} />
        <View style={styles.eventMain}>
          <Text style={styles.eventTitle}>{task.title}</Text>
          <Text style={[styles.schoolName, overdue && { color: '#C13F35', fontWeight: '700' }]}>
            {overdue ? 'Overdue · ' : 'Due '}{formatDateTime(task.due_at)}{schoolName ? ` · ${schoolName}` : ''}
          </Text>
        </View>
        <StatusBadge status={task.priority} />
      </View>
    </View>
  );
}
