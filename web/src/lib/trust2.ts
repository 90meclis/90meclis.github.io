import { supabase } from "./supabase";
import { isoWeek, type Bet } from "./trust";

/** Model backtest görünümü (havuz işçisi ekliyor). Görünüm yoksa ya da boşsa null: bölüm gizlenir. */
export type BtRow = Record<string, string | number | boolean | null>;
export async function backtest(): Promise<BtRow[] | null> {
  if (!supabase) return null;
  for (const v of ["v_model_backtest", "v_backtest"]) {
    try {
      const { data, error } = await supabase.from(v).select("*").limit(500);
      if (!error && data && data.length) return data as BtRow[];
    } catch { /* yok */ }
  }
  return null;
}

/** Sonuçlanmış (kazandı/kaybetti) bahislerde seriler: en uzun kazanma/kaybetme ve güncel seri. */
export function streaks(bets: Bet[]) {
  const ev = bets.filter((b) => b.status === "kazandi" || b.status === "kaybetti").sort((a, b) => a.t.localeCompare(b.t));
  let bw = 0, bl = 0, cw = 0, cl = 0;
  for (const e of ev) {
    if (e.status === "kazandi") { cw++; cl = 0; } else { cl++; cw = 0; }
    bw = Math.max(bw, cw); bl = Math.max(bl, cl);
  }
  const last = ev[ev.length - 1];
  return { n: ev.length, bestWin: bw, bestLoss: bl, current: last ? { kind: last.status as "kazandi" | "kaybetti", len: last.status === "kazandi" ? cw : cl } : null };
}

export interface WeekPt { week: string; n: number; won: number; lost: number; profit: number; cum: number; priced: number }
export function weekly(bets: Bet[]): WeekPt[] {
  const m = new Map<string, WeekPt>();
  const ev = bets.filter((b) => b.status === "kazandi" || b.status === "kaybetti").sort((a, b) => a.t.localeCompare(b.t));
  for (const e of ev) {
    const w = isoWeek(e.t);
    if (!m.has(w)) m.set(w, { week: w, n: 0, won: 0, lost: 0, profit: 0, cum: 0, priced: 0 });
    const x = m.get(w)!;
    x.n++; if (e.status === "kazandi") x.won++; else x.lost++;
    if (e.priced) { x.priced++; x.profit = Math.round((x.profit + (Number(e.profit) || 0)) * 100) / 100; }
  }
  let c = 0;
  return [...m.values()].sort((a, b) => a.week.localeCompare(b.week)).map((x) => { c = Math.round((c + x.profit) * 100) / 100; return { ...x, cum: c }; });
}

export interface BtBin { n: number; kutu: string; gercek: number; model_ort: number }
export interface Bt {
  market: string; segment: string | null; n: number; label: string | null;
  brier_model: number | null; brier_market: number | null; brier_blend: number | null;
  ll_model: number | null; ll_market: number | null; ll_blend: number | null; harman_agirligi: number | null;
  deger_secim_sayisi: number | null; deger_isabet: number | null; deger_roi: number | null;
  kalibrasyon: BtBin[] | null; leagues: string[] | null; model_version: string | null; computed_at: string | null;
}
export const asBt = (r: BtRow) => r as unknown as Bt;
