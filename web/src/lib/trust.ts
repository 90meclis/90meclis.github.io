import type { Coupon, Prediction } from "./types";
import { TZ } from "./format";

export const SETTLED = new Set(["kazandi", "kaybetti", "iade"]);

export interface Summary {
  total: number; settled: number; won: number; lost: number; voids: number; pending: number;
  hit: number | null; profit: number; roi: number | null; priced: number; brier: number | null;
  clv: number | null; clvN: number;
}

/** Python tarafıyla (meclis/trust.py) aynı tanımlar. Kâr/ROI yalnızca piyasa oranlı tahminlerde. */
export function summarize(rows: Prediction[]): Summary {
  const s = rows.filter((r) => SETTLED.has(r.status));
  const won = s.filter((r) => r.status === "kazandi").length;
  const lost = s.filter((r) => r.status === "kaybetti").length;
  const priced = s.filter((r) => r.odds !== null && r.status !== "iade");
  const profit = priced.reduce((a, r) => a + (Number(r.profit) || 0), 0);
  const wl = s.filter((r) => r.status !== "iade");
  const brier = wl.length ? wl.reduce((a, r) => a + (r.probability - (r.status === "kazandi" ? 1 : 0)) ** 2, 0) / wl.length : null;
  const clvs = s.map((r) => r.clv).filter((x): x is number => x !== null && x !== undefined);
  return {
    total: rows.length, settled: s.length, won, lost, voids: s.filter((r) => r.status === "iade").length,
    pending: rows.length - s.length, hit: won + lost ? won / (won + lost) : null,
    profit: Math.round(profit * 100) / 100, roi: priced.length ? profit / priced.length : null, priced: priced.length,
    brier, clv: clvs.length ? clvs.reduce((a, b) => a + b, 0) / clvs.length : null, clvN: clvs.length,
  };
}

export function isoWeek(iso: string): string {
  // İstanbul saatine göre ISO hafta
  const local = new Date(new Date(iso).toLocaleString("en-US", { timeZone: TZ }));
  const d = new Date(Date.UTC(local.getFullYear(), local.getMonth(), local.getDate()));
  const day = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - day);
  const y = d.getUTCFullYear();
  const w = Math.ceil(((d.getTime() - Date.UTC(y, 0, 1)) / 86400000 + 1) / 7);
  return `${y}-H${String(w).padStart(2, "0")}`;
}

export function groupBy<T>(rows: T[], key: (r: T) => string): [string, T[]][] {
  const m = new Map<string, T[]>();
  for (const r of rows) {
    const k = key(r);
    if (!m.has(k)) m.set(k, []);
    m.get(k)!.push(r);
  }
  return [...m.entries()];
}

export interface CurvePoint { t: string; v: number; label: string }

/** Kasa eğrisi: piyasa oranlı sonuçlanmış tahminler + kuponlar, 1 birim sabit stake. */
export function equity(preds: Prediction[], coupons: Coupon[] = []): CurvePoint[] {
  const ev: { t: string; p: number; label: string }[] = [];
  for (const r of preds) {
    if ((r.status === "kazandi" || r.status === "kaybetti") && r.odds !== null && r.tag === "meclis_gorusu")
      ev.push({ t: r.kickoff_at, p: Number(r.profit) || 0, label: `${r.home_name} – ${r.away_name}` });
  }
  for (const c of coupons) {
    if ((c.status === "kazandi" || c.status === "kaybetti") && c.odds_source === "piyasa")
      ev.push({ t: c.first_kickoff_at, p: Number(c.profit) || 0, label: c.tag === "gunun_karari" ? "Günün Kararı kuponu" : "Karar Birliği kuponu" });
  }
  ev.sort((a, b) => a.t.localeCompare(b.t));
  let acc = 0;
  return ev.map((e) => ({ t: e.t, v: (acc = Math.round((acc + e.p) * 100) / 100), label: e.label }));
}

export function calibration(rows: Prediction[]) {
  const bins = [0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0001];
  const s = rows.filter((r) => r.status === "kazandi" || r.status === "kaybetti");
  const out: { range: string; n: number; avg: number; real: number }[] = [];
  for (let i = 0; i < bins.length - 1; i++) {
    const g = s.filter((r) => r.probability >= bins[i] && r.probability < bins[i + 1]);
    if (!g.length) continue;
    out.push({
      range: `%${Math.round(bins[i] * 100)}–${Math.min(100, Math.round(bins[i + 1] * 100))}`,
      n: g.length,
      avg: g.reduce((a, r) => a + r.probability, 0) / g.length,
      real: g.filter((r) => r.status === "kazandi").length / g.length,
    });
  }
  return out;
}

export function couponSummary(cs: Coupon[]) {
  const done = cs.filter((c) => SETTLED.has(c.status));
  return {
    total: cs.length,
    won: done.filter((c) => c.status === "kazandi").length,
    lost: done.filter((c) => c.status === "kaybetti").length,
    profit: Math.round(done.filter((c) => c.odds_source === "piyasa").reduce((a, c) => a + (Number(c.profit) || 0), 0) * 100) / 100,
  };
}
