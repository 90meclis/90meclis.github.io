import type { Coupon, Prediction } from "./types";
import { TZ } from "./format";

/*
 * Kâr/zarar tanımı — Streamlit (views/guven_panosu.py) ile birebir aynı:
 *  Tekliler = Meclis Görüşü kayıtları. Kâr/ROI yalnızca kayıt anında PİYASA oranı olanlarda (1 birim). İsabet hepsinde.
 *  Kuponlar = Günün Kararı / Karar Birliği, KUPON düzeyinde (ayaklar ayrı bahis sayılmaz). Kâr/ROI yalnızca odds_source='piyasa'.
 *  Toplam   = tekliler + kuponlar.
 *  ROI = kâr / piyasa oranlı, iade olmayan sonuçlanmış bahis sayısı. İsabet = kazanan / (kazanan + kaybeden).
 *  Eğri sırası: tekliler başlama saatine, kuponlar ilk maçın başlama saatine göre.
 */
export const SETTLED = new Set(["kazandi", "kaybetti", "iade"]);

export interface Bet {
  kind: "tekli" | "kupon";
  t: string;
  status: string;
  priced: boolean;
  profit: number | null;
  league: string | null;
  market: string;
  probability: number | null;
  label: string;
  clv: number | null;
}

export function toBets(preds: Prediction[], coupons: Coupon[]): Bet[] {
  const out: Bet[] = [];
  for (const p of preds) {
    if (p.tag !== "meclis_gorusu") continue;
    out.push({ kind: "tekli", t: p.kickoff_at, status: p.status, priced: p.odds !== null, profit: p.profit, league: p.league,
      market: p.market, probability: p.probability, label: `${p.home_name} – ${p.away_name}`, clv: p.clv });
  }
  for (const c of coupons) {
    out.push({ kind: "kupon", t: c.first_kickoff_at, status: c.status, priced: c.odds_source === "piyasa", profit: c.profit, league: null,
      market: c.tag, probability: c.joint_probability, label: c.tag === "gunun_karari" ? "Günün Kararı kuponu" : "Karar Birliği kuponu", clv: null });
  }
  return out;
}

export interface Summary {
  total: number; pending: number; won: number; lost: number; voids: number;
  hit: number | null; profit: number | null; roi: number | null; priced: number;
  brier: number | null; clv: number | null; clvN: number;
}

export function summarize(rows: Bet[]): Summary {
  const s = rows.filter((r) => SETTLED.has(r.status));
  const won = s.filter((r) => r.status === "kazandi").length;
  const lost = s.filter((r) => r.status === "kaybetti").length;
  const priced = s.filter((r) => r.priced && r.status !== "iade");
  const profit = priced.reduce((a, r) => a + (Number(r.profit) || 0), 0);
  const wl = s.filter((r) => r.status !== "iade" && r.probability !== null);
  const clvs = s.map((r) => r.clv).filter((x): x is number => x !== null && x !== undefined);
  return {
    total: rows.length, pending: rows.length - s.length, won, lost, voids: s.filter((r) => r.status === "iade").length,
    hit: won + lost ? won / (won + lost) : null,
    profit: priced.length ? Math.round(profit * 100) / 100 : null,
    roi: priced.length ? profit / priced.length : null, priced: priced.length,
    brier: wl.length ? wl.reduce((a, r) => a + (r.probability! - (r.status === "kazandi" ? 1 : 0)) ** 2, 0) / wl.length : null,
    clv: clvs.length ? clvs.reduce((a, b) => a + b, 0) / clvs.length : null, clvN: clvs.length,
  };
}

export function isoWeek(iso: string): string {
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
export interface Curves { tekli: CurvePoint[]; kupon: CurvePoint[]; toplam: CurvePoint[] }

/** Kasa eğrileri: tekliler, kuponlar ve toplam; yalnızca piyasa oranlı sonuçlanmış bahisler. */
export function curves(bets: Bet[]): Curves {
  const ev = bets.filter((b) => (b.status === "kazandi" || b.status === "kaybetti") && b.priced).sort((a, b) => a.t.localeCompare(b.t));
  let s = 0, c = 0, all = 0;
  const out: Curves = { tekli: [], kupon: [], toplam: [] };
  for (const e of ev) {
    const p = Number(e.profit) || 0;
    if (e.kind === "tekli") s = Math.round((s + p) * 100) / 100; else c = Math.round((c + p) * 100) / 100;
    all = Math.round((all + p) * 100) / 100;
    out.tekli.push({ t: e.t, v: s, label: e.label });
    out.kupon.push({ t: e.t, v: c, label: e.label });
    out.toplam.push({ t: e.t, v: all, label: e.label });
  }
  return out;
}

export function calibration(rows: Bet[]) {
  const bins = [0, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0001];
  const s = rows.filter((r) => (r.status === "kazandi" || r.status === "kaybetti") && r.probability !== null);
  const out: { range: string; n: number; avg: number; real: number; lo: number; hi: number }[] = [];
  for (let i = 0; i < bins.length - 1; i++) {
    const g = s.filter((r) => r.probability! >= bins[i] && r.probability! < bins[i + 1]);
    if (!g.length) continue;
    out.push({
      range: `%${Math.round(bins[i] * 100)}–${Math.min(100, Math.round(bins[i + 1] * 100))}`,
      n: g.length, avg: g.reduce((a, r) => a + r.probability!, 0) / g.length,
      real: g.filter((r) => r.status === "kazandi").length / g.length,
      ...(() => { const w = wilson(g.filter((r) => r.status === "kazandi").length, g.length)!; return { lo: w[0], hi: w[1] }; })(),
    });
  }
  return out;
}

/** Wilson %95 aralığı (isabet oranı için). */
export function wilson(k: number, n: number, z = 1.96): [number, number] | null {
  if (!n) return null;
  const p = k / n, d = 1 + (z * z) / n;
  const c = (p + (z * z) / (2 * n)) / d;
  const h = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / d;
  return [Math.max(0, c - h), Math.min(1, c + h)];
}

export interface ClvStat { n: number; mean: number; lo: number; hi: number; beat: number }
/** CLV ortalaması ve %95 güven aralığı (normal yaklaşım; n<2 için aralık yok). beat = kapanışı yenen pay. */
export function clvStat(rows: Bet[]): ClvStat | null {
  const v = rows.filter((r) => SETTLED.has(r.status) || r.clv !== null).map((r) => r.clv).filter((x): x is number => x !== null && x !== undefined);
  if (!v.length) return null;
  const n = v.length, mean = v.reduce((a, b) => a + b, 0) / n;
  const sd = n > 1 ? Math.sqrt(v.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1)) : 0;
  const h = n > 1 ? (1.96 * sd) / Math.sqrt(n) : 0;
  return { n, mean, lo: mean - h, hi: mean + h, beat: v.filter((x) => x > 0).length / n };
}

/** Örneklem eşiği: n<30 anlamlı değil, n<100 erken, sonrası okunabilir. */
export function sampleLevel(n: number): "yok" | "erken" | "gelisen" | "okunur" {
  return n === 0 ? "yok" : n < 30 ? "erken" : n < 100 ? "gelisen" : "okunur";
}

/** "Piyasayı yeniyor muyuz?" tek cümlelik dürüst özet. */
export function verdictLine(c: ClvStat | null, settled: number): string {
  if (!c || c.n < 30) {
    const n = c?.n ?? 0;
    return n
      ? `Henüz hüküm yok: kapanış oranıyla ölçülmüş ${n} karar var, anlamlı bir okuma için en az 30 gerekir.`
      : `Henüz hüküm yok: ${settled} sonuçlanmış karar var ama kapanış oranıyla ölçülmüş karar henüz yok; Meclis'i piyasaya karşı ölçen tek dürüst ölçüt CLV'dir.`;
  }
  const pp = (x: number) => `${x >= 0 ? "+" : "−"}%${Math.abs(x * 100).toFixed(1).replace(".", ",")}`;
  if (c.lo > 0) return `Evet: ${c.n} kararda kapanış oranını ortalama ${pp(c.mean)} yeniyoruz ve %95 aralığın tamamı sıfırın üstünde (${pp(c.lo)} – ${pp(c.hi)}).`;
  if (c.hi < 0) return `Hayır: ${c.n} kararda kapanışın ortalama ${pp(c.mean)} gerisindeyiz; %95 aralık tamamen sıfırın altında (${pp(c.lo)} – ${pp(c.hi)}).`;
  return `Henüz belli değil: ${c.n} kararda ortalama CLV ${pp(c.mean)}, ama %95 aralık (${pp(c.lo)} – ${pp(c.hi)}) sıfırı kapsıyor.`;
}
