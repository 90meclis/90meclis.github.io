// Pazar taraması: botun her pazar için modeli (analiz kaydı) ile piyasa oranını (matches.odds) yan yana koyar.
// Hiçbir sayı türetilmez: model olasılığı analizden, oran ve kaynağı oran havuzundan; marjsız piyasa olasılığı
// aynı çizginin iki/üç tarafının oranlarından hesaplanır. Değer kuralı botunkiyle aynı (lib/bot.ts).
import type { Match, MarketRow } from "./types";
import { MARKET_GROUPS } from "./labels";

export const CAL_W = 0.65, EDGE_MIN = 0.03, MIN_ODDS = 1.5, MAX_ODDS = 5;

export interface ScanRow {
  market: string; selection: string; line: number | null; group: string;
  pModel: number | null; odds: number | null; pMarket: number | null; src: string | null;
  pCal: number | null; edge: number | null; value: boolean;
}

const GROUP_OF: Record<string, string> = Object.fromEntries(Object.entries(MARKET_GROUPS).flatMap(([g, ms]) => ms.map((m) => [m, g])));
const SELS: Record<string, string[]> = { "1X2": ["1", "X", "2"], DC: ["1X", "12", "X2"], BTTS: ["VAR", "YOK"], AH: ["1", "2"] };

function oddsKey(market: string, selection: string, line: number | null): string {
  if (line == null) return market;
  if (market === "AH") return `AH_${selection === "1" ? line : -line}`;
  return `${market}_${line}`;
}

/** Bir oran grubundaki (aynı pazar + çizgi) marjsız olasılıklar. */
function fairFrom(group: Record<string, number | string> | undefined, sels: string[]): Record<string, number> | null {
  if (!group) return null;
  const o = sels.map((s) => (typeof group[s] === "number" ? (group[s] as number) : null));
  if (o.some((x) => x === null || x! <= 1)) return null;
  const inv = o.map((x) => 1 / x!);
  const sum = inv.reduce((a, b) => a + b, 0);
  return Object.fromEntries(sels.map((s, i) => [s, inv[i] / sum]));
}

function selsFor(market: string, key: string, group: Record<string, unknown>): string[] {
  if (SELS[market]) return SELS[market];
  void key;
  return ["ALT", "ÜST"].filter((s) => s in group);
}

export function scanMatch(m: Pick<Match, "odds">, markets: MarketRow[] | null | undefined, modelBased: boolean): ScanRow[] {
  const odds = m.odds ?? {};
  const out: ScanRow[] = [];
  const seen = new Set<string>();
  const row = (market: string, selection: string, line: number | null, pModel: number | null): ScanRow | null => {
    if (!GROUP_OF[market]) return null;
    const key = oddsKey(market, selection, line);
    const g = odds[key] as Record<string, number | string> | undefined;
    const sel = market === "AH" ? selection : selection;
    const o = g && typeof g[sel] === "number" ? (g[sel] as number) : null;
    const fair = fairFrom(g, market === "AH" ? ["1", "2"] : selsFor(market, key, g ?? {}));
    const pMarket = fair?.[sel] ?? null;
    const pCal = pModel != null ? (pMarket != null ? CAL_W * pModel + (1 - CAL_W) * pMarket : pModel) : null;
    const edge = pCal != null && o ? pCal * o - 1 : null;
    const value = modelBased && edge != null && o != null && o >= MIN_ODDS && o <= MAX_ODDS && pCal! >= 0.3 && edge >= EDGE_MIN;
    return { market, selection, line, group: GROUP_OF[market], pModel, odds: o, pMarket, src: g ? String(g.src ?? "") || null : null, pCal, edge, value };
  };
  for (const x of markets ?? []) {
    if (x.market === "CS") continue;
    const r = row(x.market, x.selection, x.line ?? null, x.probability);
    if (r) { out.push(r); seen.add(oddsKey(x.market, x.selection, x.line ?? null) + "|" + x.selection); }
  }
  // Modelin hesaplamadığı ama piyasada fiyatı olan pazarlar (yalnızca piyasa görüşü; makul fiyat aralığı)
  for (const [key, g] of Object.entries(odds)) {
    const mm = key.match(/^([0-9A-Z_]+?)(?:_(-?\d+(?:\.\d+)?))?$/);
    if (!mm || !GROUP_OF[mm[1]] || typeof g !== "object") continue;
    const market = mm[1], ln = mm[2] != null ? Number(mm[2]) : null;
    const sels = market === "AH" ? ["1", "2"] : selsFor(market, key, g as Record<string, unknown>);
    for (const sel of sels) {
      const line = market === "AH" && ln != null ? (sel === "1" ? ln : -ln) : ln;
      if (seen.has(oddsKey(market, sel, line) + "|" + sel)) continue;
      const r = row(market, sel, line, null);
      if (r && r.odds && r.odds >= 1.2 && r.odds <= 6) out.push(r);
    }
  }
  const order = Object.keys(MARKET_GROUPS);
  const mOrder = Object.values(MARKET_GROUPS).flat();
  return out.sort((a, b) => order.indexOf(a.group) - order.indexOf(b.group) || mOrder.indexOf(a.market) - mOrder.indexOf(b.market)
    || (a.line ?? 0) - (b.line ?? 0) || a.selection.localeCompare(b.selection));
}
