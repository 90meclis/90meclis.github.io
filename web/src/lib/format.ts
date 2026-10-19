export const TZ = "Europe/Istanbul";
const LOCALE = "tr-TR";

const fmtCache = new Map<string, Intl.DateTimeFormat>();
function f(opts: Intl.DateTimeFormatOptions) {
  const k = JSON.stringify(opts);
  let x = fmtCache.get(k);
  if (!x) {
    x = new Intl.DateTimeFormat(LOCALE, { timeZone: TZ, ...opts });
    fmtCache.set(k, x);
  }
  return x;
}

export const time = (iso: string | null | undefined) => (iso ? f({ hour: "2-digit", minute: "2-digit" }).format(new Date(iso)) : "—");
export const dateShort = (iso: string | null | undefined) => (iso ? f({ day: "2-digit", month: "2-digit" }).format(new Date(iso)) : "—");
export const dateMed = (iso: string | null | undefined) => (iso ? f({ day: "numeric", month: "long", weekday: "short" }).format(new Date(iso)) : "—");
export const dateLong = (iso: string | null | undefined) => (iso ? f({ day: "numeric", month: "long", year: "numeric", weekday: "long" }).format(new Date(iso)) : "—");
export const dateTime = (iso: string | null | undefined) =>
  iso ? f({ day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(iso)) : "—";

/** İstanbul saatine göre YYYY-MM-DD */
export function trDay(d: Date | string = new Date()): string {
  const parts = f({ year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(d));
  const g = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${g("year")}-${g("month")}-${g("day")}`;
}

/** İstanbul günü (YYYY-MM-DD) → UTC aralığı. Türkiye 2016'dan beri sabit UTC+3. */
export function dayBoundsUtc(day: string): [string, string] {
  const start = new Date(`${day}T00:00:00+03:00`);
  const end = new Date(start.getTime() + 86400000);
  return [start.toISOString(), end.toISOString()];
}

export function addDays(day: string, n: number): string {
  const d = new Date(`${day}T12:00:00+03:00`);
  d.setUTCDate(d.getUTCDate() + n);
  return trDay(d);
}

export function dayLabel(day: string): { top: string; bottom: string } {
  const today = trDay();
  const d = new Date(`${day}T12:00:00+03:00`);
  const top =
    day === today ? "Bugün" : day === addDays(today, 1) ? "Yarın" : day === addDays(today, -1) ? "Dün" : f({ weekday: "short" }).format(d);
  return { top, bottom: f({ day: "numeric", month: "short" }).format(d) };
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  const abs = Math.abs(diff);
  if (abs < 60) return "az önce";
  if (abs < 3600) return rtf.format(-Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(-Math.round(diff / 3600), "hour");
  if (abs < 86400 * 7) return rtf.format(-Math.round(diff / 86400), "day");
  return dateShort(iso);
}

export const pct = (p: number | null | undefined, digits = 0) =>
  p === null || p === undefined || Number.isNaN(p) ? "—" : `%${(p * 100).toLocaleString(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;

export const num = (n: number | null | undefined, digits = 2) =>
  n === null || n === undefined || Number.isNaN(n) ? "—" : Number(n).toLocaleString(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const signed = (n: number | null | undefined, digits = 2) =>
  n === null || n === undefined || Number.isNaN(n) ? "—" : `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toLocaleString(LOCALE, { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;

export function hoursBefore(recorded: string, kickoff: string): string {
  const h = (new Date(kickoff).getTime() - new Date(recorded).getTime()) / 3600000;
  if (h < 0) return "—";
  if (h < 1) return `${Math.round(h * 60)} dk önce`;
  if (h < 48) return `${Math.round(h)} sa önce`;
  return `${Math.round(h / 24)} gün önce`;
}
