// Senaryo kaydını (yeni "senaryolar" ya da eski "scenarios") tek biçime çevirir. Alan adları esnek okunur;
// bulunmayan alan boş kalır ve arayüzde o parça hiç çizilmez.
import { pickLabel } from "./labels";

export interface Act { min: number | null; title: string; text: string }
export interface ScnMarket { label: string; p: number | null; win: boolean | null }
export interface Scn {
  title: string; p: number | null; story: string; acts: Act[]; turn: { min: number | null; text: string } | null;
  final: string | null; scores: { s: string; p: number | null }[]; markets: ScnMarket[]; signals: string[];
  pick: { text: string; win: boolean | null } | null;
}

type R = Record<string, unknown>;
const g = (o: R, ...ks: string[]) => { for (const k of ks) if (o[k] !== undefined && o[k] !== null && o[k] !== "") return o[k]; return undefined; };
const str = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));
const numOrNull = (v: unknown) => (typeof v === "number" && isFinite(v) ? v : typeof v === "string" && v.trim() && !isNaN(Number(v)) ? Number(v) : null);
const minOf = (v: unknown) => { const n = numOrNull(typeof v === "string" ? v.replace(/[^\d.]/g, "") : v); return n == null ? null : Math.max(0, Math.min(95, n)); };

export function normalizeScenarios(payload: R | undefined, home: string, away: string): Scn[] {
  if (!payload) return [];
  const raw = (g(payload, "senaryolar") ?? g(payload, "scenarios")) as unknown;
  if (!Array.isArray(raw)) return [];
  return raw.filter((x) => x && typeof x === "object").map((x0) => {
    const x = x0 as R;
    const acts = ((g(x, "perde", "perdeler", "acts") as unknown[] | undefined) ?? []).filter((a) => a && typeof a === "object").map((a0) => {
      const a = a0 as R;
      return { min: minOf(g(a, "dakika", "dk", "minute")), title: str(g(a, "baslik", "başlık", "title")), text: str(g(a, "metin", "anlatim", "anlatım", "text")) };
    }).filter((a) => a.title || a.text).sort((p, q) => (p.min ?? 0) - (q.min ?? 0));
    const k = g(x, "kirilma_ani", "kırılma_anı", "kirilma", "turning_point");
    const turn = k == null ? null : typeof k === "object"
      ? { min: minOf(g(k as R, "dakika", "dk", "minute")), text: str(g(k as R, "metin", "anlatim", "text", "baslik")) }
      : { min: null, text: str(k) };
    const sc = (g(x, "skorlar", "top_scores", "olasi_skorlar", "skor") as unknown) ?? [];
    const scores = (Array.isArray(sc) ? sc : [sc]).map((s) => typeof s === "object" && s
      ? { s: str(g(s as R, "skor", "score", "s")), p: numOrNull(g(s as R, "olasilik", "olasılık", "p", "probability")) }
      : { s: str(s), p: null }).filter((s) => /\d+\s*[-–]\s*\d+/.test(s.s));
    const fin = g(x, "final_skor", "final", "skor_final");
    const mk = g(x, "markets", "pazarlar") as unknown;
    const markets: ScnMarket[] = Array.isArray(mk)
      ? mk.filter((q) => q && typeof q === "object").map((q0) => {
        const q = q0 as R;
        const label = str(g(q, "etiket", "label")) || (g(q, "market") ? pickLabel(str(q.market), str(g(q, "selection", "secim")), numOrNull(q.line), home, away) : "");
        const p = numOrNull(g(q, "olasilik", "olasılık", "probability", "p"));
        const w = g(q, "kazanir", "kazanır", "win", "tutar");
        return { label, p, win: typeof w === "boolean" ? w : p != null ? p >= 0.5 : null };
      }).filter((q) => q.label)
      : mk && typeof mk === "object" ? Object.entries(mk as R).map(([label, v]) => {
        const p = numOrNull(typeof v === "object" && v ? g(v as R, "olasilik", "p", "probability") : v);
        return { label, p, win: p != null ? p >= 0.5 : null };
      }) : [];
    const sig = g(x, "canli_sinyaller", "canlida_izle", "canlı_sinyaller", "sinyaller", "live_signals", "izle") as unknown;
    const signals = (Array.isArray(sig) ? sig : sig ? [sig] : []).map((s) => typeof s === "object" && s ? str(g(s as R, "metin", "text", "sinyal")) : str(s)).filter(Boolean);
    const pk = g(x, "meclis_karari", "meclis_kararı", "karar", "pick") as unknown;
    const pick = pk == null ? null : typeof pk === "object"
      ? { text: str(g(pk as R, "metin", "text", "etiket", "secim")), win: typeof g(pk as R, "kazanir", "kazanır", "win") === "boolean" ? (g(pk as R, "kazanir", "kazanır", "win") as boolean) : null }
      : { text: str(pk), win: /kazan|tutar/i.test(str(pk)) ? true : /kaybe|yatar/i.test(str(pk)) ? false : null };
    return {
      title: str(g(x, "baslik", "başlık", "ad", "title")), p: numOrNull(g(x, "olasilik", "olasılık", "probability")),
      story: str(g(x, "hikaye", "hikâye", "anlatim", "anlatım", "ozet", "story")), acts, turn: turn && turn.text ? turn : null,
      final: fin != null ? str(typeof fin === "object" ? g(fin as R, "skor", "score") : fin) || null : null,
      scores, markets, signals, pick: pick && pick.text ? pick : null,
    };
  }).filter((s) => s.title);
}
