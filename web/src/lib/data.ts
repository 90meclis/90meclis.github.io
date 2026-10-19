import { supabase } from "./supabase";
import { dayBoundsUtc, addDays, trDay } from "./format";
import type {
  Agenda, Analysis, Coupon, Injury, Lineup, Match, MatchStat, Prediction, QueueItem, Team, Trend, Weather,
} from "./types";

export class NoDataError extends Error {}

type Res = PromiseLike<{ data: unknown; error: { message: string } | null }>;
interface Sel { range: (from: number, to: number) => Res }

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

const MATCH_LIST = "id,league,kickoff_at,home_team_id,away_team_id,home_name,away_name,home_goals,away_goals,score,ht_home_goals,ht_away_goals,status,durum,venue,referee,city,odds,missing_fields,completeness,updated_at,season";

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
  return all<Match>(() => db().from("matches").select(MATCH_LIST).gte("kickoff_at", lo).lt("kickoff_at", hi).order("kickoff_at"));
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

export async function teamHistory(teamId: string, beforeIso: string, limit = 10): Promise<Match[]> {
  return run<Match>(
    db().from("matches").select(MATCH_LIST)
      .or(`home_team_id.eq."${teamId}",away_team_id.eq."${teamId}"`)
      .lt("kickoff_at", beforeIso).not("home_goals", "is", null)
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
  run<Prediction>(db().from("predictions").select("*").eq("match_id", id).order("recorded_at"));
export const newsForMatch = (id: string) =>
  run<Agenda>(db().from("agenda").select("*").contains("match_ids", [id]).order("published_at", { ascending: false }).limit(12));
export const teamsIn = (ids: string[]) => run<Team>(db().from("teams").select("*").in("id", ids));

export const allPredictions = () =>
  all<Prediction>(() => db().from("predictions").select("*").order("kickoff_at", { ascending: false }));
export const allCoupons = () => all<Coupon>(() => db().from("coupons").select("*").order("coupon_date", { ascending: false }));
export const queue = () => all<QueueItem>(() => db().from("analysis_queue").select("*"));

export async function upcomingPredictions(): Promise<Prediction[]> {
  const [lo] = dayBoundsUtc(addDays(trDay(), -1));
  return all<Prediction>(() => db().from("predictions").select("*").gte("kickoff_at", lo).order("kickoff_at"));
}

export const news = (limit = 400) =>
  all<Agenda>(() => db().from("agenda").select("*").order("published_at", { ascending: false }), limit);

export const trends = (lg: string) => all<Trend>(() => db().from("trends").select("*").eq("league", lg));

/** Güncel sezonun maçları (Avrupa takvimi: 1 Temmuz'dan itibaren). */
export async function seasonMatches(lg: string): Promise<Match[]> {
  const now = new Date();
  const y = now.getUTCMonth() >= 6 ? now.getUTCFullYear() : now.getUTCFullYear() - 1;
  return all<Match>(() =>
    db().from("matches").select(MATCH_LIST).eq("league", lg).gte("kickoff_at", `${y}-07-01T00:00:00Z`).order("kickoff_at", { ascending: false }),
  );
}

export async function predictionsForMatches(ids: string[]): Promise<Prediction[]> {
  if (!ids.length) return [];
  const out: Prediction[] = [];
  for (let i = 0; i < ids.length; i += 100) out.push(...(await run<Prediction>(db().from("predictions").select("*").in("match_id", ids.slice(i, i + 100)))));
  return out;
}

