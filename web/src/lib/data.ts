import { supabase } from "./supabase";
import { dayBoundsUtc, addDays, trDay } from "./format";
import type {
  Agenda, Analysis, Coupon, Injury, Lineup, Match, MatchStat, Prediction, QueueItem, Team, Trend, Weather,
} from "./types";

export class NoDataError extends Error {}

type Res = PromiseLike<{ data: unknown; error: { message: string } | null }>;
interface Sel { range: (from: number, to: number) => Res }

/**
 * Kural: Günün Kararı'ndaki bir maç Meclis Görüşü olamaz. Kural konmadan önce kaydedilmiş (19.10.2026) bu tür tekliler
 * veritabanında değiştirilmeden durur (defter değiştirilemez) ama hiçbir herkese açık listeye, sayıma, isabet ve K/Z'ye girmez.
 */
export function publicPreds(rows: Prediction[]): Prediction[] {
  const gk = new Set(rows.filter((p) => p.tag === "gunun_karari").map((p) => p.match_id));
  return rows.filter((p) => !(p.tag === "meclis_gorusu" && gk.has(p.match_id)));
}
const pub = (q: Promise<Prediction[]>) => q.then(publicPreds);

function db() {
  if (!supabase) throw new NoDataError("no-client");
  return supabase;
}

async function run<T>(q: Res): Promise<T[]> {
  const { data, error } = await q;
  if (error) throw new Error(error.message);
  return (data ?? []) as T[];
}

/** 1000 satır sınırını sayfalayarak aşar. */
async function all<T>(make: () => Sel, max = 20000): Promise<T[]> {
  const out: T[] = [];
  for (let from = 0; from < max; from += 1000) {
    const page = await run<T>(make().range(from, from + 999));
    out.push(...page);
    if (page.length < 1000) break;
  }
  return out;
}

const MATCH_LIST = "id,league,kickoff_at,home_team_id,away_team_id,home_name,away_name,home_goals,away_goals,score,ht_home_goals,ht_away_goals,status,durum,venue,referee,city,odds,missing_fields,completeness,updated_at,season,canli:sources->_canli";

export async function leaguesInDb(): Promise<string[]> {
  const since = new Date(Date.now() - 45 * 86400000).toISOString();
  const [t, m] = await Promise.all([
    all<{ league: string }>(() => db().from("teams").select("league")),
    all<{ league: string }>(() => db().from("matches").select("league").gte("kickoff_at", since)),
  ]);
  return [...new Set([...t, ...m].map((r) => r.league))];
}

export async function matchDays(fromDay: string, toDay: string): Promise<Record<string, Record<string, number>>> {
  const [lo] = dayBoundsUtc(fromDay);
  const [, hi] = dayBoundsUtc(toDay);
  const rows = await all<{ league: string; kickoff_at: string }>(() =>
    db().from("matches").select("league,kickoff_at").gte("kickoff_at", lo).lt("kickoff_at", hi).order("kickoff_at"),
  );
  const out: Record<string, Record<string, number>> = {};
  for (const r of rows) {
    const d = trDay(r.kickoff_at);
    out[d] ??= {};
    out[d][r.league] = (out[d][r.league] ?? 0) + 1;
  }
  return out;
}

export async function matchesOnDay(day: string): Promise<Match[]> {
  const [lo, hi] = dayBoundsUtc(day);
  const rows = await all<Match>(() => db().from("matches").select(MATCH_LIST).gte("kickoff_at", lo).lt("kickoff_at", hi).order("kickoff_at"));
  // Yanlış ad eşlemesiyle başka takımın kimliğine yazılmış satırları ayıkla (yalnız ad ↔ kimlik uyuşmayanlar denetlenir)
  const sus = rows.filter((m) => { const p = m.id.split(":"); return p.length >= 4 && (nameKey(m.home_name) !== p[2] || nameKey(m.away_name) !== p[3]); });
  await prefetchLeagueSlugs(sus.map((m) => m.league));
  const flags = await Promise.all(rows.map((m) => {
    const p = m.id.split(":");
    return p.length >= 4 && (nameKey(m.home_name) !== p[2] || nameKey(m.away_name) !== p[3])
      ? corruptRow(m.id, m.league, m.home_name, m.away_name) : Promise.resolve(false);
  }));
  return rows.filter((_, i) => !flags[i]);
}

export async function matchesByIds(ids: string[]): Promise<Match[]> {
  if (!ids.length) return [];
  const out: Match[] = [];
  for (let i = 0; i < ids.length; i += 100) {
    out.push(...(await run<Match>(db().from("matches").select(MATCH_LIST).in("id", ids.slice(i, i + 100)))));
  }
  return out;
}

export async function match(id: string): Promise<Match | null> {
  const r = await run<Match>(db().from("matches").select("*").eq("id", id).limit(1));
  return r[0] ?? null;
}

/** Bu sezonun başlangıcı (1 Temmuz, UTC). Kullanıcı: "geçmiş sezon değil bu sezon genelinde". */
export function seasonStartIso(ref: Date = new Date()): string {
  const y = ref.getUTCMonth() >= 6 ? ref.getUTCFullYear() : ref.getUTCFullYear() - 1;
  return `${y}-07-01T00:00:00Z`;
}

/** Takımın bu sezonki son maçları. Avrupa kupası takımı için yerel lig maçları da (aynı kulüp) dahil edilir. */
export async function teamHistory(teamId: string, beforeIso: string, limit = 10): Promise<Match[]> {
  let ids = [teamId];
  if (/^(CL|EL|ECL):/.test(teamId)) {
    const slug = teamId.slice(teamId.indexOf(":") + 1);
    const same = await run<{ id: string }>(db().from("teams").select("id").like("id", `%:${slug}`));
    ids = [...new Set([teamId, ...same.map((x) => x.id)])];
  }
  const list = ids.map((x) => `"${x}"`).join(",");
  return run<Match>(
    db().from("matches").select(MATCH_LIST)
      .or(`home_team_id.in.(${list}),away_team_id.in.(${list})`)
      .gte("kickoff_at", seasonStartIso(new Date(beforeIso))).lt("kickoff_at", beforeIso).not("home_goals", "is", null)
      .order("kickoff_at", { ascending: false }).limit(limit),
  );
}

export async function headToHead(a: string, b: string, beforeIso: string): Promise<Match[]> {
  return run<Match>(
    db().from("matches").select(MATCH_LIST)
      .or(`and(home_team_id.eq."${a}",away_team_id.eq."${b}"),and(home_team_id.eq."${b}",away_team_id.eq."${a}")`)
      .lt("kickoff_at", beforeIso).not("home_goals", "is", null)
      .order("kickoff_at", { ascending: false }).limit(8),
  );
}

export async function statsFor(matchIds: string[]): Promise<MatchStat[]> {
  if (!matchIds.length) return [];
  return run<MatchStat>(db().from("match_stats").select("*").in("match_id", matchIds));
}

export async function injuriesFor(m: Match): Promise<Injury[]> {
  const byMatch = await run<Injury>(db().from("injuries").select("*").eq("match_id", m.id));
  if (byMatch.length) return byMatch;
  // Maça bağlanmamış güncel liste: son 10 gün içinde okunan takım kayıtları
  const since = new Date(Date.now() - 10 * 86400000).toISOString();
  return run<Injury>(
    db().from("injuries").select("*").in("team_id", [m.home_team_id, m.away_team_id]).is("match_id", null).gte("fetched_at", since),
  );
}

export const lineupsFor = (id: string) => run<Lineup>(db().from("lineups").select("*").eq("match_id", id));
export const weatherFor = (id: string) => run<Weather>(db().from("weather").select("*").eq("match_id", id).limit(1));
export const analysisFor = (id: string) =>
  run<Analysis>(db().from("analyses").select("*").eq("match_id", id).order("created_at", { ascending: false }).limit(1));
export const predictionsForMatch = (id: string) =>
  pub(run<Prediction>(db().from("predictions").select("*").eq("match_id", id).order("recorded_at")));
export const newsForMatch = (id: string) =>
  run<Agenda>(db().from("agenda").select("*").contains("match_ids", JSON.stringify([id])).order("published_at", { ascending: false }).limit(12));
export const teamsIn = (ids: string[]) => run<Team>(db().from("teams").select("*").in("id", ids));

export const allPredictions = () =>
  pub(all<Prediction>(() => db().from("predictions").select("*").order("kickoff_at", { ascending: false })));
export const allCoupons = () => all<Coupon>(() => db().from("coupons").select("*").order("coupon_date", { ascending: false }));
export const queue = () => all<QueueItem>(() => db().from("analysis_queue").select("*"));

export async function upcomingPredictions(): Promise<Prediction[]> {
  const [lo] = dayBoundsUtc(addDays(trDay(), -1));
  return pub(all<Prediction>(() => db().from("predictions").select("*").gte("kickoff_at", lo).order("kickoff_at")));
}

export const news = (limit = 400) =>
  all<Agenda>(() => db().from("agenda").select("*").order("published_at", { ascending: false }), limit);

export const trends = (lg: string) => all<Trend>(() => db().from("trends").select("*").eq("league", lg));

/** Güncel sezonun maçları (Avrupa takvimi: 1 Temmuz'dan itibaren). */
export async function seasonMatches(lg: string): Promise<Match[]> {
  return all<Match>(() =>
    db().from("matches").select(MATCH_LIST).eq("league", lg).gte("kickoff_at", seasonStartIso()).order("kickoff_at", { ascending: false }),
  );
}

export async function predictionsForMatches(ids: string[]): Promise<Prediction[]> {
  if (!ids.length) return [];
  const out: Prediction[] = [];
  for (let i = 0; i < ids.length; i += 100) out.push(...(await run<Prediction>(db().from("predictions").select("*").in("match_id", ids.slice(i, i + 100)))));
  return publicPreds(out);
}


/** Ortak bülteni: günün maçları ve her maçın son analizi (yalnızca botun seçim için gereken alanları). */
export interface BotAnalysis {
  match_id: string; created_at: string; ready: boolean | null; basis: string | null;
  markets: import("./types").MarketRow[] | null; scenarios: { ad: string; anlatım: string; olasılık: number | null }[] | null;
  model_matches: { home?: number; away?: number } | null; min_team_matches: number | null;
  lambdas: { home: number; away: number } | null; injury_effect: Record<string, unknown> | null;
  form: { home?: import("./types").FormRow[]; away?: import("./types").FormRow[] } | null; top_scores: [string, number][] | null;
}
export async function bulletin(day: string): Promise<{ matches: Match[]; analyses: Record<string, BotAnalysis> }> {
  const matches = await matchesOnDay(day);
  return { matches, analyses: await analysesLite(matches.map((m) => m.id)) };
}

/** Maçların son analizleri (yalnızca liste/bot için gereken alanlar). */
export async function analysesLite(ids: string[], light = false): Promise<Record<string, BotAnalysis>> {
  const cols = light
    ? "match_id,created_at,ready:payload->ready,basis:payload->>basis,markets:payload->markets,model_matches:payload->model_matches,min_team_matches:payload->min_team_matches"
    : "match_id,created_at,ready:payload->ready,basis:payload->>basis,markets:payload->markets,scenarios:payload->scenarios,model_matches:payload->model_matches,min_team_matches:payload->min_team_matches,lambdas:payload->lambdas,injury_effect:payload->injury_effect,form:payload->form,top_scores:payload->top_scores";
  const analyses: Record<string, BotAnalysis> = {};
  const chunks: string[][] = [];
  for (let i = 0; i < ids.length; i += 40) chunks.push(ids.slice(i, i + 40));
  // parçalar paralel (sırayla beklemek LCP'yi saniyelerce geciktiriyordu)
  const parts = await Promise.all(chunks.map((c) => run<BotAnalysis>(
    db().from("analyses").select(cols).in("match_id", c).order("created_at", { ascending: false }))));
  for (const rows of parts) for (const r of rows) if (!analyses[r.match_id]) analyses[r.match_id] = r;
  return analyses;
}

export const predictionsBetween = (fromIso: string, toIso: string) =>
  pub(all<Prediction>(() => db().from("predictions").select("*").gte("kickoff_at", fromIso).lt("kickoff_at", toIso).order("kickoff_at")));

/** Botun kaydettiği bülten (v_bot_bulten). Görünüm henüz yoksa null döner; sayfa analizlerden türetir. */
export interface BotBultenRow {
  id: string; match_id: string; kickoff_at: string; league: string | null; home_name: string | null; away_name: string | null;
  market: string; selection: string; line: number | null; probability: number; odds: number | null; fair_odds: number | null;
  edge: number | null; confidence: number | null; kind: string | null; arsiv_durumu: string | null; computed_at: string;
}
let botBultenMissing = false;
export async function botBulten(day: string): Promise<BotBultenRow[] | null> {
  if (botBultenMissing) return null;
  const [lo, hi] = dayBoundsUtc(day);
  const { data, error } = await db().from("v_bot_bulten").select("*").gte("kickoff_at", lo).lt("kickoff_at", hi).order("kickoff_at");
  if (error) { botBultenMissing = true; return null; }
  return (data ?? []) as BotBultenRow[];
}

// ---------------------------------------------------------------------------------------------
// Maç dosyası. Takım kimliği "lig:slug"; aynı kulübün lig, Avrupa ve kupa maçları slug ile birleşir
// (v_takim_mac_istatistik ile aynı kural). Yalnızca BU SEZON (1 Temmuz'dan itibaren), yalnızca bitmiş maçlar.
// ---------------------------------------------------------------------------------------------
export const slugOf = (id: string) => id.slice(id.indexOf(":") + 1);

export async function teamSeason(teamId: string, beforeIso: string): Promise<Match[]> {
  const same = await run<{ id: string }>(db().from("teams").select("id").like("id", `%:${slugOf(teamId)}`));
  const ids = [...new Set([teamId, ...same.map((x) => x.id)])].map((x) => `"${x}"`).join(",");
  return run<Match>(
    db().from("matches").select(MATCH_LIST)
      .or(`home_team_id.in.(${ids}),away_team_id.in.(${ids})`)
      .gte("kickoff_at", seasonStartIso(new Date(beforeIso))).lt("kickoff_at", beforeIso).not("home_goals", "is", null)
      .order("kickoff_at", { ascending: false }).limit(80),
  );
}

/** Aralarındaki maçlar (bütün kulvarlar, veri havuzundaki bütün sezonlar). */
export async function h2hAll(a: string, b: string, beforeIso: string): Promise<Match[]> {
  const sa = slugOf(a), sb = slugOf(b);
  return run<Match>(
    db().from("matches").select(MATCH_LIST)
      .or(`and(home_team_id.like.*:${sa},away_team_id.like.*:${sb}),and(home_team_id.like.*:${sb},away_team_id.like.*:${sa})`)
      .lt("kickoff_at", beforeIso).not("home_goals", "is", null)
      .order("kickoff_at", { ascending: false }).limit(10),
  );
}

/** Hakemin bu sezon yönettiği bitmiş maçlar. */
export async function refereeSeason(name: string, beforeIso: string): Promise<Match[]> {
  return run<Match>(
    db().from("matches").select(MATCH_LIST).eq("referee", name)
      .gte("kickoff_at", seasonStartIso(new Date(beforeIso))).lt("kickoff_at", beforeIso).not("home_goals", "is", null)
      .order("kickoff_at", { ascending: false }).limit(60),
  );
}

/** Bir ligin bu sezon oynanmış maçları (puan durumu, benzer maçlar). */
export async function leaguePlayed(lg: string, beforeIso: string): Promise<Match[]> {
  return all<Match>(() =>
    db().from("matches").select(MATCH_LIST).eq("league", lg)
      .gte("kickoff_at", seasonStartIso(new Date(beforeIso))).lt("kickoff_at", beforeIso).not("home_goals", "is", null)
      .order("kickoff_at", { ascending: false }),
  );
}

// ---------------------------------------------------------------------------------------------
// Yanlış takım eşlemesi koruması. Bir maç satırında bir tarafın ADI ligdeki BAŞKA bir takımın anahtarına denk
// geliyor ve kimlikteki takıma benzemiyorsa (ör. ad "Trabzonspor", kimlik samsunspor) satır o takımın verisine
// katılmaz. Kaynak tarafı düzeltildi (meclis/pool.py); veritabanı temizlenene kadar sayfa bu satırları atlar.
// ---------------------------------------------------------------------------------------------
const DROP = new Set(["fc", "fk", "sk", "jk", "afc", "cf", "ac", "as", "ssc", "sc", "bk", "if", "cd", "ud", "rc", "rcd", "kulubu", "futbol", "the", "club", "calcio", "sv", "vfb", "vfl", "tsg", "1", "de"]);
export function nameKey(name: string): string {
  const s = name.replace(/ı/g, "i").replace(/İ/g, "I").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase()
    .replace(/&/g, " ").replace(/'/g, "").replace(/\./g, " ");
  return s.split(/[^a-z0-9]+/).filter((t) => t && !DROP.has(t) && !/^(18|19|20)\d\d$/.test(t)).join("");
}
const GEN = ["spor", "united", "town", "city", "rovers", "athletic", "afc", "fc", "sk", "fk", "if"];
function core(k: string): string {
  let ch = true;
  while (ch) { ch = false; for (const g of GEN) if (k.endsWith(g) && k.length - g.length >= 3) { k = k.slice(0, -g.length); ch = true; } }
  return k;
}
function lcs(a: string, b: string): { size: number; ia: number; ib: number } {
  let best = { size: 0, ia: 0, ib: 0 };
  for (let i = 0; i < a.length; i++) for (let j = 0; j < b.length; j++) {
    let k = 0; while (i + k < a.length && j + k < b.length && a[i + k] === b[j + k]) k++;
    if (k > best.size) best = { size: k, ia: i, ib: j };
  }
  return best;
}
export function similarKey(a: string, b: string): boolean {
  const ca = core(a), cb = core(b);
  if (ca === cb || ca.slice(0, 4) === cb.slice(0, 4) || ca.includes(cb) || cb.includes(ca)) return true;
  const m = lcs(ca, cb);
  const aligned = (m.ia === 0 && m.ib === 0) || (m.ia + m.size === ca.length && m.ib + m.size === cb.length);
  return (m.size >= 5 && aligned) || m.size >= 7;
}
const slugCache = new Map<string, Promise<Set<string>>>();
export function leagueSlugs(lg: string): Promise<Set<string>> {
  if (!slugCache.has(lg)) {
    slugCache.set(lg, all<{ id: string }>(() => db().from("teams").select("id").eq("league", lg))
      .then((r) => new Set(r.map((x) => slugOf(x.id)))).catch(() => new Set<string>()));
  }
  return slugCache.get(lg)!;
}
/** Birden çok ligin takım anahtarlarını TEK sorguda önbelleğe alır (lig başına ayrı istek yerine). */
export function prefetchLeagueSlugs(lgs: string[]): Promise<void> {
  const need = [...new Set(lgs)].filter((l) => l && !slugCache.has(l));
  if (!need.length) return Promise.resolve();
  const q = all<{ id: string; league: string }>(() => db().from("teams").select("id,league").in("league", need).order("id"))
    .then((r) => { const m = new Map<string, Set<string>>(need.map((l) => [l, new Set<string>()])); for (const x of r) m.get(x.league)?.add(slugOf(x.id)); return m; })
    .catch(() => new Map<string, Set<string>>());
  for (const l of need) slugCache.set(l, q.then((m) => m.get(l) ?? new Set<string>()));
  return q.then(() => undefined);
}
/** id "LG:tarih:evslug:depslug" ve adlar; yanlış eşlenmiş satırsa true. */
export async function corruptRow(id: string, league: string, homeName: string, awayName: string): Promise<boolean> {
  const parts = id.split(":");
  if (parts.length < 4) return false;
  const slugs = await leagueSlugs(league);
  return ([[parts[2], homeName], [parts[3], awayName]] as const).some(([sl, nm]) => {
    const k = nameKey(nm);
    return k !== sl && slugs.has(k) && !similarKey(k, sl);
  });
}
export async function dropCorrupt<T extends { id: string; league: string; home_name: string; away_name: string }>(rows: T[]): Promise<T[]> {
  await prefetchLeagueSlugs(rows.map((r) => r.league));
  const flags = await Promise.all(rows.map((r) => corruptRow(r.id, r.league, r.home_name, r.away_name)));
  return rows.filter((_, i) => !flags[i]);
}

// ---------------------------------------------------------------------------------------------
// Maç sayfası görünümleri (2026-10-20 geçişi). Görünüm yoksa ya da hata verirse null → ham hesap kullanılır.
// ---------------------------------------------------------------------------------------------
export interface TeamStatRow {
  match_id: string; kickoff_at: string; league: string; competition: "Avrupa" | "Lig"; side: "home" | "away";
  team_id: string; team_slug: string; team_name: string; opponent: string; goals_for: number; goals_against: number;
  ht_for: number | null; ht_against: number | null; corners_for: number | null; corners_against: number | null;
  cards_for: number | null; cards_against: number | null; shots_for: number | null; shots_against: number | null;
  sot_for: number | null; sot_against: number | null; goal_kicks_for: number | null; goal_kicks_against: number | null;
  xg_for: number | null; xg_against: number | null; referee: string | null; asama: string | null;
}
async function viewOrNull<T>(make: () => Res): Promise<T[] | null> {
  try { return await run<T>(make()); } catch { return null; }
}
export const teamStatRows = (teamId: string, beforeIso: string) =>
  viewOrNull<TeamStatRow>(() => db().from("v_takim_mac_istatistik").select("*").eq("team_slug", slugOf(teamId))
    .gte("kickoff_at", seasonStartIso(new Date(beforeIso))).lt("kickoff_at", beforeIso).order("kickoff_at", { ascending: false }).limit(80));

export interface StandRow { league: string; team_id?: string; team_slug?: string; team_name: string; o: number; g: number; b: number; m: number; ag: number; yg: number; av: number; puan: number; sira: number }
export const leagueTableView = (lg: string) =>
  viewOrNull<StandRow>(() => db().from("v_puan_durumu").select("*").eq("league", lg).order("sira"));
export const europeTableView = (lg: string) =>
  viewOrNull<StandRow>(() => db().from("v_avrupa_puan_durumu").select("*").eq("league", lg).order("sira"));

export interface RestRow { match_id: string; side: "home" | "away"; team_name: string; dinlenme_gun: number | null; son14_mac: number }
export const restView = (matchId: string) =>
  viewOrNull<RestRow>(() => db().from("v_dinlenme").select("*").eq("match_id", matchId));

export interface OddsMove { match_id: string; acilis: Record<string, Record<string, number | string>>; acilis_zamani: string; guncel: Record<string, Record<string, number | string>>; guncel_zamani: string; goruntu: number }
export const oddsMoveView = (matchId: string) =>
  viewOrNull<OddsMove>(() => db().from("v_oran_hareketi").select("*").eq("match_id", matchId).limit(1));
export interface OddsSnap { taken_at: string; odds: Record<string, Record<string, number | string>> }
export const oddsSnapshots = (matchId: string) =>
  viewOrNull<OddsSnap>(() => db().from("odds_snapshots").select("taken_at,odds").eq("match_id", matchId).order("taken_at").limit(200));

/** Lig kodu → ad/ülke (leagues tablosu). */
export async function leagueNames(): Promise<{ code: string; name: string | null; country: string | null; cup: boolean | null }[]> {
  return all(() => db().from("leagues").select("code,name,country,cup").order("country"));
}

/** Birden çok takımın bu sezonki maç maç satırları (Seri Avcısı). Görünüm yoksa null. */
export async function statRowsForSlugs(slugs: string[], sinceIso: string, beforeIso: string): Promise<TeamStatRow[] | null> {
  try {
    const parts: string[][] = [];
    for (let i = 0; i < slugs.length; i += 50) parts.push(slugs.slice(i, i + 50));
    const res = await Promise.all(parts.map((part) => all<TeamStatRow>(() => db().from("v_takim_mac_istatistik").select("match_id,kickoff_at,league,competition,side,team_slug,team_name,goals_for,goals_against,corners_for,corners_against,cards_for,cards_against,sot_for,sot_against,xg_for,xg_against")
      .in("team_slug", part).gte("kickoff_at", sinceIso).lt("kickoff_at", beforeIso).order("kickoff_at", { ascending: false }))));
    return res.flat();
  } catch { return null; }
}

/** Bülten genelinde oran hareketi (Piyasa Nabzı). Görünüm yoksa ya da boşsa []. */
export async function oddsMovesFor(ids: string[]): Promise<OddsMove[]> {
  try {
    const parts: string[][] = [];
    for (let i = 0; i < ids.length; i += 40) parts.push(ids.slice(i, i + 40));
    return (await Promise.all(parts.map((p) => run<OddsMove>(db().from("v_oran_hareketi").select("*").in("match_id", p))))).flat();
  } catch { return []; }
}

/** Sezon simülasyonu (v_sezon_simulasyonu): kalan fikstürün 10.000 kez oynatılması. Tablo yoksa null. */
export interface SimRow {
  league: string; team_id: string; team_name: string; kosu: number; sampiyon: number; ilk4: number; kume: number;
  ort_puan: number; ort_sira: number; mevcut_puan: number; kalan_mac: number; sira_dagilimi: number[] | null;
  computed_at: string; yontem: string | null; tahmini_sira: number;
}
export const seasonSim = (lg?: string) =>
  viewOrNull<SimRow>(() => { const q = db().from("v_sezon_simulasyonu").select("*"); return (lg ? q.eq("league", lg) : q).order("league").order("ort_sira"); });
export const seasonSimForTeams = (ids: string[]) =>
  viewOrNull<SimRow>(() => db().from("v_sezon_simulasyonu").select("*").in("team_id", ids));
export const leagueTables = (lgs: string[]) =>
  viewOrNull<StandRow>(() => db().from("v_puan_durumu").select("*").in("league", lgs));
/**
 * Simülasyon bugünkü puan durumuyla birebir tutuyor mu? Takım listesi ve her takımın puanı aynı olmalı;
 * oynanan + kalan maç bütün takımlarda eşit olmalı. Tutmayan lig gösterilmez (eski/bozuk hesap yayımlanmaz).
 */
export function simConsistent(sim: SimRow[], table: StandRow[]): boolean {
  if (!sim.length || sim.length !== table.length) return false;
  const t = new Map(table.map((r) => [r.team_id, r]));
  const tot = new Set<number>();
  for (const s of sim) {
    const r = t.get(s.team_id);
    if (!r || r.puan !== s.mevcut_puan) return false;
    tot.add(r.o + s.kalan_mac);
  }
  return tot.size === 1;
}

/** Kanıt Mührü (v_kanit_muhru). Görünüm yoksa ya da boşsa []. */
export interface SealRow { seq: number; ref_table: "predictions" | "coupons"; ref_id: string; icerik_sha256: string; sha256: string; onceki_sha256: string; kanonik: string; muhurlendi_at: string }
export const sealsLite = () =>
  all<Pick<SealRow, "seq" | "ref_table" | "ref_id" | "sha256" | "muhurlendi_at">>(() => db().from("v_kanit_muhru").select("seq,ref_table,ref_id,sha256,muhurlendi_at").order("seq")).catch(() => []);
export const sealsFull = () =>
  all<SealRow>(() => db().from("v_kanit_muhru").select("*").order("seq")).catch(() => [] as SealRow[]);
/** Mühür doğrulaması için süzgeçsiz tahmin listesi (yayım süzgeci uygulanmaz; mühür her kaydı kapsar). */
export const allPredictionsRaw = () => all<Prediction>(() => db().from("predictions").select("*").order("kickoff_at", { ascending: false }));

/** Otomatik işlerin son başarılı çalışması (v_sistem_durumu) — alt bilgide sessiz sağlık işareti. */
export async function systemStatus(): Promise<{ is_adi: string; son_basari: string | null; gecikti: boolean }[]> {
  const { data, error } = await db().from("v_sistem_durumu").select("is_adi,son_basari,gecikti");
  if (error) return [];
  return (data ?? []) as { is_adi: string; son_basari: string | null; gecikti: boolean }[];
}
