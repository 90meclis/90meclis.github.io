import type { BotAnalysis } from "./data";
import type { MarketRow } from "./types";

// Botun değer kuralının (meclis/analysis.py rank_picks) ön yüz karşılığı; bot_picks / v_bot_bulten yoksa kullanılır.
// Kalibrasyon: p_kal = 0.65·p_model + 0.35·p_piyasa(marjsız); değer = p_kal·oran − 1 ≥ %3; oran 1,50–5,00; p_kal ≥ 0,30.
// Oransız pazarlar: yalnızca model temelli analizde, p ≥ 0,55 ve adil oran ≥ 1,50 ("adil oran", arşive girmez).
export const VALUE_EDGE_MIN = 0.03;
const MIN_ODDS = 1.5, MAX_ODDS = 5, CAL_W = 0.65;

export type BotPick = MarketRow & { kind: string; score: number; status?: string | null };

function implied(ms: MarketRow[]): Map<string, number> {
  const g = new Map<string, MarketRow[]>();
  for (const m of ms) {
    if (!m.odds || m.odds <= 1) continue;
    let ln = m.line;
    if (m.market === "AH" && ln != null) ln = m.selection === "1" ? ln : -ln;
    const k = `${m.market}|${ln}`;
    g.set(k, [...(g.get(k) ?? []), m]);
  }
  const out = new Map<string, number>();
  for (const list of g.values()) {
    const inv = list.reduce((a, x) => a + 1 / x.odds!, 0);
    if (list.length >= 2 && inv > 0) for (const x of list) out.set(`${x.market}|${x.selection}|${x.line}`, 1 / x.odds! / inv);
  }
  return out;
}

export function valuePicks(a: BotAnalysis | undefined): BotPick[] {
  if (!a?.ready || !a.markets?.length) return [];
  const modelBased = (a.basis ?? "").startsWith("model");
  const mm = a.model_matches ?? {};
  if (modelBased && Math.min(mm.home ?? 0, mm.away ?? 0) < (a.min_team_matches ?? 4)) return [];
  const imp = implied(a.markets);
  const value: BotPick[] = [], fair: BotPick[] = [];
  for (const m of a.markets) {
    if (m.market === "CS") continue;
    const o = m.odds;
    if (o) {
      const pm = imp.get(`${m.market}|${m.selection}|${m.line}`);
      const pc = pm != null ? CAL_W * m.probability + (1 - CAL_W) * pm : m.probability;
      const edge = pc * o - 1;
      if (o < MIN_ODDS || o > MAX_ODDS || pc < 0.3 || edge < VALUE_EDGE_MIN) continue;
      value.push({ ...m, probability: pc, edge, kind: "değer", score: edge });
    } else if (modelBased && m.market !== "DC" && m.probability >= 0.55 && 1 / m.probability >= MIN_ODDS) {
      fair.push({ ...m, kind: "adil oran", score: m.probability * 0.25 });
    }
  }
  return [...value.sort((x, y) => y.score - x.score), ...fair.sort((x, y) => y.score - x.score)];
}
