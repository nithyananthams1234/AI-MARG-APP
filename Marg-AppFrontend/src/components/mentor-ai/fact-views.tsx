/**
 * Per-agent rendering of the deterministic (computed) `facts` returned by
 * Mentor Intelligence. Field names follow the live backend responses.
 */
import type { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { Bar, pageStyles } from '@/components/reports/page-chrome';
import { StatusBadge } from '@/components/ui/states';
import { MargColors as C } from '@/constants/theme';
import type { MentorAgent } from '@/lib/api/services';
import { formatDate, formatDateTime, humanize } from '@/lib/format';

import { arr, hhmm, minutes, num, obj, str, strs, type Obj } from './facts';
import type { Lookups } from './lookups';

// ------------------------------------------------------------------ primitives
export function Sub({ title, count }: { title: string; count?: number }) {
  return (
    <Text style={styles.sub} accessibilityRole="header">
      {title}
      {count != null ? ` (${count})` : ''}
    </Text>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function Stats({ children }: { children: ReactNode }) {
  return <View style={styles.stats}>{children}</View>;
}

function Item({ title, meta, right, children }: { title: string; meta?: string; right?: ReactNode; children?: ReactNode }) {
  return (
    <View style={styles.item}>
      <View style={pageStyles.rowBetween}>
        <Text style={[styles.itemTitle, { flex: 1 }]}>{title}</Text>
        {right}
      </View>
      {meta ? <Text style={pageStyles.muted}>{meta}</Text> : null}
      {children}
    </View>
  );
}

function Flags({ flags }: { flags: string[] }) {
  if (!flags.length) return null;
  return (
    <View style={[pageStyles.chipRow, { marginTop: 4 }]}>
      {flags.map((f) => (
        <StatusBadge key={f} status={/overdue|missing|conflict/.test(f) ? 'overdue' : 'pending'} label={humanize(f)} />
      ))}
    </View>
  );
}

function None({ text }: { text: string }) {
  return <Text style={pageStyles.muted}>{text}</Text>;
}

function Conflicts({ list }: { list: Obj[] }) {
  return (
    <>
      <Sub title="Conflicts" count={list.length} />
      {list.length === 0 ? (
        <None text="No conflicts found." />
      ) : (
        list.map((c, i) => (
          <Item key={i} title={humanize(str(c.type))} right={<StatusBadge status={str(c.severity) ?? 'medium'} />}>
            <Text style={styles.body}>{str(c.detail)}</Text>
          </Item>
        ))
      )}
    </>
  );
}

function Workload({ w }: { w: Obj }) {
  const perDay = arr(w.per_day);
  const index = num(w.workload_index);
  const thresholds = obj(w.thresholds);
  return (
    <>
      <Stats>
        <Stat label={`Workload index${w.index_is_lower_bound ? ' (at least)' : ''}`} value={index != null ? index.toFixed(1) : '—'} />
        <Stat label="Status" value={humanize(str(w.status)) || '—'} />
        <Stat label="Committed / available" value={`${minutes(num(w.estimated_workload_minutes))} / ${minutes(num(w.available_minutes))}`} />
      </Stats>
      <Text style={pageStyles.muted}>
        Index = estimated work ÷ available working time × 100. High from {num(thresholds.high) ?? '—'}, overloaded from{' '}
        {num(thresholds.overloaded) ?? '—'}. {str(w.metric_note) ?? ''}
      </Text>
      <Sub title="Per day" />
      {perDay.map((d) => {
        const avail = num(d.available_minutes) ?? 0;
        const committed = num(d.committed_minutes) ?? 0;
        const idx = num(d.index);
        return (
          <View key={str(d.date)} style={styles.dayRow} accessible accessibilityLabel={`${formatDate(str(d.date))}: ${minutes(committed)} committed of ${minutes(avail)}. ${humanize(str(d.status))}`}>
            <Text style={styles.dayLabel}>{formatDate(str(d.date))}</Text>
            {d.working_day ? (
              <Bar value={committed} max={Math.max(avail, committed)} color={idx != null && idx >= (num(thresholds.high) ?? 80) ? C.danger : C.teal} />
            ) : (
              <Text style={[pageStyles.muted, { flex: 1 }]}>Non-working day{committed ? ` · ${minutes(committed)} scheduled` : ''}</Text>
            )}
            <Text style={styles.dayValue}>{idx != null ? idx.toFixed(0) : '—'}</Text>
          </View>
        );
      })}
      {strs(w.overloaded_days).length ? <Text style={pageStyles.error}>Overloaded days: {strs(w.overloaded_days).map((d) => formatDate(d)).join(', ')}</Text> : null}
    </>
  );
}

// ------------------------------------------------------------------ agents
function DailyPlan({ f, L }: { f: Obj; L: Lookups }) {
  const cap = obj(f.capacity_minutes);
  const timeline = arr(f.timeline);
  const cannot = arr(f.cannot_fit_or_not_schedulable);
  const fus = arr(f.followups_needing_attention);
  return (
    <>
      <Text style={styles.body}>
        Plan for {formatDate(str(f.date))} ({hhmm(str(obj(f.working_window).start))}–{hhmm(str(obj(f.working_window).end))}, {str(f.timezone)})
      </Text>
      <Stats>
        <Stat label="Available" value={minutes(num(cap.available_minutes))} />
        <Stat label="Fixed commitments" value={minutes(num(cap.scheduled_minutes))} />
        <Stat label="Tasks placed" value={minutes(num(cap.placed_minutes))} />
        <Stat label="Free" value={minutes(num(cap.free_minutes_remaining))} />
      </Stats>
      <Sub title="Time blocks" count={timeline.length} />
      {timeline.length === 0 ? <None text="Nothing scheduled for this day." /> : null}
      {timeline.map((b, i) => (
        <View key={`${str(b.ref)}-${i}`} style={styles.block}>
          <Text style={styles.blockTime}>
            {hhmm(str(b.start))}
            {'\n'}
            {hhmm(str(b.end))}
          </Text>
          <View style={{ flex: 1 }}>
            <View style={pageStyles.rowBetween}>
              <Text style={[styles.itemTitle, { flex: 1 }]}>{str(b.title)}</Text>
              {str(b.priority) ? <StatusBadge status={str(b.priority)!} /> : <StatusBadge status="planned" label={humanize(str(b.kind))} />}
            </View>
            <Text style={pageStyles.muted}>{str(b.reason)}</Text>
          </View>
        </View>
      ))}
      {cannot.length ? (
        <>
          <Sub title="Could not fit today" count={cannot.length} />
          {cannot.map((c, i) => (
            <Item key={i} title={str(c.title) ?? 'Item'} meta={str(c.reason)} right={str(c.priority) ? <StatusBadge status={str(c.priority)!} /> : undefined} />
          ))}
        </>
      ) : null}
      {arr(f.conflicts).length ? <Conflicts list={arr(f.conflicts)} /> : null}
      {arr(f.critical_tasks).length ? (
        <>
          <Sub title="Critical tasks" count={arr(f.critical_tasks).length} />
          {arr(f.critical_tasks).map((t, i) => (
            <Item key={i} title={str(t.title) ?? L.taskTitle(str(t.task_ref)) ?? 'Task'} />
          ))}
        </>
      ) : null}
      <Sub title="Follow-ups needing attention" count={fus.length} />
      {fus.length === 0 ? <None text="No follow-ups need attention." /> : null}
      {fus.map((x) => (
        <Item key={str(x.followup_ref)} title={L.followUp(str(x.followup_ref))?.description ?? str(x.action_plan_title) ?? 'Follow-up'} meta={str(x.action_plan_title)}>
          <Flags flags={strs(x.flags)} />
        </Item>
      ))}
      {str(f.note) ? <Text style={pageStyles.muted}>{str(f.note)}</Text> : null}
    </>
  );
}

function WeeklyPlan({ f, L }: { f: Obj; L: Lookups }) {
  const week = obj(f.week);
  const visitsByDay = obj(f.visits_by_day);
  const prev = obj(f.previous_week);
  const deadlines = arr(f.deadlines_this_week);
  const overdue = arr(f.already_overdue);
  const fus = arr(f.followups_due_or_overdue);
  const unplanned = arr(f.schools_needing_visit_unplanned);
  return (
    <>
      <Text style={styles.body}>
        Week {formatDate(str(week.start_date))} – {formatDate(str(week.end_date))}
      </Text>
      <Workload w={obj(f.workload)} />
      <Sub title="Visits by day" />
      {Object.keys(visitsByDay).length === 0 ? <None text="No visits this week." /> : null}
      {Object.entries(visitsByDay).map(([day, list]) => (
        <Item key={day} title={formatDate(day)}>
          {arr(list).map((v, i) => (
            <Text key={i} style={styles.body}>
              {hhmm(str(v.start))} · {L.schoolName(str(v.school_ref)) ?? 'School visit'}
            </Text>
          ))}
        </Item>
      ))}
      <Sub title="Deadlines this week" count={deadlines.length} />
      {deadlines.length === 0 ? <None text="No task deadlines this week." /> : null}
      {deadlines.map((d) => (
        <Item key={str(d.task_ref)} title={str(d.title) ?? 'Task'} meta={`Due ${formatDateTime(str(d.due_at))}`} />
      ))}
      {overdue.length ? (
        <>
          <Sub title="Already overdue" count={overdue.length} />
          {overdue.map((d) => (
            <Item key={str(d.task_ref)} title={str(d.title) ?? 'Task'} right={<StatusBadge status="overdue" />} />
          ))}
        </>
      ) : null}
      <Sub title="Follow-ups due or overdue" count={fus.length} />
      {fus.map((x) => (
        <Item
          key={str(x.followup_ref)}
          title={L.followUp(str(x.followup_ref))?.description ?? 'Follow-up'}
          meta={`Due ${formatDateTime(str(x.due_at))}`}
          right={<StatusBadge status={str(x.status) ?? 'pending'} />}
        />
      ))}
      {unplanned.length ? (
        <>
          <Sub title="Schools needing a visit (none planned)" count={unplanned.length} />
          {unplanned.map((s, i) => (
            <Item key={i} title={str(s.school_name) ?? L.schoolName(str(s.school_ref)) ?? 'School'} />
          ))}
        </>
      ) : null}
      <Conflicts list={arr(f.conflicts)} />
      <Sub title="Previous week" />
      <Stats>
        <Stat label="Tasks completed" value={num(prev.tasks_completed) ?? 0} />
        <Stat label="Visits completed" value={num(prev.visits_completed) ?? 0} />
        <Stat label="Follow-ups verified" value={num(prev.followups_verified) ?? 0} />
      </Stats>
    </>
  );
}

function TaskPrioritisation({ f, L }: { f: Obj; L: Lookups }) {
  const s = obj(f.summary);
  const by = obj(s.by_priority);
  const tasks = arr(f.tasks);
  return (
    <>
      <Stats>
        <Stat label="Open tasks" value={num(s.open_tasks) ?? 0} />
        <Stat label="Overdue" value={num(s.overdue) ?? 0} />
        <Stat label="Critical / high" value={`${num(by.critical) ?? 0} / ${num(by.high) ?? 0}`} />
        <Stat label="Medium / low" value={`${num(by.medium) ?? 0} / ${num(by.low) ?? 0}`} />
      </Stats>
      {str(f.formula) ? <Text style={pageStyles.muted}>Score = {str(f.formula)}</Text> : null}
      <Sub title="Ranked tasks" count={tasks.length} />
      {tasks.length === 0 ? <None text="No open tasks." /> : null}
      {tasks.map((t) => {
        const p = obj(t.priority);
        const score = num(p.score);
        const missing = strs(p.missing_factors);
        return (
          <View key={str(t.task_ref)} style={styles.block}>
            <Text style={styles.rank}>#{num(t.rank)}</Text>
            <View style={{ flex: 1 }}>
              <View style={pageStyles.rowBetween}>
                <Text style={[styles.itemTitle, { flex: 1 }]}>{str(t.title) ?? L.taskTitle(str(t.task_ref))}</Text>
                <StatusBadge status={str(p.priority) ?? 'medium'} label={`${humanize(str(p.priority))}${score != null ? ` · ${score.toFixed(1)}` : ''}`} />
              </View>
              <Text style={[pageStyles.muted, t.overdue ? { color: C.danger, fontWeight: '700' } : null]}>
                {str(t.due_at) ? `${t.overdue ? 'Overdue · due ' : 'Due '}${formatDateTime(str(t.due_at))}` : 'No due date'}
                {str(t.category) ? ` · ${humanize(str(t.category))}` : ''}
                {L.schoolName(str(t.school_ref)) ? ` · ${L.schoolName(str(t.school_ref))}` : ''}
              </Text>
              {str(t.next_action) ? <Text style={styles.body}>Next: {str(t.next_action)}</Text> : null}
              {missing.length ? <Text style={pageStyles.muted}>Missing inputs: {missing.map(humanize).join(', ')}</Text> : null}
              {arr(t.blocked_by).length || strs(t.blocked_by).length ? <Text style={pageStyles.error}>Blocked by other tasks</Text> : null}
            </View>
          </View>
        );
      })}
    </>
  );
}

function WorkloadAnalysis({ f, L }: { f: Obj; L: Lookups }) {
  const after = strs(f.tasks_due_after_window);
  const unassigned = arr(f.unassigned_work);
  const candidates = arr(f.adjustment_candidates);
  return (
    <>
      <Workload w={obj(f.workload)} />
      {unassigned.length ? (
        <>
          <Sub title="Work without a date" count={unassigned.length} />
          {unassigned.map((u, i) => (
            <Item key={i} title={str(u.title) ?? L.taskTitle(str(u.task_ref)) ?? 'Item'} />
          ))}
        </>
      ) : null}
      {candidates.length ? (
        <>
          <Sub title="Could be moved to reduce load" count={candidates.length} />
          {candidates.map((c, i) => (
            <Item key={i} title={str(c.title) ?? L.taskTitle(str(c.task_ref)) ?? 'Item'} meta={str(c.reason)} />
          ))}
        </>
      ) : null}
      {after.length ? <Text style={pageStyles.muted}>{after.length} task(s) are due after this window and were not counted.</Text> : null}
    </>
  );
}

function ScheduleAnalysis({ f }: { f: Obj }) {
  const win = obj(f.window);
  const free = arr(f.free_time);
  const entries = arr(f.entries);
  return (
    <>
      <Text style={styles.body}>
        {entries.length} calendar entr{entries.length === 1 ? 'y' : 'ies'} from {formatDate(str(win.start_date))} over {num(win.days) ?? '—'} days
      </Text>
      <Conflicts list={arr(f.conflicts)} />
      {arr(f.conflicts_without_proposal).length ? (
        <Text style={pageStyles.muted}>{arr(f.conflicts_without_proposal).length} conflict(s) have no verified free slot to propose.</Text>
      ) : null}
      <Sub title="Free time" />
      {free.map((d) => (
        <Item
          key={str(d.date)}
          title={formatDate(str(d.date))}
          meta={
            arr(d.slots).length
              ? arr(d.slots)
                  .map((s) => `${hhmm(str(s.start))}–${hhmm(str(s.end))}`)
                  .join(', ')
              : 'No free slots'
          }
          right={<Text style={styles.dayValue}>{minutes(num(d.free_minutes))}</Text>}
        />
      ))}
    </>
  );
}

function VisitPlanning({ f, L }: { f: Obj; L: Lookups }) {
  const recs = arr(f.recommended_visits);
  const ranked = arr(f.all_schools_ranked);
  return (
    <>
      {str(f.score_method) ? <Text style={pageStyles.muted}>Attention score = {str(f.score_method)}</Text> : null}
      <Sub title="Suggested visits" count={recs.length} />
      {recs.length === 0 ? <None text="No visit suggestions for this window." /> : null}
      {recs.map((r) => {
        const a = obj(r.attention);
        const brief = obj(r.pre_visit_brief);
        const slot = obj(r.suggested_slot);
        const areas = strs(brief.latest_observation_support_areas);
        return (
          <Item
            key={str(r.school_ref)}
            title={str(r.school_name) ?? L.schoolName(str(r.school_ref)) ?? 'School'}
            right={<StatusBadge status="planned" label={`Score ${num(a.attention_score)?.toFixed(1) ?? '—'}`} />}
          >
            <Text style={pageStyles.muted}>
              {num(a.days_since_last_visit) != null ? `${num(a.days_since_last_visit)} days since last visit` : 'No completed visit recorded'} ·{' '}
              {num(a.overdue_followups) ?? 0} overdue follow-ups · {num(a.open_action_plans) ?? 0} open plans · {num(a.open_tasks) ?? 0} open tasks
            </Text>
            {str(slot.start) ? (
              <Text style={styles.body}>
                Suggested slot: {formatDateTime(str(slot.start))}
                {str(slot.end) ? ` – ${hhmm(str(slot.end))}` : ''}
              </Text>
            ) : null}
            {str(r.slot_note) ? <Text style={pageStyles.muted}>{str(r.slot_note)}</Text> : null}
            {areas.length ? <Text style={styles.body}>Support areas from latest observation: {areas.join(', ')}</Text> : null}
            <Flags flags={strs(a.flags)} />
          </Item>
        );
      })}
      {ranked.length ? (
        <>
          <Sub title="All schools by attention score" />
          {ranked.map((s) => (
            <View key={str(s.school_ref)} style={styles.dayRow}>
              <Text style={[styles.body, { flex: 2 }]} numberOfLines={1}>
                {str(s.school_name)}
              </Text>
              <Bar value={num(s.attention_score) ?? 0} max={100} />
              <Text style={styles.dayValue}>
                {num(s.attention_score)?.toFixed(1) ?? '—'}
                {s.score_complete === false ? '*' : ''}
              </Text>
            </View>
          ))}
          {ranked.some((s) => s.score_complete === false) ? <Text style={pageStyles.muted}>* Score incomplete because some data is missing.</Text> : null}
        </>
      ) : null}
    </>
  );
}

function FollowupAnalysis({ f, L }: { f: Obj; L: Lookups }) {
  const c = obj(f.counts);
  const items = arr(f.items).filter((i) => str(i.category) !== 'resolved');
  const reminders = arr(f.verification_reminders);
  return (
    <>
      <Stats>
        <Stat label="Total" value={num(c.total) ?? 0} />
        <Stat label="Overdue" value={num(c.overdue) ?? 0} />
        <Stat label="Awaiting teacher" value={num(c.awaiting_teacher_response) ?? 0} />
        <Stat label="Awaiting your verification" value={num(c.awaiting_mentor_verification) ?? 0} />
      </Stats>
      <Sub title="Open follow-ups" count={items.length} />
      {items.length === 0 ? <None text="No open follow-ups." /> : null}
      {items.map((i) => {
        const progress = obj(i.progress);
        const reported = obj(progress.teacher_reported);
        return (
          <Item
            key={str(i.followup_ref)}
            title={L.followUp(str(i.followup_ref))?.description ?? str(i.action_plan_title) ?? 'Follow-up'}
            meta={[str(i.action_plan_title), L.teacher(str(i.teacher_ref))?.full_name, L.schoolName(str(i.school_ref)), str(i.due_at) ? `due ${formatDateTime(str(i.due_at))}` : null]
              .filter(Boolean)
              .join(' · ')}
            right={<StatusBadge status={str(i.status) ?? 'pending'} />}
          >
            {str(reported.text) ? (
              <Text style={styles.body}>
                “{str(reported.text)}” <Text style={pageStyles.muted}>({str(reported.label)})</Text>
              </Text>
            ) : null}
            <Flags flags={strs(i.flags)} />
          </Item>
        );
      })}
      {reminders.length ? (
        <>
          <Sub title="Verification reminders" count={reminders.length} />
          {reminders.map((r) => (
            <Item key={str(r.followup_ref)} title={L.followUp(str(r.followup_ref))?.description ?? str(r.reminder) ?? 'Reminder'} meta={str(r.basis)} />
          ))}
        </>
      ) : null}
      {str(f.rule) ? <Text style={pageStyles.muted}>{str(f.rule)}</Text> : null}
    </>
  );
}

function Report({ f }: { f: Obj }) {
  const r = obj(f.records);
  const completed = arr(r.tasks_completed);
  const overdue = arr(r.tasks_overdue);
  const visits = arr(r.visits_completed);
  const upcoming = arr(r.visits_planned_upcoming);
  const byStatus = obj(r.followups_by_status);
  return (
    <>
      <Text style={styles.body}>
        {humanize(str(f.period))} report · {formatDate(str(f.start_date))} – {formatDate(str(f.end_date))}
      </Text>
      <Stats>
        <Stat label="Tasks completed" value={completed.length} />
        <Stat label="Tasks open" value={num(r.tasks_open) ?? 0} />
        <Stat label="Visits completed" value={visits.length} />
        <Stat label="Observations" value={num(r.observations_recorded) ?? 0} />
        <Stat label="Teacher responses" value={num(r.teacher_responses_in_period) ?? 0} />
        <Stat label="Follow-ups verified" value={num(r.followups_verified_in_period) ?? 0} />
      </Stats>
      {visits.length ? (
        <>
          <Sub title="Visits completed" count={visits.length} />
          {visits.map((v) => (
            <Item key={str(v.visit_ref)} title={str(v.school) ?? 'School'} />
          ))}
        </>
      ) : null}
      {overdue.length ? (
        <>
          <Sub title="Overdue tasks" count={overdue.length} />
          {overdue.map((t) => (
            <Item key={str(t.task_ref)} title={str(t.title) ?? 'Task'} meta={`Due ${formatDateTime(str(t.due_at))}`} right={<StatusBadge status="overdue" />} />
          ))}
        </>
      ) : null}
      {upcoming.length ? (
        <>
          <Sub title="Upcoming visits" count={upcoming.length} />
          {upcoming.map((v) => (
            <Item key={str(v.visit_ref)} title={str(v.school) ?? 'School'} meta={formatDateTime(str(v.start))} />
          ))}
        </>
      ) : null}
      <Sub title="Follow-ups by status" />
      <View style={pageStyles.chipRow}>
        {Object.entries(byStatus).map(([k, v]) => (
          <StatusBadge key={k} status={k} label={`${humanize(k)}: ${String(v)}`} />
        ))}
      </View>
      {num(r.visits_cancelled) ? <Text style={pageStyles.muted}>{num(r.visits_cancelled)} visit(s) cancelled in this period.</Text> : null}
      {str(f.label) ? <Text style={[pageStyles.muted, { marginTop: 8 }]}>{str(f.label)}</Text> : null}
    </>
  );
}

function TeacherMessage({ f, L }: { f: Obj; L: Lookups }) {
  const draft = obj(f.draft);
  return (
    <>
      <Text style={styles.body}>
        To {L.teacher(str(f.teacher_ref))?.full_name ?? 'teacher'} · {humanize(str(f.purpose))} · {str(f.language) === 'ta' ? 'Tamil' : 'English'}
      </Text>
      <View style={styles.draft}>
        <Text style={styles.draftText} selectable>
          {str(draft.body) ?? 'No draft text returned.'}
        </Text>
      </View>
      <Text style={pageStyles.muted}>
        Drafted by: {str(draft.generated_by) === 'template' ? 'standard template (no AI)' : str(draft.generated_by) === 'ai' ? 'AI' : humanize(str(draft.generated_by))}.{' '}
        {str(f.delivery)}
      </Text>
    </>
  );
}

function Generic({ f }: { f: Obj }) {
  return (
    <>
      {Object.entries(f).map(([k, v]) => (
        <Text key={k} style={styles.body}>
          {humanize(k)}: {typeof v === 'object' ? (Array.isArray(v) ? `${v.length} item(s)` : '…') : String(v)}
        </Text>
      ))}
    </>
  );
}

export function FactsView({ agent, facts, lookups }: { agent: MentorAgent; facts: Obj; lookups: Lookups }) {
  switch (agent) {
    case 'daily_plan':
      return <DailyPlan f={facts} L={lookups} />;
    case 'weekly_plan':
      return <WeeklyPlan f={facts} L={lookups} />;
    case 'task_prioritisation':
      return <TaskPrioritisation f={facts} L={lookups} />;
    case 'workload_analysis':
      return <WorkloadAnalysis f={facts} L={lookups} />;
    case 'schedule_analysis':
      return <ScheduleAnalysis f={facts} />;
    case 'visit_planning':
      return <VisitPlanning f={facts} L={lookups} />;
    case 'followup_analysis':
      return <FollowupAnalysis f={facts} L={lookups} />;
    case 'report':
      return <Report f={facts} />;
    case 'teacher_message_draft':
      return <TeacherMessage f={facts} L={lookups} />;
    default:
      return <Generic f={facts} />;
  }
}

const styles = StyleSheet.create({
  sub: { color: C.navy, fontSize: 14, fontWeight: '800', marginTop: 14, marginBottom: 6 },
  body: { color: C.text, fontSize: 14, lineHeight: 20 },
  stats: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginVertical: 8 },
  stat: { flexGrow: 1, flexBasis: '22%', minWidth: 110, backgroundColor: C.inputBackground, borderRadius: 10, padding: 10 },
  statValue: { color: C.navy, fontSize: 16, fontWeight: '800' },
  statLabel: { color: C.secondaryText, fontSize: 12, marginTop: 2 },
  item: { borderTopWidth: 1, borderTopColor: C.border, paddingVertical: 8, gap: 2 },
  itemTitle: { color: C.navy, fontSize: 14, fontWeight: '700' },
  block: { flexDirection: 'row', gap: 12, borderTopWidth: 1, borderTopColor: C.border, paddingVertical: 8 },
  blockTime: { color: C.tealDark, fontSize: 13, fontWeight: '800', width: 46, lineHeight: 18 },
  rank: { color: C.tealDark, fontSize: 15, fontWeight: '800', width: 32 },
  dayRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 4 },
  dayLabel: { color: C.text, fontSize: 13, width: 92 },
  dayValue: { color: C.navy, fontSize: 13, fontWeight: '700', minWidth: 40, textAlign: 'right' },
  draft: { backgroundColor: '#F2FBFA', borderRadius: 12, borderWidth: 1, borderColor: '#BFE7E3', padding: 12, marginVertical: 8 },
  draftText: { color: C.text, fontSize: 15, lineHeight: 22 },
});
