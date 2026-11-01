/** Local-time date helpers for the schedule screen. */
export function startOfWeek(d: Date): Date {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const offset = (x.getDay() + 6) % 7; // Monday = 0
  x.setDate(x.getDate() - offset);
  return x;
}

export function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

export function sameLocalDay(iso: string, day: Date): boolean {
  const d = new Date(iso);
  return d.getFullYear() === day.getFullYear() && d.getMonth() === day.getMonth() && d.getDate() === day.getDate();
}

export function inRange(iso: string, start: Date, endExclusive: Date): boolean {
  const t = new Date(iso).getTime();
  return t >= start.getTime() && t < endExclusive.getTime();
}

export function timeLabel(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

export function dayLabel(d: Date): string {
  return d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' });
}

export function weekLabel(start: Date): string {
  const end = addDays(start, 6);
  const f = (x: Date) => x.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  return `${f(start)} – ${f(end)} ${end.getFullYear()}`;
}
