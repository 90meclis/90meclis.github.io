import type { BotAnalysis } from "./data";
import type { MarketRow } from "./types";

// Botun değer kuralının (meclis/analysis.py select_single) aynısı; burada maç başına TÜM adaylar listelenir.
export const VALUE_EDGE_MIN = 0.03;
export const NO_ODDS_MIN_PROB = 0.72;

export type BotPick = MarketRow & { kind: "değer" | "yüksek olasılık"; score: number };

export function valuePicks(a: BotAnalysis | undefined): BotPick[] {
  if (!a?.ready || !a.markets?.length) return [];
  const modelBased = (a.basis ?? "").startsWith("model");
  const mm = a.model_matches ?? {};
  if (modelBased && Math.min(mm.home ?? 0, mm.away ?? 0) < (a.min_team_matches ?? 4)) return [];
  const out: BotPick[] = [];
  for (const m of a.markets) {
    if (m.market === "CS") continue;
    const p = m.probability;
    if (m.odds) {
      if (p < 0.4 || m.edge == null || m.edge < VALUE_EDGE_MIN || m.odds > 3.2) continue;
      out.push({ ...m, kind: "değer", score: p * (1 + Math.min(m.edge, 0.25)) });
    } else if (modelBased && p >= NO_ODDS_MIN_PROB && p <= 0.86 && m.market !== "DC") {
      out.push({ ...m, kind: "yüksek olasılık", score: p * 0.97 });
    }
  }
  return out.sort((x, y) => y.score - x.score);
}
