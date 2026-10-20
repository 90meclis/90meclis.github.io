// Seri Avcısı: bugünün maçlarında takımların sahaya göre (ev sahibi evinde, deplasman dışarıda) bu sezonki serileri.
// Kaynak v_takim_mac_istatistik; her seri, aynı pazarın model/piyasa satırına bağlanır ("seri var, değer yok" dürüstlüğü).
import type { TeamStatRow } from "./data";
import type { ScanRow } from "./scan";
import type { Match } from "./types";

export interface Find {
  m: Match; side: "home" | "away"; team: string; text: string; k: number; n: number;
  market: string; selection: string; line: number | null; row?: ScanRow;
}

const DEFS: { market: string; label: string; lines: number[]; v: (r: TeamStatRow) => number | null }[] = [
  { market: "OU_GOALS", label: "toplam gol", lines: [1.5, 2.5, 3.5], v: (r) => r.goals_for + r.goals_against },
  { market: "CORNERS_OU", label: "toplam korner", lines: [7.5, 8.5, 9.5, 10.5, 11.5], v: (r) => (r.corners_for != null && r.corners_against != null ? r.corners_for + r.corners_against : null) },
  { market: "CARDS_OU", label: "toplam kart", lines: [2.5, 3.5, 4.5, 5.5], v: (r) => (r.cards_for != null && r.cards_against != null ? r.cards_for + r.cards_against : null) },
  { market: "SOT_OU", label: "toplam isabetli şut", lines: [6.5, 7.5, 8.5, 9.5, 10.5], v: (r) => (r.sot_for != null && r.sot_against != null ? r.sot_for + r.sot_against : null) },
];
const fl = (x: number) => String(x).replace(".", ",");

export function huntFinds(matches: Match[], rows: TeamStatRow[], slugOf: (id: string) => string, scans: Map<string, ScanRow[]>, minN = 5, minR = 0.8): Find[] {
  const by = new Map<string, TeamStatRow[]>();
  for (const r of rows) by.set(r.team_slug, [...(by.get(r.team_slug) ?? []), r]);
  const out: Find[] = [];
  for (const m of matches) {
    for (const side of ["home", "away"] as const) {
      const slug = slugOf(side === "home" ? m.home_team_id : m.away_team_id);
      const team = side === "home" ? m.home_name : m.away_name;
      const mine = (by.get(slug) ?? []).filter((r) => r.side === side && new Date(r.kickoff_at) < new Date(m.kickoff_at)).slice(0, 8);
      const where = side === "home" ? "evinde" : "deplasmanda";
      const scan = scans.get(m.id) ?? [];
      const push = (f: Omit<Find, "m" | "side" | "team" | "row">) =>
        out.push({ ...f, m, side, team, row: scan.find((s) => s.market === f.market && s.selection === f.selection && (s.line ?? null) === f.line) });
      // KG
      if (mine.length >= minN) {
        const k = mine.filter((r) => r.goals_for > 0 && r.goals_against > 0).length;
        if (k / mine.length >= minR) push({ text: `${where} son ${mine.length} maçın ${k}'inde KG Var`, k, n: mine.length, market: "BTTS", selection: "VAR", line: null });
        else if ((mine.length - k) / mine.length >= minR) push({ text: `${where} son ${mine.length} maçın ${mine.length - k}'inde KG Yok`, k: mine.length - k, n: mine.length, market: "BTTS", selection: "YOK", line: null });
      }
      for (const d of DEFS) {
        const vals = mine.map(d.v).filter((x): x is number => x != null);
        if (vals.length < minN) continue;
        let best: { line: number; k: number; over: boolean; score: number } | null = null;
        for (const ln of d.lines) {
          const over = vals.filter((v) => v > ln).length, under = vals.length - over;
          for (const [k, isOver] of [[over, true], [under, false]] as const) {
            if (k / vals.length < minR) continue;
            // aynı oranda daha "zor" çizgiyi seç (üstte yüksek, altta düşük çizgi)
            const score = k / vals.length + (isOver ? ln : -ln) / 100;
            if (!best || score > best.score) best = { line: ln, k, over: isOver, score };
          }
        }
        if (best) push({ text: `${where} son ${vals.length} maçın ${best.k}'inde ${fl(best.line)} ${best.over ? "üst" : "alt"} ${d.label}`, k: best.k, n: vals.length, market: d.market, selection: best.over ? "ÜST" : "ALT", line: best.line });
      }
    }
  }
  return out.sort((a, b) => b.k / b.n - a.k / a.n || b.n - a.n || (b.row?.edge ?? -1) - (a.row?.edge ?? -1));
}
