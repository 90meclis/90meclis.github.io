// Maç dosyası hesapları. Hepsi havuzdaki gerçek kayıtlardan; veri yoksa sonuç boş döner (uydurma yok).
import type { Match, MatchStat } from "./types";
import type { StandRow, TeamStatRow } from "./data";
import { hasScore, sameTeam } from "./match";

export const UEFA = new Set(["CL", "EL", "ECL"]);

export type MetricKey = "gol" | "iy" | "kg" | "korner" | "kart" | "sut" | "isabet" | "kale";
export const METRICS: { key: MetricKey; label: string; lines: number[]; teamLines: number[] }[] = [
  { key: "gol", label: "Gol", lines: [1.5, 2.5, 3.5], teamLines: [0.5, 1.5] },
  { key: "iy", label: "İY Gol", lines: [0.5, 1.5], teamLines: [0.5] },
  { key: "kg", label: "KG", lines: [], teamLines: [] },
  { key: "korner", label: "Korner", lines: [8.5, 9.5, 10.5], teamLines: [3.5, 4.5, 5.5] },
  { key: "kart", label: "Kart", lines: [3.5, 4.5, 5.5], teamLines: [1.5, 2.5] },
  { key: "sut", label: "Şut", lines: [20.5, 24.5], teamLines: [10.5, 12.5] },
  { key: "isabet", label: "İsabetli Şut", lines: [7.5, 8.5, 9.5], teamLines: [3.5, 4.5] },
  { key: "kale", label: "Kale Vuruşu", lines: [14.5, 16.5], teamLines: [6.5, 7.5] },
];

export interface GameRow {
  m: Match; home: boolean; opp: string; comp: "avrupa" | "lig" | "diger";
  gf: number; ga: number; vals: Partial<Record<MetricKey, [number | null, number | null]>>; res: "G" | "B" | "M";
  /** Avrupa kupası aşaması: "Ön eleme/play-off" | "Lig aşaması" | "Eleme turları" (görünümden) */
  stage?: string | null;
  /** lehte–aleyhte xG (yalnızca görünüm satırlarında, kaynakta varsa) */
  xg?: [number | null, number | null];
}

/** v_takim_mac_istatistik satırlarından (takım × maç, lehte/aleyhte) maç satırları. */
export function viewGameRows(rows: TeamStatRow[]): GameRow[] {
  const c = new Map<string, number>();
  for (const r of rows) if (r.competition !== "Avrupa") c.set(r.league, (c.get(r.league) ?? 0) + 1);
  const ml = [...c.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
  const p = (a: number | null, b: number | null): [number | null, number | null] => [a, b];
  return rows.map((r) => {
    const home = r.side === "home";
    const m = {
      id: r.match_id, league: r.league, kickoff_at: r.kickoff_at,
      home_name: home ? r.team_name : r.opponent, away_name: home ? r.opponent : r.team_name,
      home_goals: home ? r.goals_for : r.goals_against, away_goals: home ? r.goals_against : r.goals_for,
    } as Match;
    const gf = r.goals_for, ga = r.goals_against;
    return {
      m, home, opp: r.opponent, comp: r.competition === "Avrupa" ? "avrupa" : r.league === ml ? "lig" : "diger", gf, ga,
      res: gf > ga ? "G" : gf === ga ? "B" : "M", stage: r.competition === "Avrupa" ? r.asama : null, xg: [r.xg_for, r.xg_against],
      vals: {
        gol: [gf, ga], iy: p(r.ht_for, r.ht_against), kg: [gf > 0 ? 1 : 0, ga > 0 ? 1 : 0], korner: p(r.corners_for, r.corners_against),
        kart: p(r.cards_for, r.cards_against), sut: p(r.shots_for, r.shots_against), isabet: p(r.sot_for, r.sot_against),
        kale: p(r.goal_kicks_for, r.goal_kicks_against),
      },
    } as GameRow;
  });
}

/** Görünümdeki puan durumu satırları → TableRow (sıra görünümden, eşitlikte ad sırası). */
export function viewTable(rows: StandRow[], idOf: (r: StandRow) => string): TableRow[] {
  return [...rows].sort((a, b) => a.sira - b.sira || a.team_name.localeCompare(b.team_name)).map((r, i) => ({
    id: idOf(r), name: r.team_name, p: r.o, w: r.g, d: r.b, l: r.m, gf: r.ag, ga: r.yg, pts: r.puan, pos: i + 1,
  }));
}

const cards = (s?: MatchStat) => (s && (s.yellow != null || s.red != null) ? (s.yellow ?? 0) + (s.red ?? 0) : null);

/** Takımın bu sezonki ana ligi: Avrupa dışı maçlarında en sık görülen lig kodu. */
export function mainLeague(games: Match[]): string | null {
  const c = new Map<string, number>();
  for (const g of games) if (!UEFA.has(g.league)) c.set(g.league, (c.get(g.league) ?? 0) + 1);
  return [...c.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
}

export function gameRows(games: Match[], teamId: string, stats: MatchStat[]): GameRow[] {
  const ml = mainLeague(games);
  const idx = new Map(stats.map((s) => [`${s.match_id}:${s.side}`, s]));
  return games.filter(hasScore).map((g) => {
    const home = sameTeam(g.home_team_id, teamId);
    const me = idx.get(`${g.id}:${home ? "home" : "away"}`), op = idx.get(`${g.id}:${home ? "away" : "home"}`);
    const gf = home ? g.home_goals! : g.away_goals!, ga = home ? g.away_goals! : g.home_goals!;
    const hf = home ? g.ht_home_goals : g.ht_away_goals, ha = home ? g.ht_away_goals : g.ht_home_goals;
    const pair = (a: number | null | undefined, b: number | null | undefined): [number | null, number | null] => [a ?? null, b ?? null];
    return {
      m: g, home, opp: home ? g.away_name : g.home_name, comp: UEFA.has(g.league) ? "avrupa" : g.league === ml ? "lig" : "diger", gf, ga,
      res: gf > ga ? "G" : gf === ga ? "B" : "M",
      vals: {
        gol: [gf, ga], iy: pair(hf, ha), kg: [gf > 0 ? 1 : 0, ga > 0 ? 1 : 0],
        korner: pair(me?.corners, op?.corners), kart: pair(cards(me), cards(op)), sut: pair(me?.shots, op?.shots),
        isabet: pair(me?.shots_on_target, op?.shots_on_target), kale: pair(me?.goal_kicks, op?.goal_kicks),
      },
    };
  });
}

/** "son 6 iç saha maçının 5'inde 9,5 üst korner" türü seri cümleleri (yalnızca belirgin olanlar). */
export function streaks(rows: GameRow[], metric: MetricKey, scope: string, fmtLine: (n: number) => string): string[] {
  const def = METRICS.find((x) => x.key === metric)!;
  const out: string[] = [];
  const recent = rows.slice(0, 10);
  if (metric === "kg") {
    const r = recent.filter((x) => x.vals.kg);
    if (r.length >= 5) {
      const k = r.filter((x) => x.gf > 0 && x.ga > 0).length;
      if (k / r.length >= 0.7) out.push(`son ${r.length} ${scope} maçının ${k}'inde KG Var`);
      else if (k / r.length <= 0.3) out.push(`son ${r.length} ${scope} maçının ${r.length - k}'inde KG Yok`);
    }
    return out;
  }
  const tot = recent.map((x) => { const v = x.vals[metric]; return v && v[0] != null && v[1] != null ? v[0] + v[1] : null; }).filter((x): x is number => x != null);
  const fo = recent.map((x) => x.vals[metric]?.[0]).filter((x): x is number => x != null);
  const pick = (vals: number[], lines: number[], what: string) => {
    if (vals.length < 5) return;
    let best: { line: number; k: number; over: boolean; r: number } | null = null;
    for (const ln of lines) {
      const k = vals.filter((v) => v > ln).length;
      const r = Math.max(k, vals.length - k) / vals.length;
      if (r >= 0.8 && (!best || r > best.r)) best = { line: ln, k, over: k >= vals.length - k, r };
    }
    if (best) out.push(`son ${vals.length} ${scope} maçının ${best.over ? best.k : vals.length - best.k}'inde ${fmtLine(best.line)} ${best.over ? "üst" : "alt"} ${what}`);
  };
  pick(tot, def.lines, `toplam ${def.label.toLocaleLowerCase("tr-TR")}`);
  pick(fo, def.teamLines, `takım ${def.label.toLocaleLowerCase("tr-TR")}`);
  return out;
}

export interface TableRow { id: string; name: string; p: number; w: number; d: number; l: number; gf: number; ga: number; pts: number; pos: number }
/** Bu sezonun bitmiş maçlarından puan durumu. */
export function standings(ms: Match[]): TableRow[] {
  const t = new Map<string, TableRow>();
  const get = (id: string, name: string) => t.get(id) ?? (t.set(id, { id, name, p: 0, w: 0, d: 0, l: 0, gf: 0, ga: 0, pts: 0, pos: 0 }), t.get(id)!);
  for (const m of ms) {
    if (!hasScore(m) || m.status === "ertelendi") continue;
    const h = get(m.home_team_id, m.home_name), a = get(m.away_team_id, m.away_name);
    h.p++; a.p++; h.gf += m.home_goals!; h.ga += m.away_goals!; a.gf += m.away_goals!; a.ga += m.home_goals!;
    if (m.home_goals! > m.away_goals!) { h.w++; a.l++; h.pts += 3; } else if (m.home_goals! < m.away_goals!) { a.w++; h.l++; a.pts += 3; } else { h.d++; a.d++; h.pts++; a.pts++; }
  }
  return [...t.values()].sort((x, y) => y.pts - x.pts || (y.gf - y.ga) - (x.gf - x.ga) || y.gf - x.gf || x.name.localeCompare(y.name))
    .map((r, i) => ({ ...r, pos: i + 1 }));
}

/** Son maçından bu yana gün ve son 14 gündeki maç sayısı (bütün kulvarlar; v_dinlenme ile aynı tanım). */
export function rest(games: Match[], kickoff: string): { days: number | null; last14: number } {
  const ko = new Date(kickoff).getTime();
  const past = games.filter((g) => new Date(g.kickoff_at).getTime() < ko);
  const last = past.sort((a, b) => b.kickoff_at.localeCompare(a.kickoff_at))[0];
  return { days: last ? Math.floor((ko - new Date(last.kickoff_at).getTime()) / 864e5) : null, last14: past.filter((g) => ko - new Date(g.kickoff_at).getTime() <= 14 * 864e5).length };
}

/** λ'lardan bağımsız Poisson skor dağılımı (0–5). */
export function poissonGrid(lh: number, la: number, n = 6): number[][] {
  const f = (k: number, l: number) => { let p = Math.exp(-l); for (let i = 1; i <= k; i++) p *= l / i; return p; };
  return Array.from({ length: n }, (_, i) => Array.from({ length: n }, (_, j) => f(i, lh) * f(j, la)));
}

/** Marjsız 1X2 olasılığı (maçın oran kaydından). */
export function implied1x2(m: Pick<Match, "odds">): [number, number, number] | null {
  const g = (m.odds ?? {})["1X2"];
  const o = ["1", "X", "2"].map((s) => (g && typeof g[s] === "number" ? (g[s] as number) : null));
  if (o.some((x) => !x || x <= 1)) return null;
  const inv = o.map((x) => 1 / x!); const s = inv.reduce((a, b) => a + b, 0);
  return inv.map((x) => x / s) as [number, number, number];
}
