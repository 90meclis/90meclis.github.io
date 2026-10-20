/*
 * Veri Laboratuvarı motoru. Tek kaynak: v_takim_mac_istatistik (takım × maç, lehte/aleyhte, iç/dış, Avrupa/Lig).
 * Yalnızca BU SEZON (1 Temmuz'dan itibaren). Ortalama yok sayılmaz: her şey maç maç seriden türetilir.
 */
import { supabase } from "./supabase";
import { NoDataError, corruptRow, leagueSlugs, nameKey, similarKey, seasonStartIso, type TeamStatRow } from "./data";
import { addDays, dayBoundsUtc, trDay } from "./format";
import { league } from "./labels";

export type StatKey = "gol" | "iy" | "kg" | "korner" | "kart" | "sut" | "isabet" | "kale";
export type Yon = "lehte" | "aleyhte" | "toplam";
export type Saha = "tum" | "ic" | "dis";
export type Kulvar = "tum" | "lig" | "avrupa";

export interface StatDef {
  k: StatKey; label: string; short: string; for: keyof LabRow | null; against: keyof LabRow | null;
  team: number[]; total: number[]; market?: string; teamMarket?: { home: string; away: string };
}
export interface LabRow extends TeamStatRow { btts?: boolean | null; venue?: string | null }

export const STATS: StatDef[] = [
  { k: "gol", label: "Gol", short: "Gol", for: "goals_for", against: "goals_against", team: [0.5, 1.5, 2.5], total: [1.5, 2.5, 3.5, 4.5], market: "OU_GOALS", teamMarket: { home: "TEAM_GOALS_HOME", away: "TEAM_GOALS_AWAY" } },
  { k: "iy", label: "İlk yarı gol", short: "İY gol", for: "ht_for", against: "ht_against", team: [0.5, 1.5], total: [0.5, 1.5, 2.5], market: "HT_OU_GOALS" },
  { k: "kg", label: "Karşılıklı gol", short: "KG", for: null, against: null, team: [], total: [0.5], market: "BTTS" },
  { k: "korner", label: "Korner", short: "Korner", for: "corners_for", against: "corners_against", team: [3.5, 4.5, 5.5, 6.5], total: [7.5, 8.5, 9.5, 10.5, 11.5], market: "CORNERS_OU" },
  { k: "kart", label: "Kart", short: "Kart", for: "cards_for", against: "cards_against", team: [0.5, 1.5, 2.5], total: [2.5, 3.5, 4.5, 5.5], market: "CARDS_OU" },
  { k: "sut", label: "Şut", short: "Şut", for: "shots_for", against: "shots_against", team: [8.5, 10.5, 12.5, 14.5], total: [19.5, 22.5, 25.5, 28.5] },
  { k: "isabet", label: "İsabetli şut", short: "İsabetli", for: "sot_for", against: "sot_against", team: [2.5, 3.5, 4.5, 5.5], total: [6.5, 7.5, 8.5, 9.5, 10.5], market: "SOT_OU" },
  { k: "kale", label: "Kale vuruşu", short: "Kale vur.", for: "goal_kicks_for", against: "goal_kicks_against", team: [5.5, 6.5, 7.5, 8.5], total: [13.5, 15.5, 17.5, 19.5], market: "GOAL_KICKS_OU" },
];
export const statDef = (k: string) => STATS.find((s) => s.k === k) ?? STATS[0];

export const YON_LABEL: Record<Yon, string> = { lehte: "Yaptığı", aleyhte: "Rakibe verdiği", toplam: "Maç toplamı" };
export const SAHA_LABEL: Record<Saha, string> = { tum: "Tüm maçlar", ic: "İç saha", dis: "Deplasman" };
export const KULVAR_LABEL: Record<Kulvar, string> = { tum: "Tümü", lig: "Lig", avrupa: "Avrupa" };

export function linesFor(s: StatDef, y: Yon): number[] {
  if (s.k === "kg") return [0.5];
  return y === "toplam" ? s.total : s.team;
}
export function defaultLine(s: StatDef, y: Yon): number {
  const l = linesFor(s, y);
  return l[Math.floor((l.length - 1) / 2)];
}

/** Bir satırın seçili istatistik değeri (null = kaynakta yok). KG: 1 = var, 0 = yok. */
export function valueOf(r: LabRow, s: StatDef, y: Yon): number | null {
  if (s.k === "kg") {
    if (r.btts !== undefined && r.btts !== null) return r.btts ? 1 : 0;
    return r.goals_for > 0 && r.goals_against > 0 ? 1 : 0;
  }
  const f = r[s.for!] as number | null, a = r[s.against!] as number | null;
  if (y === "lehte") return f ?? null;
  if (y === "aleyhte") return a ?? null;
  return f === null || f === undefined || a === null || a === undefined ? null : f + a;
}

const isHome = (r: LabRow) => r.side === "home";
export function filterRows(rows: LabRow[], saha: Saha, kulvar: Kulvar): LabRow[] {
  return rows.filter((r) => (saha === "tum" || (saha === "ic") === isHome(r)) && (kulvar === "tum" || (kulvar === "avrupa") === (r.competition === "Avrupa")));
}

export interface Series { rows: LabRow[]; vals: (number | null)[]; known: number[] }
/** Eskiden yeniye seri. */
export function series(rows: LabRow[], s: StatDef, y: Yon): Series {
  const asc = [...rows].sort((a, b) => a.kickoff_at.localeCompare(b.kickoff_at));
  const vals = asc.map((r) => valueOf(r, s, y));
  return { rows: asc, vals, known: vals.filter((v): v is number => v !== null) };
}

export const avg = (v: number[]) => (v.length ? v.reduce((a, b) => a + b, 0) / v.length : null);
export function hits(v: number[], line: number, over = true) { return v.filter((x) => (over ? x > line : x < line)).length; }

/** Güncel seri: en yeni maçtan geriye, koşulun art arda tuttuğu maç sayısı. */
export function streak(v: number[], line: number, over: boolean): number {
  let n = 0;
  for (let i = v.length - 1; i >= 0; i--) { if (over ? v[i] > line : v[i] < line) n++; else break; }
  return n;
}

// ------------------------------------------------------------------------------------------------
// Veri çekme
// ------------------------------------------------------------------------------------------------
type Res = PromiseLike<{ data: unknown; error: { message: string } | null }>;
function db() { if (!supabase) throw new NoDataError("no-client"); return supabase; }
async function paged<T>(make: () => { range: (a: number, b: number) => Res }, max = 20000): Promise<T[]> {
  const out: T[] = [];
  for (let from = 0; from < max; from += 1000) {
    const { data, error } = await make().range(from, from + 999);
    if (error) throw new Error(error.message);
    const page = (data ?? []) as T[];
    out.push(...page);
    if (page.length < 1000) break;
  }
  return out;
}
const V = "v_takim_mac_istatistik";
const COLS = "match_id,kickoff_at,league,competition,side,team_id,team_slug,team_name,opponent,goals_for,goals_against,ht_for,ht_against,btts,corners_for,corners_against,cards_for,cards_against,shots_for,shots_against,sot_for,sot_against,goal_kicks_for,goal_kicks_against,xg_for,xg_against,asama";
const EURO = new Set(["CL", "EL", "ECL"]);
export const isEuroLeague = (lg: string) => EURO.has(lg);

/** Yanlış ad eşlemesiyle başka takımın kimliğine yazılmış maçları ayıklar (Maç Merkezi ile aynı kural). */
async function clean(rows: LabRow[]): Promise<LabRow[]> {
  const ids = [...new Map(rows.map((r) => [r.match_id, r])).values()];
  const bad = new Set<string>();
  await Promise.all(ids.map(async (r) => {
    const home = r.side === "home" ? r.team_name : r.opponent, away = r.side === "home" ? r.opponent : r.team_name;
    if (await corruptRow(r.match_id, r.league, home, away)) bad.add(r.match_id);
  }));
  // Satır düzeyi: takım adı ligdeki BAŞKA bir takımın anahtarıysa (ör. kimlik samsunspor, ad "Trabzonspor") satır o takıma ait değildir
  const lgs = [...new Set(rows.map((r) => r.league))];
  const sl = new Map(await Promise.all(lgs.map(async (l) => [l, await leagueSlugs(l)] as const)));
  return rows.filter((r) => {
    if (bad.has(r.match_id)) return false;
    const k = nameKey(r.team_name);
    return k === r.team_slug || !sl.get(r.league)?.has(k) || similarKey(k, r.team_slug);
  });
}

/** Bir ligin bu sezonki bütün takım × maç satırları + (yerel ligse) o takımların bu sezonki Avrupa maçları. */
export async function leagueRows(lg: string): Promise<LabRow[]> {
  const since = seasonStartIso();
  const base = await paged<LabRow>(() => db().from(V).select(COLS).eq("league", lg).gte("kickoff_at", since).order("kickoff_at", { ascending: false }));
  let euro: LabRow[] = [];
  if (!EURO.has(lg)) {
    const slugs = [...new Set(base.map((r) => r.team_slug))];
    for (let i = 0; i < slugs.length; i += 40) {
      const part = slugs.slice(i, i + 40);
      euro.push(...await paged<LabRow>(() => db().from(V).select(COLS).eq("competition", "Avrupa").in("team_slug", part).gte("kickoff_at", since)));
    }
  } else {
    // Avrupa kupası seçildiyse takımların yerel lig maçları da (Avrupa/Lig ayrımıyla) okunur
    const slugs = [...new Set(base.map((r) => r.team_slug))];
    for (let i = 0; i < slugs.length; i += 40) {
      const part = slugs.slice(i, i + 40);
      euro.push(...await paged<LabRow>(() => db().from(V).select(COLS).eq("competition", "Lig").in("team_slug", part).gte("kickoff_at", since)));
    }
  }
  euro = euro.filter((r) => r.league !== lg);
  return clean([...base, ...euro]);
}

/** Bugün ve yarın oynanacak maçlar + iki takımın bu sezonki bütün satırları (Seri Avcısı · bülten kapsamı). */
export interface Fixture { id: string; league: string; kickoff_at: string; home_team_id: string; away_team_id: string; home_name: string; away_name: string }
/** maxFixtures: yalnızca öncelikli liglerden en çok bu kadar maç (ana sayfa için hafif sorgu). */
export async function bulletinRows(maxFixtures?: number): Promise<{ fixtures: Fixture[]; rows: LabRow[] }> {
  const today = trDay();
  const [lo] = dayBoundsUtc(today), [, hi] = dayBoundsUtc(addDays(today, 1));
  const now = new Date().toISOString();
  const all = await paged<Fixture>(() => db().from("matches").select("id,league,kickoff_at,home_team_id,away_team_id,home_name,away_name")
    .gte("kickoff_at", lo > now ? lo : now).lt("kickoff_at", hi).order("kickoff_at"));
  const fx = maxFixtures ? [...all].sort((a, b) => league(a.league).order - league(b.league).order || a.kickoff_at.localeCompare(b.kickoff_at)).slice(0, maxFixtures) : all;
  const slugOf = (id: string) => id.slice(id.indexOf(":") + 1);
  const slugs = [...new Set(fx.flatMap((f) => [slugOf(f.home_team_id), slugOf(f.away_team_id)]))];
  const rows: LabRow[] = [];
  const since = seasonStartIso();
  const chunks: string[][] = [];
  for (let i = 0; i < slugs.length; i += 30) chunks.push(slugs.slice(i, i + 30));
  const parts = await Promise.all(chunks.map((c) => paged<LabRow>(() => db().from(V).select(COLS).in("team_slug", c).gte("kickoff_at", since).lt("kickoff_at", now))));
  for (const p of parts) rows.push(...p);
  return { fixtures: fx, rows: await clean(rows) };
}

export interface ScanRow { match_id: string; market: string; selection: string; line: number | null; p_model: number | null; odds: number | null; edge: number | null; deger: boolean | null; secildi: boolean | null }
export async function scanFor(ids: string[]): Promise<ScanRow[]> {
  const out: ScanRow[] = [];
  for (let i = 0; i < ids.length; i += 60) {
    try {
      const part = ids.slice(i, i + 60);
      out.push(...await paged<ScanRow>(() => db().from("v_bot_tarama").select("match_id,market,selection,line,p_model,odds,edge,deger,secildi").in("match_id", part)));
    } catch { /* görünüm yoksa değer bayrağı gösterilmez */ }
  }
  return out;
}

export interface TeamLite { id: string; name: string; league: string }
export const allTeams = () => paged<TeamLite>(() => db().from("teams").select("id,name,league").order("name"));

// ------------------------------------------------------------------------------------------------
// Türetilmiş tablolar
// ------------------------------------------------------------------------------------------------
export interface TeamInfo { slug: string; id: string; name: string }
export function teamsOf(rows: LabRow[], lg: string): TeamInfo[] {
  const m = new Map<string, TeamInfo>();
  for (const r of rows) if (r.league === lg && !m.has(r.team_slug)) m.set(r.team_slug, { slug: r.team_slug, id: r.team_id, name: r.team_name });
  return [...m.values()].sort((a, b) => a.name.localeCompare(b.name, "tr"));
}
export const rowsOfTeam = (rows: LabRow[], slug: string) => rows.filter((r) => r.team_slug === slug);

export interface Leader { t: TeamInfo; n: number; avg: number; hit: number; last: (number | null)[] }
export function leaderboard(rows: LabRow[], teams: TeamInfo[], s: StatDef, y: Yon, saha: Saha, kulvar: Kulvar, line: number, minN = 3): Leader[] {
  const out: Leader[] = [];
  for (const t of teams) {
    const sr = series(filterRows(rowsOfTeam(rows, t.slug), saha, kulvar), s, y);
    if (sr.known.length < minN) continue;
    out.push({ t, n: sr.known.length, avg: avg(sr.known)!, hit: hits(sr.known, line) / sr.known.length, last: sr.vals.slice(-8) });
  }
  return out;
}

export interface Streak {
  t: TeamInfo; s: StatDef; y: Yon; saha: Saha; line: number; over: boolean; run: number; hit10: number; n10: number; base: number; score: number;
  fixture?: Fixture; side?: "home" | "away"; vals: number[];
}
/**
 * Seri Avcısı. Her takım × istatistik × yön × çizgi için en yeni maçtan geriye art arda tutan seri. Önemsiz seriler
 * (ör. %95'i zaten tutan "0,5 üst") taban oranla cezalandırılır: puan = seri × (1 − taban oran).
 */
export function hunt(rows: LabRow[], teams: { t: TeamInfo; saha: Saha; fixture?: Fixture; side?: "home" | "away" }[], minRun = 4): Streak[] {
  // Taban oranlar: kapsamdaki bütün satırlarda koşulun tutma oranı
  const baseCache = new Map<string, number>();
  const base = (s: StatDef, y: Yon, line: number, over: boolean) => {
    const k = `${s.k}|${y}|${line}|${over}`;
    if (!baseCache.has(k)) {
      const v = rows.map((r) => valueOf(r, s, y)).filter((x): x is number => x !== null);
      baseCache.set(k, v.length ? hits(v, line, over) / v.length : 0.5);
    }
    return baseCache.get(k)!;
  };
  const out: Streak[] = [];
  for (const { t, saha, fixture, side } of teams) {
    const tr = filterRows(rowsOfTeam(rows, t.slug), saha, "tum");
    for (const s of STATS) {
      const yons: Yon[] = s.k === "kg" ? ["toplam"] : ["toplam", "lehte", "aleyhte"];
      let best: Streak | null = null;
      for (const y of yons) {
        const v = series(tr, s, y).known;
        if (v.length < minRun) continue;
        for (const line of linesFor(s, y)) {
          for (const over of [true, false]) {
            const run = streak(v, line, over);
            if (run < minRun) continue;
            const b = base(s, y, line, over);
            if (b > 0.85) continue;
            const last = v.slice(-10);
            const score = run * (1 - b) + (hits(last, line, over) / last.length) * 2;
            if (!best || score > best.score) best = { t, s, y, saha, line, over, run, hit10: hits(last, line, over), n10: last.length, base: b, score, fixture, side, vals: v.slice(-10) };
          }
        }
      }
      if (best) out.push(best);
    }
  }
  return out.sort((a, b) => b.score - a.score);
}

/** Seri ile piyasa: bu maçın taramasında karşılık gelen pazar var mı, değer var mı? */
export function streakMarket(st: Streak, scan: ScanRow[]): ScanRow | null {
  if (!st.fixture) return null;
  let market: string | undefined;
  if (st.y === "toplam") market = st.s.market;
  else if (st.s.k === "gol" && st.side) {
    // Takımın kendi golü (lehte) → kendi takım gol pazarı; rakibe verdiği → rakibin takım gol pazarı
    const own = st.y === "lehte" ? st.side : st.side === "home" ? "away" : "home";
    market = own === "home" ? st.s.teamMarket!.home : st.s.teamMarket!.away;
  }
  if (!market) return null;
  const sel = st.s.k === "kg" ? (st.over ? "VAR" : "YOK") : st.over ? "ÜST" : "ALT";
  return scan.find((r) => r.match_id === st.fixture!.id && r.market === market && r.selection === sel && (st.s.k === "kg" || Number(r.line) === st.line)) ?? null;
}

export function streakText(st: Streak): string {
  const lineTxt = st.s.k === "kg" ? (st.over ? "KG var" : "KG yok") : `${String(st.line).replace(".", ",")} ${st.over ? "üst" : "alt"}`;
  const what = st.s.k === "kg" ? "" : ` ${st.y === "toplam" ? "maç toplamı" : st.y === "lehte" ? "yaptığı" : "rakibe verdiği"} ${st.s.label.toLocaleLowerCase("tr-TR")}`;
  const where = st.saha === "ic" ? "evindeki" : st.saha === "dis" ? "deplasmandaki" : "";
  return `${where ? where + " " : ""}son ${st.run} maçında art arda${what} ${lineTxt}`.trim();
}

// ------------------------------------------------------------------------------------------------
// Puan durumu (bitmiş lig maçlarından)
// ------------------------------------------------------------------------------------------------
export interface Stand { t: TeamInfo; o: number; g: number; b: number; m: number; ag: number; yg: number; p: number; form: string[] }
export function standings(rows: LabRow[], lg: string): Stand[] {
  const m = new Map<string, Stand>();
  const asc = rows.filter((r) => r.league === lg && r.competition === "Lig").sort((a, b) => a.kickoff_at.localeCompare(b.kickoff_at));
  for (const r of asc) {
    if (!m.has(r.team_slug)) m.set(r.team_slug, { t: { slug: r.team_slug, id: r.team_id, name: r.team_name }, o: 0, g: 0, b: 0, m: 0, ag: 0, yg: 0, p: 0, form: [] });
    const s = m.get(r.team_slug)!;
    s.o++; s.ag += r.goals_for; s.yg += r.goals_against;
    if (r.goals_for > r.goals_against) { s.g++; s.p += 3; s.form.push("G"); } else if (r.goals_for < r.goals_against) { s.m++; s.form.push("M"); } else { s.b++; s.p++; s.form.push("B"); }
  }
  return [...m.values()].sort((a, b) => b.p - a.p || (b.ag - b.yg) - (a.ag - a.yg) || b.ag - a.ag || a.t.name.localeCompare(b.t.name, "tr"));
}

/** "8'inde", "2'sinde", "6'sında", "10'unda" — sayıya göre bulunma eki. */
export function inde(n: number): string {
  const last = n % 10, tens = n % 100;
  if (n === 0) return "0'ında";
  if (last === 0) return `${n}'${({ 10: "unda", 20: "sinde", 30: "unda", 40: "ında", 50: "sinde", 60: "ında", 70: "inde", 80: "inde", 90: "ında" } as Record<number, string>)[tens] ?? "unda"}`;
  return `${n}'${["", "inde", "sinde", "ünde", "ünde", "inde", "sında", "sinde", "inde", "unda"][last]}`;
}
