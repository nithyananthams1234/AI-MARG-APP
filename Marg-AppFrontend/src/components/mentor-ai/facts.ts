/**
 * Safe readers for Mentor Intelligence `facts` (typed as unknown JSON by the
 * API contract). Shapes were confirmed against the live backend.
 */
export type Obj = Record<string, unknown>;

export const obj = (v: unknown): Obj => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Obj) : {});
export const arr = (v: unknown): Obj[] => (Array.isArray(v) ? v.map(obj) : []);
export const strs = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []);
export const str = (v: unknown): string | undefined => (typeof v === 'string' && v.length > 0 ? v : undefined);
export const num = (v: unknown): number | undefined => (typeof v === 'number' && Number.isFinite(v) ? v : undefined);

/** "2026-11-01T10:00:00+05:30" -> "10:00" (local wall time as recorded). */
export function hhmm(iso?: string): string {
  if (!iso) return '';
  const m = /T(\d{2}:\d{2})/.exec(iso);
  return m ? m[1] : iso;
}

export function minutes(m?: number): string {
  if (m == null) return '—';
  const h = Math.floor(m / 60);
  const r = Math.round(m % 60);
  return h > 0 ? (r ? `${h} h ${r} min` : `${h} h`) : `${r} min`;
}
