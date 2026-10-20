// Senaryo kaydını (yeni "senaryolar" ya da eski "scenarios") tek biçime çevirir. Alan adları esnek okunur;
// bulunmayan alan boş kalır ve arayüzde o parça hiç çizilmez.
import { pickLabel } from "./labels";

export interface Act { min: number | null; at: number | null; label: string; title: string; text: string }
export interface ScnMarket { label: string; p: number | null; win: boolean | null; value?: number | null }
export interface Signal { text: string; cond?: string; from?: number | null; to?: number | null }
export interface Scn {
  title: string; p: number | null; story: string; acts: Act[]; turn: { min: number | null; text: string } | null;
  final: string | null; scores: { s: string; p: number | null }[]; markets: ScnMarket[]; signals: Signal[];
  pick: { text: string; win: boolean | null; p?: number | null } | null; kind: "ana" | "ortusen"; basis: string[];
}
export interface ScnMeta { mainSum: number | null; whatIf: string | null; sims: number | null }

type R = Record<string, unknown>;
const g = (o: R, ...ks: string[]) => { for (const k of ks) if (o[k] !== undefined && o[k] !== null && o[k] !== "") return o[k]; return undefined; };
const str = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : String(v));
const numOrNull = (v: unknown) => (typeof v === "number" && isFinite(v) ? v : typeof v === "string" && v.trim() && !isNaN(Number(v)) ? Number(v) : null);
/** "0–15′" → 0, "70–90′+" → 70, "Devre arası" → 45, 34 → 34 (aralıkta başlangıç dakikası). */
const minOf = (v: unknown) => {
  if (typeof v === "string") {
    if (/devre/i.test(v)) return 45;
    const m = v.match(/\d+/); return m ? Math.max(0, Math.min(95, Number(m[0]))) : null;
  }
  const n = numOrNull(v); return n == null ? null : Math.max(0, Math.min(95, n));
};
const tri = (p: number | null) => (p == null ? null : p >= 0.6 ? true : p <= 0.4 ? false : null);
function rawList(payload: R): unknown[] | null {
  const raw = (g(payload, "senaryolar") ?? g(payload, "scenarios")) as unknown;
  if (Array.isArray(raw)) return raw;
  if (raw && typeof raw === "object") { const l = g(raw as R, "liste", "list", "items"); if (Array.isArray(l)) return l; }
  return null;
}
export function scenarioMeta(payload: R | undefined): ScnMeta {
  const raw = payload ? (g(payload, "senaryolar") as unknown) : null;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return { mainSum: null, whatIf: null, sims: null };
  const r = raw as R, w = g(r, "eksik_etkisi") as R | undefined;
  return { mainSum: numOrNull(g(r, "ortusmeyen_toplam")), whatIf: w && typeof w === "object" ? str(g(w, "metin")) || null : null, sims: numOrNull(g(r, "simulasyon")) };
}

export function normalizeScenarios(payload: R | undefined, home: string, away: string): Scn[] {
  if (!payload) return [];
  const raw = rawList(payload);
  if (!raw) return [];
  return raw.filter((x) => x && typeof x === "object").map((x0) => {
    const x = x0 as R;
    const acts = ((g(x, "perde", "perdeler", "acts") as unknown[] | undefined) ?? []).filter((a) => a && typeof a === "object").map((a0) => {
      const a = a0 as R;
      const d = g(a, "dakika", "dk", "minute");
      const nums = typeof d === "string" ? (d.match(/\d+/g) ?? []).map(Number) : [];
      const at = typeof d === "string" && /devre/i.test(d) ? 45 : nums.length >= 2 ? Math.min(95, (nums[0] + nums[1]) / 2) : minOf(d);
      return { min: minOf(d), at, label: typeof d === "string" ? d : d != null ? `${d}′` : "", title: str(g(a, "baslik", "başlık", "title")), text: str(g(a, "metin", "anlatim", "anlatım", "text")) };
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
      : mk && typeof mk === "object" ? Object.entries(mk as R).flatMap(([label, v]): ScnMarket[] => {
        if (v && typeof v === "object") {
          const o = v as R;
          if (label === "1X2" || ("1" in o && "X" in o)) return ([["1", `${home} kazanır`], ["X", "Beraberlik"], ["2", `${away} kazanır`]] as const)
            .map(([k2, l]) => { const p = numOrNull(o[k2]); return { label: l, p, win: tri(p) }; })
            // sonuç senaryosunda 1X2 tanım gereği %100/%0'dır: bilgi taşımaz, gösterilmez
            .filter((q) => q.p != null && q.p > 0.005 && q.p < 0.995);
          const ex = numOrNull(g(o, "beklenen", "expected"));
          if (ex != null) return [{ label, p: null, win: null, value: ex }];
          const p = numOrNull(g(o, "olasilik", "p", "probability"));
          return [{ label, p, win: tri(p) }];
        }
        const p = numOrNull(v); return [{ label: label.replace(/(\d)\.(\d)/, "$1,$2"), p, win: tri(p) }];
      }) : [];
    const sig = g(x, "canli_sinyaller", "canlida_izle", "canlı_sinyaller", "sinyaller", "live_signals", "izle") as unknown;
    const signals: Signal[] = (Array.isArray(sig) ? sig : sig ? [sig] : []).map((s): Signal => {
      if (typeof s === "object" && s) {
        const o = s as R, cond = str(g(o, "sinyal", "kosul"));
        const from = numOrNull(g(o, "olasilik_once")), to = numOrNull(g(o, "olasilik_sonra"));
        return { text: str(g(o, "metin", "text")) || cond, cond: cond || undefined, from, to };
      }
      return { text: str(s) };
    }).filter((s) => s.text);
    const pk = g(x, "meclis_secimi", "meclis_karari", "meclis_kararı", "karar", "pick") as unknown;
    const durum = pk && typeof pk === "object" ? str(g(pk as R, "durum")) : "";
    const pick = pk == null ? null : typeof pk === "object"
      ? { text: [str(g(pk as R, "metin", "text", "etiket", "secim")).replace(/(\d)\.(\d)/g, "$1,$2"), durum && durum !== "senaryodan bağımsız" ? durum : durum ? "(senaryodan bağımsız)" : ""].filter(Boolean).join(durum && durum !== "senaryodan bağımsız" ? ": " : " "),
          p: numOrNull(g(pk as R, "kazanma_olasiligi")),
          win: typeof g(pk as R, "kazanir", "kazanır", "win") === "boolean" ? (g(pk as R, "kazanir", "kazanır", "win") as boolean) : durum === "kazanır" ? true : durum === "kaybeder" ? false : null }
      : { text: str(pk), win: /kazan|tutar/i.test(str(pk)) ? true : /kaybe|yatar/i.test(str(pk)) ? false : null };
    return {
      title: str(g(x, "baslik", "başlık", "ad", "title")), p: numOrNull(g(x, "olasilik", "olasılık", "probability")),
      story: str(g(x, "hikaye", "hikâye", "anlatim", "anlatım", "ozet", "story")), acts, turn: turn && turn.text ? turn : null,
      final: fin != null ? str(typeof fin === "object" ? g(fin as R, "skor", "score") : fin) || null : null,
      scores, markets, signals, pick: pick && pick.text ? pick : null,
      kind: (str(g(x, "tur")) === "ortusen" ? "ortusen" : "ana") as Scn["kind"],
      basis: ((g(x, "dayanaklar") as unknown[] | undefined) ?? []).map(str).filter(Boolean),
    };
  }).filter((s) => s.title);
}
