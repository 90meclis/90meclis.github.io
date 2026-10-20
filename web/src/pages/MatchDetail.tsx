import { useEffect, useMemo, useState } from "react";
import { normalizeScenarios, scenarioMeta, type Scn } from "../lib/scenario";
import { leagueTables, seasonSim, simConsistent } from "../lib/data";
import { Link, useParams, useSearchParams } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { abbr, Crest } from "../components/Crest";
import { dateLong, dateShort, dateTime, hoursBefore, num, pct, relTime, signed, time } from "../lib/format";
import { league, pickLabel, sourceLabel, fmtLine } from "../lib/labels";
import { hasScore, idFromSlug, matchPath, matchState, sameTeam } from "../lib/match";
import { usePageMeta } from "../lib/seo";
import type { AnalysisPayload, Injury, Lineup, Match, MatchStat, Prediction } from "../lib/types";
import { Card, Empty, Gate, Meter, Skeleton, Stat, StatusPill, TagPill } from "../components/ui";
import { ProbBar } from "../components/charts";
import { MiniMd } from "../components/MiniMd";
import { PickCard } from "../components/PickCard";
import { ScanTable } from "../components/ScanTable";
import { scanMatch } from "../lib/scan";
import {
  METRICS, UEFA, gameRows, implied1x2, mainLeague, poissonGrid, rest, standings, streaks, viewGameRows, viewTable,
  type GameRow, type MetricKey, type TableRow,
} from "../lib/dossier";
import { story } from "../lib/story";

export default function MatchDetail() {
  const { id } = useParams();
  const [sp] = useSearchParams();
  const mid = sp.get("id") ?? (id ? idFromSlug(id) ?? decodeURIComponent(id) : "");
  const mq = useAsync(`match:${mid}`, () => api.match(mid), [mid]);
  const m = mq.data;
  usePageMeta(m ? `${m.home_name} – ${m.away_name}` : "Maç", m ? `${m.home_name} – ${m.away_name} maç dosyası: kadrolar, eksikler, maç maç form ve istatistik, karşılaşmalar, oranlar, olasılıklar ve senaryolar.` : undefined);

  if (mq.loading) return <Skeleton rows={6} h={90} />;
  if (mq.error || !m) {
    return (
      <Gate loading={false} error={mq.error}>
        <Empty title="Maç bulunamadı" icon="◎"><Link to="/mac-merkezi" className="btn primary">Maç Merkezi'ne dön</Link></Empty>
      </Gate>
    );
  }
  return <Detail m={m} />;
}

// ---------------------------------------------------------------------------------------------
// Veri: maçın bütün dosyası tek yüklemede
// ---------------------------------------------------------------------------------------------
interface Dossier {
  a?: AnalysisPayload; picks: Prediction[]; lineups: Lineup[]; inj: Injury[];
  weather?: NonNullable<AnalysisPayload["weather"]>; news: Awaited<ReturnType<typeof api.newsForMatch>>;
  h2h: Match[]; hGames: Match[]; aGames: Match[]; hRows: GameRow[]; aRows: GameRow[]; stats: MatchStat[]; ref: Match[];
  tables: Record<string, TableRow[]>; phaseKey: string | null; homeLg: string | null; awayLg: string | null;
  rest: { home: RestInfo; away: RestInfo }; snaps: api.OddsSnap[];
  /** hangi blok hangi kaynaktan: "görünüm" (veritabanı görünümü) ya da "ham" (maç + istatistik tablosundan) */
  via: { form: string; table: string };
}
interface RestInfo { days: number | null; last14: number }

const PHASE = (m: Match) => `${m.league}:faz`;

/** Görünüm puan durumu ham hesapla aynıysa görünüm kullanılır (aynı takımlar, aynı puan/averaj). */
function sameTable(a: TableRow[], b: TableRow[]): boolean {
  if (a.length !== b.length) return false;
  const ib = new Map(b.map((r) => [r.id, r]));
  return a.every((r) => { const x = ib.get(r.id); return !!x && x.pts === r.pts && x.p === r.p && x.gf - x.ga === r.gf - r.ga; });
}

async function loadDossier(m: Match): Promise<Dossier> {
  const ko = m.kickoff_at;
  const [an, picks, lineups, inj, w, news, h2h0, hG0, aG0, ref0, hV, aV, restV, snaps] = await Promise.all([
    api.analysisFor(m.id), api.predictionsForMatch(m.id), api.lineupsFor(m.id), api.injuriesFor(m), api.weatherFor(m.id),
    api.newsForMatch(m.id), api.h2hAll(m.home_team_id, m.away_team_id, ko), api.teamSeason(m.home_team_id, ko),
    api.teamSeason(m.away_team_id, ko), m.referee ? api.refereeSeason(m.referee, ko) : Promise.resolve([] as Match[]),
    api.teamStatRows(m.home_team_id, ko), api.teamStatRows(m.away_team_id, ko), api.restView(m.id), api.oddsSnapshots(m.id),
  ]);
  // Yanlış eşlenmiş satırlar (ör. adı Trabzonspor, kimliği samsunspor) hiçbir hesaba girmez
  const [h2h, hGames, aGames, ref] = await Promise.all([api.dropCorrupt(h2h0), api.dropCorrupt(hG0), api.dropCorrupt(aG0), api.dropCorrupt(ref0)]);
  const cup = UEFA.has(m.league);
  const homeLg = mainLeague(hGames), awayLg = mainLeague(aGames);
  const lgs = [...new Set([m.league, ...(cup ? [homeLg, awayLg] : [])].filter((x): x is string => !!x))];
  const ids = [...new Set([...hGames, ...aGames, ...h2h, ...ref].map((x) => x.id))];
  const [stats, played, views] = await Promise.all([
    api.statsFor(ids),
    Promise.all(lgs.map((lg) => api.leaguePlayed(lg, ko).then(api.dropCorrupt))),
    Promise.all(lgs.map((lg) => (UEFA.has(lg) ? api.europeTableView(lg) : api.leagueTableView(lg)))),
  ]);
  const tables: Record<string, TableRow[]> = {};
  let phaseKey: string | null = null;
  const via = { form: "ham", table: "ham" };
  lgs.forEach((lg, i) => {
    let raw: TableRow[];
    if (UEFA.has(lg)) {
      // Lig aşaması: ön eleme/play-off maçları (Eylül öncesi) puan durumuna girmez
      const y = new Date(seasonStart(ko)).getUTCFullYear();
      raw = standings(played[i].filter((x) => x.kickoff_at >= `${y}-09-01`));
    } else raw = standings(played[i]);
    const v = views[i] ? viewTable(views[i]!, (r) => (UEFA.has(lg) ? `${lg}:${r.team_slug}` : r.team_id!)) : null;
    const use = v && sameTable(v, raw) ? v : raw;
    if (v && use === v) via.table = "görünüm";
    if (!use.length) return;
    if (UEFA.has(lg)) { tables[PHASE(m)] = use; phaseKey = PHASE(m); } else tables[lg] = use;
  });
  // Takım maç satırları: görünüm, ham hesapla aynı maç kümesini veriyorsa görünümden (aşama bilgisiyle)
  const fromView = async (v: api.TeamStatRow[] | null, games: Match[]) => {
    if (!v) return null;
    const rows = viewGameRows(v);
    const ok = await api.dropCorrupt(rows.map((r) => ({ id: r.m.id, league: r.m.league, home_name: r.m.home_name, away_name: r.m.away_name })));
    const keep = new Set(ok.map((x) => x.id));
    const out = rows.filter((r) => keep.has(r.m.id));
    const gi = new Set(games.map((g) => g.id));
    return out.length === games.length && out.every((r) => gi.has(r.m.id)) ? out : null;
  };
  const [hv, av] = await Promise.all([fromView(hV, hGames), fromView(aV, aGames)]);
  const hRows = hv ?? gameRows(hGames, m.home_team_id, stats), aRows = av ?? gameRows(aGames, m.away_team_id, stats);
  if (hv && av) via.form = "görünüm";
  const rv = (side: "home" | "away", games: Match[]): RestInfo => {
    const x = restV?.find((r) => r.side === side);
    return x ? { days: x.dinlenme_gun != null ? Math.floor(x.dinlenme_gun) : null, last14: x.son14_mac } : rest(games, ko);
  };
  const order: Record<string, number> = { meclis_gorusu: 0, gunun_karari: 1, karar_birligi: 2 };
  return {
    a: an[0]?.payload, picks: [...picks].sort((x, y) => (order[x.tag] ?? 9) - (order[y.tag] ?? 9)), lineups, inj,
    weather: w[0]?.data ?? an[0]?.payload?.weather, news, h2h, hGames, aGames, hRows, aRows, stats, ref, tables, phaseKey, homeLg, awayLg,
    rest: { home: rv("home", hGames), away: rv("away", aGames) }, snaps: snaps ?? [], via,
  };
}
const seasonStart = (iso: string) => api.seasonStartIso(new Date(iso));

// ---------------------------------------------------------------------------------------------
// Sayfa: skor tabelası + yapışkan bölüm çubuğu (başparmak boyu, derin bağlantı: ?bolum=)
// ---------------------------------------------------------------------------------------------
const TABS = [
  ["ozet", "Özet"], ["kadro", "Kadrolar"], ["eksik", "Eksikler"], ["form", "Form & İstatistik"],
  ["h2h", "Karşılaşmalar"], ["oran", "Oranlar & Olasılıklar"], ["senaryo", "Senaryolar"],
] as const;
type TabKey = (typeof TABS)[number][0];

function Detail({ m }: { m: Match }) {
  const [sp, setSp] = useSearchParams();
  const raw = sp.get("bolum");
  const want: TabKey = (TABS.find((t) => t[0] === raw)?.[0] ?? "ozet") as TabKey;
  const go = (k: TabKey) => {
    const n = new URLSearchParams(sp);
    if (k === "ozet") n.delete("bolum"); else n.set("bolum", k);
    setSp(n, { replace: true });
    const el = document.getElementById("mtabs");
    if (el && el.getBoundingClientRect().top < 0) el.scrollIntoView({ block: "start" });
  };
  const d = useAsync(`dos:${m.id}`, () => loadDossier(m), [m.id]);
  // Oynanmış maçta hiç kadro kaydı yoksa Kadrolar bölümü gösterilmez (boş kart yok)
  const noXI = !!d.data && hasScore(m) && (["home", "away"] as const).every((s) => !xisFor(d.data!.lineups, s, d.data!.a).length);
  const hiddenTab = (k: TabKey) => (k === "senaryo" && !!d.data && !d.data.a) || (k === "kadro" && noXI);
  const tab: TabKey = hiddenTab(want) ? "ozet" : want;
  useEffect(() => {
    // Seçili bölüm düğmesi her zaman görünür kalsın (yatay kaydırma)
    document.querySelector<HTMLElement>("#mtabs button.on")?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [tab]);
  const st = matchState(m);
  const sc = hasScore(m);
  const l = league(m.league);
  const [stuck, setStuck] = useState(false);
  useEffect(() => {
    const el = document.querySelector(".scoreboard");
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([e]) => setStuck(!e.isIntersecting), { rootMargin: "-60px 0px 0px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  const counts: Partial<Record<TabKey, number>> = d.data ? {
    eksik: injuryCount(d.data, m),
    h2h: d.data.h2h.length,
    senaryo: d.data.a?.scenarios?.length ?? 0,
  } : {};

  return (
    <div className="detail">
      <nav className="crumbs" aria-label="Konum"><Link to="/mac-merkezi">Maç Merkezi</Link> <span aria-hidden="true">/</span> <Link to={`/mac-merkezi?gun=${m.kickoff_at.slice(0, 10)}&lig=${m.league}`}>{l.name}</Link></nav>
      <section className="scoreboard elite">
        <div className="sb-meta"><span>{l.flag} {l.name}</span><span>{dateLong(m.kickoff_at)} · {time(m.kickoff_at)} TSİ</span></div>
        <div className="sb-main">
          <div className="sb-side home">
            <Crest name={m.home_name} />
            <h1 className="sb-team">{m.home_name}</h1>
            {d.data && <FormPills rows={d.data.hRows} />}
          </div>
          <div className="sb-score">
            {sc ? <span className="sb-goals">{m.home_goals}<i>–</i>{m.away_goals}</span> : <span className="sb-time">{time(m.kickoff_at)}</span>}
            {st.label && <span className={`mstate ${st.key}`}>{st.label}</span>}
            {!sc && <Countdown iso={m.kickoff_at} />}
            {m.ht_home_goals !== null && sc && <small className="muted">İY {m.ht_home_goals}-{m.ht_away_goals}</small>}
          </div>
          <div className="sb-side away">
            <Crest name={m.away_name} />
            <h1 className="sb-team">{m.away_name}</h1>
            {d.data && <FormPills rows={d.data.aRows} />}
          </div>
        </div>
        {d.data && <HeroProb m={m} d={d.data} />}
        {d.data && <CompareStrip m={m} d={d.data} />}
        <div className="sb-foot">
          {m.venue && <span>🏟 {m.venue}{m.city ? `, ${m.city}` : ""}</span>}
          {m.referee && <span>Hakem: {m.referee}</span>}
        </div>
      </section>

      <nav id="mtabs" className={`mtabs ${stuck ? "stuck" : ""}`} role="tablist" aria-label="Maç dosyası bölümleri">
        {stuck && <span className="mt-mini" aria-hidden="true"><b>{abbr(m.home_name)}</b>{sc ? `${m.home_goals}–${m.away_goals}` : time(m.kickoff_at)}<b>{abbr(m.away_name)}</b></span>}
        {TABS.filter(([k]) => !hiddenTab(k)).map(([k, label]) => (
          <button key={k} role="tab" type="button" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => go(k)}>
            {label}{counts[k] ? <small>{counts[k]}</small> : null}
          </button>
        ))}
      </nav>

      <Gate loading={d.loading} error={d.error} rows={5}>
        {d.data && (
          <div className="mtab-body" role="tabpanel" key={tab}>
            {tab === "ozet" && <Ozet m={m} d={d.data} go={go} />}
            {tab === "kadro" && <Squads m={m} d={d.data} />}
            {tab === "eksik" && <Absences m={m} d={d.data} />}
            {tab === "form" && <FormTab m={m} d={d.data} />}
            {tab === "h2h" && <H2HTab m={m} d={d.data} />}
            {tab === "oran" && <OddsTab m={m} d={d.data} />}
            {tab === "senaryo" && d.data.a && <ScenarioTab m={m} d={d.data} />}
          </div>
        )}
      </Gate>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Skor tabelası parçaları: monogram arma (telifsiz), form hapları, geri sayım, kazanma olasılığı, istatistik şeridi
// ---------------------------------------------------------------------------------------------
function FormPills({ rows }: { rows: GameRow[] }) {
  const r = [...rows].sort((a, b) => b.m.kickoff_at.localeCompare(a.m.kickoff_at)).slice(0, 5).reverse();
  if (r.length < 3) return null;
  return <span className="fpills" aria-label={`Son ${r.length} maç: ${r.map((x) => x.res).join(" ")}`}>{r.map((x, i) => <i key={i} className={`fp ${x.res}`} title={`${x.home ? "İç" : "Dış"} · ${x.opp} ${x.gf}-${x.ga}`}>{x.res}</i>)}</span>;
}
function Countdown({ iso }: { iso: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(t); }, []);
  const ms = new Date(iso).getTime() - now;
  if (ms <= 0 || ms > 7 * 864e5) return null;
  const d = Math.floor(ms / 864e5), h = Math.floor((ms % 864e5) / 36e5), mi = Math.floor((ms % 36e5) / 6e4);
  return <small className="cd">{d ? `${d} gün ${h} sa` : h ? `${h} sa ${mi} dk` : `${mi} dk`} sonra</small>;
}
function HeroProb({ m, d }: { m: Match; d: Dossier }) {
  const p1 = Object.fromEntries((d.a?.markets ?? []).filter((x) => x.market === "1X2").map((x) => [x.selection, x.probability]));
  const own = modelOwn(d.a) && p1["1"] !== undefined && !modelOff(m, d.a);
  const imp = implied1x2(m);
  const v = own ? [p1["1"], p1["X"], p1["2"]] : imp;
  if (!v) return null;
  return (
    <div className="hprob">
      <div className="hp-bar">{v.map((x, i) => <span key={i} className={`h${i}`} style={{ width: `${x * 100}%` }}><b>{pct(x)}</b></span>)}</div>
      <div className="hp-k"><span>{m.home_name}</span><span>{own ? "Meclis olasılığı" : "Piyasa (marjsız)"}</span><span>{m.away_name}</span></div>
    </div>
  );
}
function CompareStrip({ m, d }: { m: Match; d: Dossier }) {
  const avg = (rows: GameRow[], f: (r: GameRow) => [number | null, number | null] | undefined): [number, number, number] | null => {
    const v = rows.map(f).filter((x): x is [number, number] => !!x && x[0] != null && x[1] != null);
    return v.length >= 3 ? [v.reduce((a, x) => a + x[0], 0) / v.length, v.reduce((a, x) => a + x[1], 0) / v.length, v.length] : null;
  };
  const H = d.hRows, A = d.aRows;
  const defs: [string, (r: GameRow) => [number | null, number | null] | undefined, number][] = [
    ["Gol", (r) => r.vals.gol, 1], ["xG", (r) => r.xg, 2], ["Şut", (r) => r.vals.sut, 1], ["İsabetli şut", (r) => r.vals.isabet, 1], ["Korner", (r) => r.vals.korner, 1], ["Kart", (r) => r.vals.kart, 1],
  ];
  const rows = defs.map(([k, f, dg]) => ({ k, dg, h: avg(H, f), a: avg(A, f) })).filter((x) => x.h && x.a);
  if (!rows.length) return null;
  // xG şansı: gol − xG (lehte) ve yenilen − xG (aleyhte); ≥5 maç
  const luck = (rows: GameRow[]) => {
    const v = rows.filter((r) => r.xg && r.xg[0] != null && r.xg[1] != null);
    if (v.length < 5) return null;
    const f = v.reduce((a, r) => a + r.gf - r.xg![0]!, 0), g = v.reduce((a, r) => a + r.ga - r.xg![1]!, 0);
    return { f, g, n: v.length };
  };
  const lt = (x: ReturnType<typeof luck>, name: string) => {
    if (!x) return null;
    const net = x.f - x.g;
    const tag = net >= 2.5 ? "şanslı gidiyor" : net <= -2.5 ? "şanssız gidiyor" : "xG'ye uygun";
    return <span className={`luck ${net >= 2.5 ? "up" : net <= -2.5 ? "down" : ""}`}><b>{name}</b> {tag}: {x.n} maçta xG'den {signed(x.f, 1)} gol attı, {signed(x.g, 1)} gol yedi</span>;
  };
  return (
    <div className="cstrip" aria-label="Bu sezon maç başı, lehte–aleyhte">
      <div className="cs-h"><span>{abbr(m.home_name)}</span><small>bu sezon maç başı · lehte–aleyhte</small><span>{abbr(m.away_name)}</span></div>
      {rows.map((x) => {
        const hv = x.h![0], av = x.a![0], mx = Math.max(hv, av) || 1;
        return (
          <div key={x.k} className="cs-row">
            <span className="cs-v"><b>{num(hv, x.dg)}</b><small>{num(x.h![1], x.dg)}</small></span>
            <span className="cs-bar l"><i style={{ width: `${(hv / mx) * 100}%` }} className={hv >= av && x.k !== "Kart" ? "win" : ""} /></span>
            <span className="cs-k">{x.k}</span>
            <span className="cs-bar r"><i style={{ width: `${(av / mx) * 100}%` }} className={av >= hv && x.k !== "Kart" ? "win" : ""} /></span>
            <span className="cs-v r"><b>{num(av, x.dg)}</b><small>{num(x.a![1], x.dg)}</small></span>
          </div>
        );
      })}
      <div className="lucks">{lt(luck(H), m.home_name)}{lt(luck(A), m.away_name)}</div>
    </div>
  );
}

function injuryCount(d: Dossier, m: Match): number {
  const ie = (d.a?.injury_effect ?? {}) as Record<string, unknown>;
  const pm = ((ie.home_missing as unknown[] | undefined)?.length ?? 0) + ((ie.away_missing as unknown[] | undefined)?.length ?? 0);
  return pm || d.inj.filter((x) => x.team_id === m.home_team_id || x.team_id === m.away_team_id).length;
}

const modelOwn = (a?: AnalysisPayload) => (a?.basis ?? "").startsWith("model");
/** Model 1X2'si piyasadan 20 puandan fazla ayrışıyor mu (veri kontrol)? Öyleyse modelin olasılıkları gösterilmez. */
const modelOff = (m: Match, a?: AnalysisPayload) => modelOwn(a) && scanMatch(m, a?.markets, true).some((r) => r.market === "1X2" && r.wild);
const rowsFor = (_m: Match, d: Dossier, side: "home" | "away") => (side === "home" ? d.hRows : d.aRows);

// ---------------------------------------------------------------------------------------------
// ÖZET
// ---------------------------------------------------------------------------------------------
function Ozet({ m, d, go }: { m: Match; d: Dossier; go: (k: TabKey) => void }) {
  const a = d.a;
  const cup = UEFA.has(m.league);
  const H = rowsFor(m, d, "home"), A = rowsFor(m, d, "away");
  const scope = (r: GameRow[], home: boolean) => r.filter((x) => x.home === home && (cup ? x.comp === "avrupa" : x.comp === "lig"));
  // Avrupa örneklemi küçükse (ör. 1-2 maç) bütün kulvarların sahaya göre maçları kullanılır
  const ven = (r: GameRow[], home: boolean) => { const x = scope(r, home); return x.length >= 3 ? x : r.filter((g) => g.home === home); };
  const homeVen = ven(H, true), awayVen = ven(A, false);
  const scanRows = useMemo(() => scanMatch(m, a?.markets, modelOwn(a) && !!a?.ready), [m, a]);
  const best = scanRows.filter((r) => r.value).sort((x, y) => (y.edge ?? 0) - (x.edge ?? 0))[0] ?? null;
  const rH = d.rest.home, rA = d.rest.away;
  const tKey = cup ? d.phaseKey : m.league;
  const table = tKey ? d.tables[tKey] ?? null : null;
  const fl = (n: number) => fmtLine(n);
  const sH = METRICS.flatMap((x) => streaks(homeVen, x.key, "iç saha", fl));
  const sA = METRICS.flatMap((x) => streaks(awayVen, x.key, "deplasman", fl));
  const pick = d.picks[0] ?? null;
  const lines = story({
    m, a, homeVen, awayVen, table, restH: rH.days, restA: rA.days, implied: implied1x2(m), best: pick ? null : best, pick,
    streakH: sH, streakA: sA, cup,
  });
  const p1 = Object.fromEntries((a?.markets ?? []).filter((x) => x.market === "1X2").map((x) => [x.selection, x.probability]));
  const imp = implied1x2(m);
  const published = d.picks.length > 0;
  const bp = a?.best_pick;

  return (
    <div className="detail-grid">
      <div className="col-main">
        {published && <Verdict picks={d.picks} a={a} m={m} />}
        <TopScenario m={m} d={d} go={go} />
        <Card title="Maç konuşuyor" className="analysis">
          {lines.length > 0 && <div className="story">{lines.map((x, i) => <p key={i}>{x}</p>)}</div>}
          {p1["1"] !== undefined && modelOwn(a) && !modelOff(m, a) ? (
            <div className="pb-block"><span className="kicker">Meclis olasılıkları</span><ProbBar p1={p1["1"]} px={p1["X"]} p2={p1["2"]} home={m.home_name} away={m.away_name} /></div>
          ) : imp ? (
            <div className="pb-block"><span className="kicker">Piyasanın gördüğü (marjsız)</span><ProbBar p1={imp[0]} px={imp[1]} p2={imp[2]} home={m.home_name} away={m.away_name} /></div>
          ) : null}
          {a && (
            <div className="stats-row">
              {a.lambdas && <Stat label={`${m.home_name} gol bekl.`} value={num(a.lambdas.home)} />}
              {a.lambdas && <Stat label={`${m.away_name} gol bekl.`} value={num(a.lambdas.away)} />}
              {a.count_info?.corners && <Stat label="Korner bekl." value={num(a.count_info.corners.total, 1)} />}
              {a.count_info?.cards && <Stat label="Kart bekl." value={num(a.count_info.cards.total, 1)} />}
              {a.count_info?.shots_on_target && <Stat label="İsabetli şut bekl." value={num(a.count_info.shots_on_target.total, 1)} />}
            </div>
          )}
          {bp && !published && modelOwn(a) && !modelOff(m, a) && (
            <div className="best-pick">
              <span className="kicker">Meclis'in eğilimi</span>
              <strong>{pickLabel(bp.market, bp.selection, bp.line, m.home_name, m.away_name)}</strong>
              <span className="muted">olasılık {pct(bp.probability)} · {bp.odds ? `oran ${num(bp.odds)}` : `adil oran ${num(bp.fair_odds)}`}</span>
            </div>
          )}
          <div className="jump">
            <button type="button" className="btn ghost" onClick={() => go("form")}>Maç maç form →</button>
            <button type="button" className="btn ghost" onClick={() => go("oran")}>Bütün pazarlar →</button>
          </div>
        </Card>
        <SeasonStakes m={m} />
        {d.picks.length > 1 && (
          <Card title="Bu maçtaki tüm kararlar"><div className="picks">{d.picks.map((p) => <PickCard key={p.id} p={p} />)}</div></Card>
        )}
        <NewsCard d={d} />
      </div>
      <aside className="col-side">
        <TableCard m={m} d={d} />
        <RestCard m={m} rH={rH} rA={rA} />
        <RefereeCard m={m} d={d} />
        <WeatherCard m={m} w={d.weather} />
        <SourcesCard m={m} d={d} />
      </aside>
    </div>
  );
}

function TableCard({ m, d }: { m: Match; d: Dossier }) {
  const cup = UEFA.has(m.league);
  const blocks: { title: string; rows: TableRow[]; ids: string[]; phase: boolean }[] = [];
  if (cup && d.phaseKey) blocks.push({ title: `${league(m.league).name} · lig aşaması`, rows: d.tables[d.phaseKey], ids: [m.home_team_id, m.away_team_id], phase: true });
  if (!cup && d.tables[m.league]) blocks.push({ title: league(m.league).name, rows: d.tables[m.league], ids: [m.home_team_id, m.away_team_id], phase: false });
  if (cup) for (const [lg, side] of [[d.homeLg, "home"], [d.awayLg, "away"]] as const) {
    if (!lg || !d.tables[lg]) continue;
    const slug = (side === "home" ? m.home_team_id : m.away_team_id).split(":")[1];
    const ex = blocks.find((b) => b.title === league(lg).name);
    const id = d.tables[lg].find((r) => r.id.endsWith(`:${slug}`))?.id;
    if (!id) continue;
    if (ex) ex.ids.push(id); else blocks.push({ title: league(lg).name, rows: d.tables[lg], ids: [id], phase: false });
  }
  const shown = blocks.filter((b) => b.rows.some((r) => b.ids.some((i) => sameTeam(r.id, i) && r.p > 0)));
  if (!shown.length) return null;
  return (
    <Card title="Puan durumu" aside={<span className="muted tiny">bu sezon, oynanmış maçlardan</span>}>
      {shown.map((b) => <MiniTable key={b.title} {...b} />)}
    </Card>
  );
}

function MiniTable({ title, rows, ids, phase }: { title: string; rows: TableRow[]; ids: string[]; phase: boolean }) {
  const mine = rows.filter((r) => ids.some((i) => r.id === i || sameTeam(r.id, i)));
  const n = rows.length;
  const keep = new Set<number>([1]);
  for (const r of mine) for (let k = r.pos - 1; k <= r.pos + 1; k++) if (k >= 1 && k <= n) keep.add(k);
  const list = rows.filter((r) => keep.has(r.pos));
  const note = (r: TableRow) => {
    const lead = rows[0];
    if (phase) {
      const p8 = rows[7], p24 = rows[23];
      if (r.pos <= 8) { const g = r.pts - (rows[8]?.pts ?? r.pts); return `ilk 8 içinde (son 16'ya doğrudan) · ${g > 0 ? `9.'nun ${g} puan önünde` : "9. ile aynı puanda"}`; }
      if (r.pos <= 24) return `play-off hattında · ilk 8'e ${Math.max(0, (p8?.pts ?? 0) - r.pts)} puan`;
      return `elenme hattında · 24.'ye ${Math.max(0, (p24?.pts ?? 0) - r.pts)} puan`;
    }
    const drop = rows[n - 3];
    if (r.pos === 1) { const g = r.pts - (rows[1]?.pts ?? r.pts); return g > 0 ? `lider · ikinciye ${g} puan fark` : "lider · ikinciyle aynı puanda, averajla önde"; }
    return `lidere ${lead.pts - r.pts} puan${n >= 10 && drop && r.pos < n - 2 ? ` · düşme hattının ${r.pts - drop.pts} puan üstünde` : ""}`;
  };
  return (
    <div className="mini-table">
      <h4>{title}</h4>
      <table className="tbl tight">
        <thead><tr><th>#</th><th>Takım</th><th>O</th><th>AV</th><th>P</th></tr></thead>
        <tbody>
          {list.map((r, i) => (
            <tr key={r.id} className={mine.includes(r) ? "me" : ""}>
              <td>{i > 0 && list[i - 1].pos !== r.pos - 1 ? <span className="gap">⋯ </span> : null}{r.pos}</td>
              <td>{r.name}</td><td>{r.p}</td><td>{signed(r.gf - r.ga, 0)}</td><td><b>{r.pts}</b></td>
            </tr>
          ))}
        </tbody>
      </table>
      {mine.map((r) => <p key={r.id} className="muted tiny"><b>{r.name}</b>: {note(r)}</p>)}
    </div>
  );
}

function RestCard({ m, rH, rA }: { m: Match; rH: RestInfo; rA: RestInfo }) {
  if (rH.days == null && rA.days == null) return null;
  const row = (name: string, r: RestInfo) => (
    <div className="rest-row"><b>{name}</b><span>{r.days != null ? `${r.days} gün dinlenme` : "—"}</span><span className="muted small">son 14 günde {r.last14} maç</span></div>
  );
  return (
    <Card title="Dinlenme ve yoğunluk">
      {row(m.home_name, rH)}{row(m.away_name, rA)}
      <p className="muted tiny">Bütün kulvarlar (lig, Avrupa, kupa); son maçtan bu maçın başlama saatine.</p>
    </Card>
  );
}

function RefereeCard({ m, d }: { m: Match; d: Dossier }) {
  if (!m.referee) return null;
  const games = d.ref.filter(hasScore);
  const idx = new Map(d.stats.map((s) => [`${s.match_id}:${s.side}`, s]));
  let cn = 0, cards = 0, fn = 0, fouls = 0, goals = 0, hw = 0, aw = 0, red = 0;
  for (const g of games) {
    const h = idx.get(`${g.id}:home`), a = idx.get(`${g.id}:away`);
    if (h && a && h.yellow != null && a.yellow != null) { cn++; cards += h.yellow + a.yellow + (h.red ?? 0) + (a.red ?? 0); red += (h.red ?? 0) + (a.red ?? 0); }
    if (h?.fouls != null && a?.fouls != null) { fn++; fouls += h.fouls + a.fouls; }
    goals += g.home_goals! + g.away_goals!;
    if (g.home_goals! > g.away_goals!) hw++; else if (g.home_goals! < g.away_goals!) aw++;
  }
  return (
    <Card title="Hakem">
      <p><b>{m.referee}</b></p>
      {games.length ? (
        <>
          <div className="mini-stats">
            <span><b>{games.length}</b> maç</span>
            {cn > 0 && <span><b>{num(cards / cn, 1)}</b> kart/maç</span>}
            {fn > 0 && <span><b>{num(fouls / fn, 1)}</b> faul/maç</span>}
            <span><b>{num(goals / games.length, 1)}</b> gol/maç</span>
          </div>
          <p className="muted tiny">Bu sezon yönettiği maçlar: ev sahibi {hw}, beraberlik {games.length - hw - aw}, deplasman {aw} galibiyet{cn ? ` · ${red} kırmızı kart` : ""}{cn && cn < games.length ? ` · kart verisi ${cn} maçta var` : ""}. Penaltı verisi kaynaklarda yok.</p>
        </>
      ) : <p className="muted small">Bu sezon veri havuzunda yönettiği başka maç yok.</p>}
    </Card>
  );
}

function WeatherCard({ m, w }: { m: Match; w: Dossier["weather"] }) {
  if (!w) return null;
  return (
    <Card title="Saha ve hava">
      {m.venue && <p className="small">🏟 {m.venue}{m.city ? `, ${m.city}` : ""}</p>}
      <div className="weather">
        <b className="w-temp">{num(w.temperature_c, 0)}°</b>
        <div><strong>{w.summary}</strong><p className="muted small">Yağış %{w.precip_prob ?? "—"} · Rüzgâr {num(w.wind_kmh, 0)} km/sa · Nem %{w.humidity ?? "—"}</p></div>
      </div>
      <p className="muted tiny">{w.location} · Open-Meteo{w.time_utc ? ` · ${time(w.time_utc.endsWith("Z") ? w.time_utc : w.time_utc + "Z")} TSİ` : ""}</p>
    </Card>
  );
}

function SourcesCard({ m, d }: { m: Match; d: Dossier }) {
  const all = (m.sources as { _all?: string[] })?._all ?? [];
  const c = d.picks.find((p) => p.tag === "meclis_gorusu")?.confidence ?? null;
  if (!all.length && c == null) return null;
  return (
    <Card title="Güven ve kaynak">
      {c != null && <><div className="q-score"><b>{num(c * 100, 0)}</b><span>/100</span></div><Meter value={c * 100} label="Meclis güveni" /></>}
      {all.length > 0 && <p className="muted tiny">Veri kaynakları: {all.join(", ")}</p>}
    </Card>
  );
}

function NewsCard({ d }: { d: Dossier }) {
  if (!d.news.length) return null;
  return (
    <Card title="Maçın gündemi">
      <ul className="news-mini">
        {d.news.map((x) => (
          <li key={x.id}><a href={x.link} target="_blank" rel="noopener noreferrer">{x.title}</a><span className="muted small">{x.source} · {relTime(x.published_at)}</span></li>
        ))}
      </ul>
    </Card>
  );
}

// ---------------------------------------------------------------------------------------------
// KADROLAR: resmî ilk 11 (açıklandıysa) → Meclis tahmini 11 → dış kaynak tahmini; saha dizilişi + yedekler
// ---------------------------------------------------------------------------------------------
function isOfficial(lu: Lineup) {
  return lu.lineup_status ? lu.lineup_status === "resmi" : !/tahmin/i.test(lu.source ?? "");
}
type XiPlayer = { name: string; position?: string | null; score?: number; note?: string | null; number?: number | null };
const POS_TR: Record<string, string> = { Goalkeeper: "K", Defender: "D", Midfielder: "O", Attacker: "F", Forward: "F", G: "K", GK: "K", D: "D", DF: "D", M: "O", MF: "O", F: "F", FW: "F", K: "K", O: "O" };
const posOf = (p?: string | null) => POS_TR[p ?? ""] ?? POS_TR[(p ?? "").slice(0, 1).toUpperCase()] ?? "";

interface XIP { name: string; pos: string; number?: number | null; note?: string | null; grid?: string; captain?: boolean }
interface XI { label: string; kind: "off" | "pred"; formation: string | null; players: XIP[]; subs: string[]; coach: string | null; basis?: string[] }

/** Yapısal doğrulama: 11 oyuncu, mevkiler biliniyorsa tam bir kaleci, tekrar eden isim yok. Tutmayan kadro gösterilmez. */
function plausible(x: XI): boolean {
  if (x.players.length !== 11) return false;
  if (new Set(x.players.map((p) => p.name.toLocaleLowerCase("tr-TR"))).size !== 11) return false;
  const known = x.players.filter((p) => p.pos).length;
  return known < 10 || x.players.filter((p) => p.pos === "K").length === 1;
}

function xisFor(rows: Lineup[], side: "home" | "away", a?: AnalysisPayload): XI[] {
  return xisRaw(rows, side, a).filter((x) => x.kind === "off" || plausible(x));
}

function xisRaw(rows: Lineup[], side: "home" | "away", a?: AnalysisPayload): XI[] {
  const mine = rows.filter((x) => x.side === side);
  const out: XI[] = [];
  const conv = (lu: Lineup, label: string, kind: XI["kind"]): XI => ({
    label, kind, formation: lu.formation, coach: lu.coach, subs: (lu.subs ?? []).map((p) => p.name),
    players: lu.start_xi.map((p) => ({ name: p.name, pos: posOf(p.pos), number: p.number, grid: p.grid, captain: p.captain })),
  });
  const off = mine.find(isOfficial);
  if (off) out.push(conv(off, "Resmî ilk 11", "off"));
  const px = (a as { predicted_xi?: Record<string, { players?: XiPlayer[]; bench?: XiPlayer[]; formation?: string; basis?: string[] }> } | undefined)?.predicted_xi?.[side];
  if (px?.players?.length) {
    out.push({
      label: "Meclis tahmini 11", kind: "pred", formation: px.formation ?? null, coach: null, basis: px.basis,
      subs: (px.bench ?? []).map((p) => p.name),
      players: px.players.map((p) => ({ name: p.name, pos: posOf(p.position), number: p.number, note: p.note })),
    });
  } else {
    const ext = mine.find((x) => !isOfficial(x));
    if (ext) out.push(conv(ext, "Tahmini ilk 11", "pred"));
  }
  return out;
}

function formationOf(x: XI): string | null {
  if (x.formation) return x.formation;
  const c = { D: 0, O: 0, F: 0 } as Record<string, number>;
  for (const p of x.players) if (p.pos in c) c[p.pos]++;
  return c.D + c.O + c.F === 10 ? `${c.D}-${c.O}-${c.F}` : null;
}

/**
 * Dizilişe göre hatlar (kaleci önce): 1) API-Football "satır:sütun" ızgarası; 2) diziliş sırası (4-2-3-1 → 4,2,3,1;
 * kaynak sırası hat hat gelir); 3) mevki harfi. Hiçbiri tutmazsa null (liste gösterilir).
 */
function linesOf(x: XI): XIP[][] | null {
  const ps = x.players;
  if (ps.length !== 11) return null;
  if (ps.every((p) => p.grid && /^\d+:\d+$/.test(p.grid))) {
    const rows = new Map<number, XIP[]>();
    for (const p of ps) { const r = Number(p.grid!.split(":")[0]); rows.set(r, [...(rows.get(r) ?? []), p]); }
    return [...rows.entries()].sort((a, b) => a[0] - b[0]).map(([, l]) => l.sort((a, b) => Number(a.grid!.split(":")[1]) - Number(b.grid!.split(":")[1])));
  }
  const f = (x.formation ?? "").split("-").map(Number).filter((n) => n > 0);
  if (f.length >= 2 && f.reduce((a, b) => a + b, 0) === 10) {
    const gi = Math.max(0, ps.findIndex((p) => p.pos === "K"));
    const rest = ps.filter((_, i) => i !== gi);
    const out: XIP[][] = [[ps[gi]]];
    let k = 0;
    for (const n of f) { out.push(rest.slice(k, k + n)); k += n; }
    return out;
  }
  if (ps.filter((p) => p.pos).length >= 10) {
    const out = ["K", "D", "O", "F"].map((c) => ps.filter((p) => p.pos === c)).filter((l) => l.length);
    return out.length >= 3 ? out : null;
  }
  return null;
}

type Flag = (name: string) => "suphe" | "yok" | null;
function Chip({ p, side, flag }: { p: XIP; side: "home" | "away"; flag: Flag }) {
  const f = flag(p.name);
  return (
    <span className={`pp ${side}`}>
      <i>{p.number ?? p.name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase()}{p.captain && <em className="cap" title="Kaptan">C</em>}{f && <em className={`doubt ${f}`} title={f === "suphe" ? "Şüpheli" : "Eksik listesinde"}>!</em>}</i>
      <b>{shortName(p.name)}</b>
    </span>
  );
}

/** Tek saha: ev sahibi alt yarıda (kaleci en altta), deplasman üst yarıda (kaleci en üstte); hatlar dizilişe göre. */
function FullPitch({ home, away, flag }: { home: XI | null; away: XI | null; flag: Flag }) {
  const half = (x: XI | null, side: "home" | "away") => {
    const ls = x ? linesOf(x) : null;
    if (!ls) return null;
    const n = ls.length;
    return ls.map((l, i) => {
      // kaleci kaleye yakın; hatlar orta sahaya doğru eşit aralıkla
      const d = 5 + (i / Math.max(1, n - 1)) * 38;
      const top = side === "home" ? 100 - d : d;
      const row = side === "home" ? [...l].reverse() : l;
      return (
        <div key={`${side}${i}`} className="pf-line" style={{ top: `${top}%` }}>
          {row.map((p, j) => <Chip key={j} p={p} side={side} flag={flag} />)}
        </div>
      );
    });
  };
  const H = half(home, "home"), A = half(away, "away");
  if (!H && !A) return null;
  return (
    <div className="pf" role="img" aria-label={`Sahada: ${[home, away].filter(Boolean).map((x) => `${x!.formation ?? ""} ${x!.players.map((p) => p.name).join(", ")}`).join(" | ")}`}>
      <div className="pf-marks" aria-hidden="true"><span className="pf-mid" /><span className="pf-circle" /><span className="pf-box t" /><span className="pf-box b" /><span className="pf-six t" /><span className="pf-six b" /></div>
      {A}{H}
    </div>
  );
}
const shortName = (n: string) => { const s = n.trim().split(/\s+/); return s.length > 1 ? (n.length > 12 ? s[s.length - 1] : n) : n; };

function Squads({ m, d }: { m: Match; d: Dossier }) {
  const sides = (["home", "away"] as const).map((side) => ({ side, name: side === "home" ? m.home_name : m.away_name, xis: xisFor(d.lineups, side, d.a), dropped: xisRaw(d.lineups, side, d.a).length - xisFor(d.lineups, side, d.a).length }));
  const [pick, setPick] = useState<"off" | "pred" | null>(null);
  if (sides.every((s) => !s.xis.length)) {
    return (
      <Card title="Kadrolar">
        <p className="muted small">Resmî ilk 11 maçtan yaklaşık bir saat önce açıklanır ve burada sahaya dizilir.</p>
      </Card>
    );
  }
  const kinds = [...new Set(sides.flatMap((s) => s.xis.map((x) => x.kind)))];
  const kind = pick && kinds.includes(pick) ? pick : kinds.includes("off") ? "off" : "pred";
  const sel = sides.map((s) => s.xis.find((x) => x.kind === kind) ?? null);
  const inj = new Map(d.inj.map((x) => [x.player_name.toLocaleLowerCase("tr-TR"), x.injury_status]));
  const flag: Flag = (n) => { const st = inj.get(n.toLocaleLowerCase("tr-TR")); return st === undefined ? null : st === "şüpheli" ? "suphe" : "yok"; };
  return (
    <>
      <Card title="Sahada" aside={kinds.length > 1 ? (
        <div className="seg" role="group" aria-label="Kadro türü">
          {kinds.map((k) => <button key={k} type="button" className={k === kind ? "on" : ""} onClick={() => setPick(k)}>{k === "off" ? "Resmî" : "Tahmini"}</button>)}
        </div>) : <span className={`lu-badge ${kind}`}>{kind === "off" ? "Resmî ilk 11" : "Tahmini ilk 11"}</span>}>
        <div className="pf-head">
          <span><b>{m.away_name}</b>{sel[1] && <small>{sel[1].formation ?? formationOf(sel[1]) ?? ""}</small>}</span>
        </div>
        <FullPitch home={sel[0]} away={sel[1]} flag={flag} />
        <div className="pf-head">
          <span><b>{m.home_name}</b>{sel[0] && <small>{sel[0].formation ?? formationOf(sel[0]) ?? ""}</small>}</span>
        </div>
        <p className="muted tiny pf-legend"><em className="cap">C</em> kaptan · <em className="doubt suphe">!</em> şüpheli · <em className="doubt yok">!</em> eksik listesinde{kind === "pred" ? " · tahmini kadro, resmî 11 maçtan yaklaşık bir saat önce gelir" : ""}</p>
      </Card>
      <div className="two-cards">
        {sides.map((s, i) => {
          const x = sel[i];
          if (!x) return null;
          return (
            <Card key={s.side} title={s.name} aside={<span className="muted small">{x.formation ?? formationOf(x) ?? ""}</span>}>
              <ol className="lu-list">{x.players.map((p, j) => <li key={j}><span className="lu-no">{p.number ?? ""}</span>{p.name}{p.captain && <em className="cap">C</em>}{flag(p.name) && <em className={`doubt ${flag(p.name)}`}>!</em>}<small>{p.pos}</small></li>)}</ol>
              {x.subs.length > 0 && <p className="muted tiny"><b>Yedekler:</b> {x.subs.join(", ")}</p>}
              {x.coach && <p className="muted tiny"><b>Teknik direktör:</b> {x.coach}</p>}
              {x.basis?.length ? <p className="muted tiny">Dayanak: {x.basis.join(", ")}</p> : null}
            </Card>
          );
        })}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------------------------
// EKSİKLER: oyuncu oyuncu ağırlık (dakika payı, gol katkısı, savunma katkısı, kesinlik) ve takım Eksik Etkisi
// ---------------------------------------------------------------------------------------------
interface Miss {
  name: string; kind?: string; reason?: string | null; importance?: number | null; minutes_share?: number | null;
  ga_share?: number | null; certainty?: number | null; is_key?: boolean | null; group?: string | null; known?: boolean;
  def?: number | null; replacement?: string | null; components?: { ad?: string; name?: string; deger?: number; value?: number }[];
}
const GROUP_TR: Record<string, string> = { GK: "Kaleci", DEF: "Defans", MID: "Orta saha", ATT: "Hücum" };

function Absences({ m, d }: { m: Match; d: Dossier }) {
  const ie = (d.a?.injury_effect ?? {}) as Record<string, unknown>;
  return (
    <>
      <div className="two-cards">
        {(["home", "away"] as const).map((side) => {
          const teamId = side === "home" ? m.home_team_id : m.away_team_id;
          const name = side === "home" ? m.home_name : m.away_name;
          const tbl = d.inj.filter((x) => sameTeam(x.team_id, teamId));
          const byName = new Map(tbl.map((x) => [x.player_name.toLocaleLowerCase("tr-TR"), x]));
          let list: Miss[] = ((ie[`${side}_missing`] as Miss[] | undefined) ?? []).map((x) => {
            const t = byName.get(x.name.toLocaleLowerCase("tr-TR"));
            return { ...x, def: t?.defensive_contribution ?? null, is_key: x.is_key ?? t?.is_key ?? null, minutes_share: x.minutes_share ?? t?.minutes_share ?? null, ga_share: x.ga_share ?? t?.goal_contribution ?? null };
          });
          if (!list.length) list = tbl.map((t) => ({
            name: t.player_name, kind: t.injury_status ?? undefined, reason: t.reason, importance: t.weight_score, minutes_share: t.minutes_share,
            ga_share: t.goal_contribution, def: t.defensive_contribution, is_key: t.is_key,
          }));
          list.sort((x, y) => (y.importance ?? 0) - (x.importance ?? 0));
          const fromModel = ((ie[`${side}_missing`] as unknown[] | undefined) ?? []).length > 0;
          // Analiz eksik listesi gelmeden çalıştıysa takım puanı bayattır: gösterilmez (oyuncu listesi gösterilir).
          const stale = !fromModel && list.length > 0;
          const tee = stale ? undefined : ie[`${side}_tee`], band = ie[`${side}_band`], mult = ie[`${side}_mult`];
          return (
            <Card key={side} title={name}>
              {typeof tee === "number" && (
                <div className="tee-box">
                  <div className="tee"><span>Eksik Etkisi</span><b>{num(tee, 0)}</b><small>/100 · {String(band ?? "")}</small></div>
                  <Meter value={tee} label={`Eksik Etkisi ${num(tee, 0)}/100`} />
                  {typeof mult === "number" && Math.abs(mult - 1) >= 0.005 && (
                    <p className="muted tiny">Modelde bu takımın gol beklentisine etkisi: <b>{signed((mult - 1) * 100, 1)}%</b> (kendi eksiklerinin hücuma, rakibin eksiklerinin savunmaya etkisi birlikte).</p>
                  )}
                </div>
              )}
              {stale && <p className="muted tiny">Bu eksikler son model hesabından sonra bildirildi; Eksik Etkisi bir sonraki hesapta güncellenir.</p>}
              {!list.length ? <p className="muted small">Bildirilen sakat veya cezalı oyuncu yok.</p> : (
                <ul className="injuries">
                  {list.map((r, i) => (
                    <li key={i}>
                      <div className="inj-head">
                        <b>{r.name}</b>
                        {r.is_key && <span className="key-badge">Kilit</span>}
                        {r.group && GROUP_TR[r.group] && <span className="muted tiny">{GROUP_TR[r.group]}</span>}
                        <span className={`inj-st ${/şüpheli|doubt/i.test(r.kind ?? "") ? "doubt" : /ceza|susp/i.test(r.kind ?? "") ? "susp" : "out"}`}>{r.kind ?? "eksik"}</span>
                      </div>
                      {r.importance != null && (
                        <div className="inj-w" title={`Önem ağırlığı ${num(r.importance)} / 1`}><span style={{ width: `${Math.round(r.importance * 100)}%` }} /></div>
                      )}
                      <span className="muted tiny">
                        {[r.reason, r.importance != null ? `ağırlık ${num(r.importance * 100, 0)}/100` : null,
                          r.minutes_share != null ? `dakika payı ${pct(r.minutes_share)}` : null,
                          r.ga_share != null ? `gol+asist payı ${pct(r.ga_share)}` : null,
                          r.def != null ? `savunma katkısı ${pct(r.def)}` : null,
                          r.certainty != null && r.certainty < 1 ? `kesinlik ×${num(r.certainty, 1)}` : null,
                          r.replacement ? `yerine: ${r.replacement}` : null].filter(Boolean).join(" · ")}
                      </span>
                      {r.known === false && r.minutes_share == null && <span className="muted tiny"> · bu sezon dakika verisi yok, temel ağırlıkla sayıldı</span>}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          );
        })}
      </div>
      <Card title="Eksik Etkisi nasıl okunur?">
        <p className="small">Her eksik oyuncuya 0–1 arası bir ağırlık verilir: bu sezonki dakika payı, ilk 11 payı ve takımın gol+asistlerindeki payı birlikte tartılır. Kesin yok ve cezalı oyuncu tam, şüpheli yarım (×0,5), maç günü kararı ×0,3 sayılır. Bu sezon dakika verisi bulunmayan oyuncu temel ağırlıkla (0,15) girer. Eksiklerin toplamı takımın 0–100 arası <b>Eksik Etkisi</b>dir; aynı mevkide iki ve daha fazla eksik varsa etki büyür. Bantlar: 0–10 etkisiz, 10–25 hissedilir, 25–45 ciddi, 45 üstü ağır.</p>
        <p className="small">Model bunu iki yoldan gol beklentisine taşır: hücumcu eksikler takımın kendi gol beklentisini düşürür, defans ve kaleci eksikleri rakibinkini yükseltir. Çarpan ±%30 ile sınırlıdır.</p>
      </Card>
    </>
  );
}

// ---------------------------------------------------------------------------------------------
// FORM & İSTATİSTİK: maç maç lehte/aleyhte; Avrupa / Lig / Tümü; sahaya göre (ev sahibinin iç sahası,
// konuğun deplasmanı) veya tüm maçlar; seçili istatistiğin çizgi tutma sayıları ve belirgin seriler. Yalnızca bu sezon.
// ---------------------------------------------------------------------------------------------
type Comp = "avrupa" | "lig" | "tumu";
const COMP_LABEL: Record<Comp, string> = { avrupa: "Avrupa", lig: "Lig", tumu: "Tümü" };
const COLS: { key: MetricKey; short: string; title: string }[] = [
  { key: "gol", short: "Skor", title: "Gol (lehte–aleyhte)" }, { key: "iy", short: "İY", title: "İlk yarı golü" },
  { key: "korner", short: "Krn", title: "Korner" }, { key: "kart", short: "Kart", title: "Kart (sarı+kırmızı)" },
  { key: "sut", short: "Şut", title: "Şut" }, { key: "isabet", short: "İsb", title: "İsabetli şut" },
  { key: "kale", short: "KV", title: "Kale vuruşu" },
];

function FormTab({ m, d }: { m: Match; d: Dossier }) {
  const cup = UEFA.has(m.league);
  const H = useMemo(() => rowsFor(m, d, "home"), [m, d]);
  const A = useMemo(() => rowsFor(m, d, "away"), [m, d]);
  const hasEu = [...H, ...A].some((x) => x.comp === "avrupa");
  const [comp, setComp] = useState<Comp>(cup ? "avrupa" : "lig");
  const [venue, setVenue] = useState<"saha" | "tum">("saha");
  const [metric, setMetric] = useState<MetricKey>("gol");
  const comps: Comp[] = hasEu ? ["avrupa", "lig", "tumu"] : ["lig", "tumu"];
  const c = comps.includes(comp) ? comp : comps[0];
  const filt = (r: GameRow[], home: boolean) => r.filter((x) => (c === "tumu" || x.comp === c) && (venue === "tum" || x.home === home));

  return (
    <>
      <div className="form-ctl">
        <div className="seg" role="radiogroup" aria-label="Kulvar">
          {comps.map((k) => <button key={k} type="button" role="radio" aria-checked={c === k} className={c === k ? "on" : ""} onClick={() => setComp(k)}>{COMP_LABEL[k]}</button>)}
        </div>
        <div className="seg" role="radiogroup" aria-label="Saha">
          <button type="button" role="radio" aria-checked={venue === "saha"} className={venue === "saha" ? "on" : ""} onClick={() => setVenue("saha")}>Sahaya göre</button>
          <button type="button" role="radio" aria-checked={venue === "tum"} className={venue === "tum" ? "on" : ""} onClick={() => setVenue("tum")}>Tüm maçlar</button>
        </div>
      </div>
      <div className="chips scroll metric-chips" role="radiogroup" aria-label="İstatistik">
        {METRICS.map((x) => <button key={x.key} type="button" role="radio" aria-checked={metric === x.key} className={`chip ${metric === x.key ? "on" : ""}`} onClick={() => setMetric(x.key)}>{x.label}</button>)}
      </div>
      <p className="muted tiny form-scope">
        {c === "avrupa" ? "Avrupa'da bu sezon (ön eleme dahil)" : c === "lig" ? "Ligde bu sezon" : "Bu sezon bütün kulvarlar (lig, Avrupa, kupa)"}
        {" · "}{venue === "saha" ? `${m.home_name} iç sahada, ${m.away_name} deplasmanda` : "iç saha ve deplasman birlikte"} · her satır bir maç, değerler lehte–aleyhte
      </p>
      {hasEu && <CompSummary m={m} H={H} A={A} />}
      {c === "avrupa" && cup && d.phaseKey && <PhaseStrip m={m} rows={d.tables[d.phaseKey]} />}
      <div className="two-cards">
        <TeamForm name={m.home_name} rows={filt(H, true)} all={H} metric={metric} scope={venue === "saha" ? "iç saha" : ""} comp={c} />
        <TeamForm name={m.away_name} rows={filt(A, false)} all={A} metric={metric} scope={venue === "saha" ? "deplasman" : ""} comp={c} />
      </div>
    </>
  );
}

function PhaseStrip({ m, rows }: { m: Match; rows: TableRow[] }) {
  const mine = rows.filter((r) => r.id === m.home_team_id || r.id === m.away_team_id);
  if (!mine.length) return null;
  return (
    <div className="phase-strip">
      <span className="kicker">{league(m.league).name} · lig aşaması</span>
      {mine.map((r) => (
        <span key={r.id} className="ps-team"><b>{r.pos}.</b> {r.name} <span className="muted">{r.p} maç · {r.w}G {r.d}B {r.l}M · {r.gf}-{r.ga} · <b>{r.pts} P</b></span>
          <em className={r.pos <= 8 ? "pos" : r.pos <= 24 ? "" : "neg"}>{r.pos <= 8 ? "ilk 8" : r.pos <= 24 ? "play-off hattı" : "elenme hattı"}</em></span>
      ))}
    </div>
  );
}

function TeamForm({ name, rows, all, metric, scope, comp }: { name: string; rows: GameRow[]; all: GameRow[]; metric: MetricKey; scope: string; comp: Comp }) {
  const def = METRICS.find((x) => x.key === metric)!;
  const fl = (n: number) => fmtLine(n);
  const scopeWord = `${comp === "avrupa" ? "Avrupa " : comp === "lig" ? "lig " : ""}${scope}`.trim() || "son";
  const st = METRICS.flatMap((x) => streaks(rows, x.key, scopeWord, fl)).slice(0, 4);
  const vals = rows.map((r) => r.vals[metric]).filter((v): v is [number, number] => !!v && v[0] != null && v[1] != null);
  const w = rows.filter((r) => r.res === "G").length, dr = rows.filter((r) => r.res === "B").length;
  const avg = (i: 0 | 1) => (vals.length ? vals.reduce((s, v) => s + v[i], 0) / vals.length : null);
  if (!all.length) return <Card title={name}><p className="muted small">Bu sezon veri havuzunda bitmiş maçı yok.</p></Card>;
  return (
    <Card title={name} aside={<span className="muted tiny">{rows.length} maç</span>}>
      {!rows.length ? <p className="muted small">Bu seçimde bu sezon oynanmış maç yok.</p> : (
        <>
          <div className="form-dots" aria-label="Sonuçlar, yeniden eskiye">{rows.slice(0, 10).map((r) => <span key={r.m.id} className={`fd r-${r.res}`} title={`${r.m.home_name} ${r.m.home_goals}-${r.m.away_goals} ${r.m.away_name}`}>{r.res}</span>)}</div>
          <div className="mini-stats">
            <span><b>{w}G {dr}B {rows.length - w - dr}M</b></span>
            {metric === "kg" ? (
              <span>KG Var <b>{rows.filter((r) => r.gf > 0 && r.ga > 0).length}/{rows.length}</b></span>
            ) : vals.length > 0 && (
              <>
                <span>{def.label} lehte <b>{num(avg(0), 1)}</b></span><span>aleyhte <b>{num(avg(1), 1)}</b></span>
                {vals.length < rows.length && <span className="muted">({vals.length} maçta veri)</span>}
              </>
            )}
          </div>
          {metric !== "kg" && vals.length > 0 && (
            <div className="line-hits">
              {def.lines.map((ln) => { const k = vals.filter((v) => v[0] + v[1] > ln).length; return <span key={`t${ln}`} className={k / vals.length >= 0.7 ? "hot" : k / vals.length <= 0.3 ? "cold" : ""}>Toplam {fl(ln)} Üst <b>{k}/{vals.length}</b></span>; })}
              {def.teamLines.map((ln) => { const k = vals.filter((v) => v[0] > ln).length; return <span key={`f${ln}`} className={k / vals.length >= 0.7 ? "hot" : k / vals.length <= 0.3 ? "cold" : ""}>Takım {fl(ln)} Üst <b>{k}/{vals.length}</b></span>; })}
            </div>
          )}
          {st.length > 0 && <ul className="streaks">{st.map((s, i) => <li key={i}>🔥 {s.charAt(0).toLocaleUpperCase("tr-TR") + s.slice(1)}</li>)}</ul>}
          <div className="table-wrap">
            <table className="tbl tight mm-tbl">
              <thead><tr><th>Tarih</th><th>Rakip</th>{COLS.map((x) => <th key={x.key} title={x.title} className={x.key === metric || (metric === "kg" && x.key === "gol") ? "sel" : ""}>{x.short}</th>)}</tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.m.id}>
                    <td>{dateShort(r.m.kickoff_at)}</td>
                    <td className="opp"><Link to={matchPath(r.m.id)}>{r.home ? "" : "@ "}{r.opp}</Link>{r.comp !== "lig" && <small className={`comp ${r.comp}`}>{r.comp === "avrupa" ? r.m.league : "Kupa"}</small>}{r.stage && r.stage !== "Lig aşaması" && <small className="comp diger" title={r.stage}>{r.stage.startsWith("Ön") ? "ÖE" : "ET"}</small>}</td>
                    {COLS.map((x) => {
                      const v = r.vals[x.key];
                      const sel = x.key === metric || (metric === "kg" && x.key === "gol");
                      const ok = v && v[0] != null && v[1] != null;
                      return <td key={x.key} className={`${sel ? "sel" : ""} ${x.key === "gol" ? `res r-${r.res}` : ""}`}>{ok ? `${v![0]}-${v![1]}` : "–"}</td>;
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted tiny">Her hücre takımın bakış açısıyla lehte–aleyhte; "@" deplasman. Krn korner, İsb isabetli şut, KV kale vuruşu; ÖE ön eleme/play-off. "–": o maç için kaynakta veri yok.</p>
        </>
      )}
    </Card>
  );
}

/** Avrupa ve lig yan yana: iki kulvarın bu sezonki özeti (iç saha / deplasman ayrımıyla). */
function CompSummary({ m, H, A }: { m: Match; H: GameRow[]; A: GameRow[] }) {
  const sum = (r: GameRow[]) => {
    const n = r.length, w = r.filter((x) => x.res === "G").length, dd = r.filter((x) => x.res === "B").length;
    return n ? `${n} maç · ${w}G ${dd}B ${n - w - dd}M · ${num(r.reduce((s, x) => s + x.gf, 0) / n, 1)}–${num(r.reduce((s, x) => s + x.ga, 0) / n, 1)}` : "—";
  };
  const teams: [string, GameRow[], boolean][] = [[m.home_name, H, true], [m.away_name, A, false]];
  return (
    <div className="comp-sum table-wrap">
      <table className="tbl tight">
        <thead><tr><th>Takım</th><th>Avrupa'da bu sezon</th><th>Ligde bu sezon</th></tr></thead>
        <tbody>
          {teams.map(([n, r, home]) => (
            <tr key={n}>
              <td><b>{n}</b><small className="muted"> {home ? "iç saha" : "deplasman"}</small></td>
              <td>{sum(r.filter((x) => x.comp === "avrupa"))}<br /><small className="muted">{home ? "evinde" : "dışarıda"}: {sum(r.filter((x) => x.comp === "avrupa" && x.home === home))}</small></td>
              <td>{sum(r.filter((x) => x.comp === "lig"))}<br /><small className="muted">{home ? "evinde" : "dışarıda"}: {sum(r.filter((x) => x.comp === "lig" && x.home === home))}</small></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted tiny">Maç · galibiyet-beraberlik-mağlubiyet · maç başı atılan–yenilen gol.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// KARŞILAŞMALAR
// ---------------------------------------------------------------------------------------------
function H2HTab({ m, d }: { m: Match; d: Dossier }) {
  const g = d.h2h.filter(hasScore);
  if (!g.length) return <Card title="Aralarındaki maçlar"><p className="muted small">Veri havuzunda bu iki takımın oynadığı bir maç yok.</p></Card>;
  const rows = gameRows(g, m.home_team_id, d.stats);
  const w = rows.filter((x) => x.res === "G").length, dr = rows.filter((x) => x.res === "B").length;
  const goals = rows.reduce((s, x) => s + x.gf + x.ga, 0);
  const o25 = rows.filter((x) => x.gf + x.ga > 2.5).length, kg = rows.filter((x) => x.gf > 0 && x.ga > 0).length;
  return (
    <Card title="Aralarındaki maçlar" aside={<span className="muted tiny">veri havuzundaki son {g.length} maç</span>}>
      <div className="mini-stats">
        <span>{m.home_name} <b>{w}</b></span><span>Beraberlik <b>{dr}</b></span><span>{m.away_name} <b>{rows.length - w - dr}</b></span>
        <span>Maç başı <b>{num(goals / rows.length, 1)}</b> gol</span><span>2,5 Üst <b>{o25}/{rows.length}</b></span><span>KG Var <b>{kg}/{rows.length}</b></span>
      </div>
      <div className="table-wrap">
        <table className="tbl tight">
          <thead><tr><th>Tarih</th><th>Kulvar</th><th>Maç</th><th>İY</th><th title="Korner (ev–dep)">Krn</th><th title="Kart (ev–dep)">Kart</th></tr></thead>
          <tbody>
            {rows.map((r) => {
              const x = r.m; const hv = r.home;
              const flip = (v?: [number | null, number | null]) => (v && v[0] != null && v[1] != null ? (hv ? `${v[0]}-${v[1]}` : `${v[1]}-${v[0]}`) : "–");
              return (
                <tr key={x.id}>
                  <td>{dateShort(x.kickoff_at)}.{x.kickoff_at.slice(2, 4)}</td><td><small>{league(x.league).name}</small></td>
                  <td><Link to={matchPath(x.id)}>{x.home_name} <b>{x.home_goals}-{x.away_goals}</b> {x.away_name}</Link></td>
                  <td>{x.ht_home_goals != null ? `${x.ht_home_goals}-${x.ht_away_goals}` : "–"}</td><td>{flip(r.vals.korner)}</td><td>{flip(r.vals.kart)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted tiny">Aralarındaki maçlar sezondan bağımsızdır; Meclis'in modeli bunları değil bu sezonki formu esas alır.</p>
    </Card>
  );
}

// ---------------------------------------------------------------------------------------------
// ORANLAR & OLASILIKLAR
// ---------------------------------------------------------------------------------------------
function OddsTab({ m, d }: { m: Match; d: Dossier }) {
  const a = d.a;
  const own = modelOwn(a) && !!a?.ready;
  const rows = useMemo(() => scanMatch(m, a?.markets, own), [m, a, own]);
  const picked = new Set(d.picks.map((p) => `${p.market}|${p.selection}|${p.line ?? ""}`));
  const p1 = Object.fromEntries((a?.markets ?? []).filter((x) => x.market === "1X2").map((x) => [x.selection, x.probability]));
  const imp = implied1x2(m);
  const srcs = [...new Set(Object.values(m.odds ?? {}).map((g) => sourceLabel(String((g as Record<string, unknown>)?.src ?? ""))).filter(Boolean))];
  return (
    <>
      <Card title="Maç sonucu: Meclis ve piyasa">
        {own && p1["1"] !== undefined && <div className="pb-block"><span className="kicker">Meclis</span><ProbBar p1={p1["1"]} px={p1["X"]} p2={p1["2"]} home={m.home_name} away={m.away_name} /></div>}
        {imp && <div className="pb-block"><span className="kicker">Piyasa (marjsız)</span><ProbBar p1={imp[0]} px={imp[1]} p2={imp[2]} home={m.home_name} away={m.away_name} /></div>}
        {!own && a?.markets?.length ? <p className="muted tiny">Bu maçta olasılıklar piyasa oranından türetildi ({a.basis}); bu yüzden değer sütunu boş kalır.</p> : null}
        {srcs.length > 0 && <p className="muted tiny">Oran kaynağı: {srcs.join(", ")}. Oranlar değişebilir.</p>}
      </Card>
      <OddsMove m={m} snaps={d.snaps} />
      {a?.lambdas && <ScoreGrid m={m} a={a} />}
      <Card title="Bütün pazarlar" aside={<span className="muted tiny">{rows.length} seçim</span>}>
        {rows.length ? <ScanTable rows={rows} home={m.home_name} away={m.away_name} picked={picked} /> : <p className="muted small">Bu maç için pazar verisi yok.</p>}
      </Card>
    </>
  );
}

/** Oran hareketi: odds_snapshots kayıtlarından açılış → güncel (en az iki görüntü varsa; yoksa hiç gösterilmez). */
const MOVE_KEYS: [string, string[], string][] = [["1X2", ["1", "X", "2"], "Maç sonucu"], ["OU_GOALS_2.5", ["ALT", "ÜST"], "2,5 Gol"], ["BTTS", ["VAR", "YOK"], "KG"]];
function OddsMove({ m, snaps }: { m: Match; snaps: api.OddsSnap[] }) {
  if (snaps.length < 2) return null;
  const first = snaps[0], last = snaps[snaps.length - 1];
  const val = (o: api.OddsSnap, k: string, sel: string) => { const v = o.odds?.[k]?.[sel]; return typeof v === "number" && v > 1 ? v : null; };
  const rows = MOVE_KEYS.flatMap(([k, sels, label]) => sels.map((sel) => {
    const series = snaps.map((x) => val(x, k, sel)).filter((v): v is number => v != null);
    const a = val(first, k, sel), b = val(last, k, sel);
    return a && b ? { k, sel, label, a, b, series } : null;
  })).filter((x): x is NonNullable<typeof x> => !!x);
  if (!rows.length) return null;
  const selName = (k: string, sel: string) => pickLabel(k === "1X2" ? "1X2" : k === "BTTS" ? "BTTS" : "OU_GOALS", sel, k.startsWith("OU_") ? 2.5 : null, m.home_name, m.away_name);
  return (
    <Card title="Oran hareketi" aside={<span className="muted tiny">{snaps.length} görüntü · {dateTime(first.taken_at)} → {dateTime(last.taken_at)}</span>}>
      <div className="table-wrap">
        <table className="tbl tight odds-move">
          <thead><tr><th>Seçim</th><th>Açılış</th><th>Güncel</th><th>Değişim</th><th></th></tr></thead>
          <tbody>
            {rows.map((r) => {
              const ch = (r.b - r.a) / r.a;
              return (
                <tr key={r.k + r.sel}>
                  <td>{selName(r.k, r.sel)}</td><td>{num(r.a)}</td><td><b>{num(r.b)}</b></td>
                  <td className={Math.abs(ch) < 0.01 ? "muted" : ch < 0 ? "pos" : "neg"}>{Math.abs(ch) < 0.005 ? "—" : `${ch < 0 ? "▼" : "▲"} ${num(Math.abs(ch) * 100, 1)}%`}</td>
                  <td><Spark v={r.series} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted tiny">Düşen oran (▼) piyasanın o seçime daha çok inandığını gösterir. Kaynak: oran görüntüleri (odds_snapshots).</p>
    </Card>
  );
}
function Spark({ v }: { v: number[] }) {
  if (v.length < 2) return null;
  const lo = Math.min(...v), hi = Math.max(...v), w = 60, h = 18;
  const pts = v.map((x, i) => `${(i / (v.length - 1)) * w},${hi === lo ? h / 2 : h - ((x - lo) / (hi - lo)) * h}`).join(" ");
  return <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true"><polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>;
}

function ScoreGrid({ m, a }: { m: Match; a: AnalysisPayload }) {
  const g = poissonGrid(a.lambdas!.home, a.lambdas!.away);
  const max = Math.max(...g.flat());
  return (
    <Card title="Skor dağılımı" aside={<span className="muted tiny">satır {m.home_name}, sütun {m.away_name}</span>}>
      <div className="table-wrap">
        <table className="heat">
          <thead><tr><th></th>{g[0].map((_, j) => <th key={j}>{j}</th>)}</tr></thead>
          <tbody>
            {g.map((r, i) => (
              <tr key={i}><th>{i}</th>{r.map((p, j) => (
                <td key={j} style={{ background: `rgba(56, 189, 248, ${(p / max) * 0.85})` }} className={i > j ? "h" : i < j ? "a" : "x"} title={`${i}-${j}: ${pct(p, 1)}`}>{p >= 0.005 ? pct(p, 0) : ""}</td>
              ))}</tr>
            ))}
          </tbody>
        </table>
      </div>
      {!!a.top_scores?.length && <div className="ts-list">{a.top_scores.slice(0, 6).map(([s, pr]) => <span key={s} className="ts"><b>{s}</b>{pct(pr)}</span>)}</div>}
      <p className="muted tiny">Isı haritası gol beklentilerinden ({num(a.lambdas!.home)} – {num(a.lambdas!.away)}) bağımsız Poisson yaklaşımıdır; alttaki en olası skorlar Meclis modelinin kendi (düşük skor düzeltmeli) olasılıklarıdır.</p>
    </Card>
  );
}

// ---------------------------------------------------------------------------------------------
// SENARYOLAR
// ---------------------------------------------------------------------------------------------
function Ring({ p, hue }: { p: number | null; hue: number }) {
  const r = 26, c = 2 * Math.PI * r;
  return (
    <svg className="ring" viewBox="0 0 64 64" aria-hidden="true">
      <circle cx="32" cy="32" r={r} className="ring-bg" />
      {p != null && <circle cx="32" cy="32" r={r} className="ring-fg" stroke={`hsl(${hue} 85% 60%)`} strokeDasharray={`${c * p} ${c}`} transform="rotate(-90 32 32)" />}
      <text x="32" y="37" textAnchor="middle">{p != null ? `%${Math.round(p * 100)}` : "—"}</text>
    </svg>
  );
}

const SCN_HUES = [78, 165, 195, 280, 30, 340];

function ScenarioCard({ s, i, m }: { s: Scn; i: number; m: Match }) {
  const [reveal, setReveal] = useState(false);
  const [act, setAct] = useState<number | null>(0);
  const h = SCN_HUES[i % SCN_HUES.length];
  const tl = s.acts.filter((x) => x.at != null);
  return (
    <article className="scn2" style={{ ["--h" as string]: h }}>
      <header className="scn2-poster">
        <div><span className="scn2-no">{s.kind === "ortusen" ? "Yan hikâye" : `Senaryo ${i + 1}`}</span><h3>{s.title}</h3></div>
        {s.p != null ? <Ring p={s.p} hue={h} /> : <span className="scn2-tag">Ayrı etken</span>}
      </header>
      {s.story && <p className="scn2-story">{s.story}</p>}
      {(tl.length > 0 || s.turn?.min != null) && (
        <div className="tl" aria-label="Maçın zaman çizelgesi">
          <div className="tl-track"><span className="tl-ht" /></div>
          {tl.map((x, j) => (
            <button key={j} type="button" className={`tl-dot ${act === j ? "on" : ""}`} style={{ left: `${(x.at! / 95) * 100}%` }} onClick={() => setAct(act === j ? null : j)} aria-label={`${x.label || `${x.min}′`} ${x.title}`}>{x.label && /devre/i.test(x.label) ? "İY" : `${x.min}′`}</button>
          ))}
          {s.turn?.min != null && <span className="tl-turn" style={{ left: `${(s.turn.min / 95) * 100}%` }} title="Kırılma anı">⚡</span>}
          <div className="tl-scale"><span>0′</span><span>45′</span><span>90′</span></div>
        </div>
      )}
      {s.acts.length > 0 && (
        <ol className="acts">
          {s.acts.map((x, j) => (
            <li key={j} className={act === j ? "on" : ""}>
              <button type="button" onClick={() => setAct(act === j ? null : j)} aria-expanded={act === j}>
                <span className="a-min">{x.label || (x.min != null ? `${x.min}′` : `${j + 1}. perde`)}</span><b>{x.title || `${j + 1}. perde`}</b>
              </button>
              {(act === j || s.acts.length <= 2) && x.text && <p>{x.text}</p>}
            </li>
          ))}
        </ol>
      )}
      {s.turn && <p className="turn"><span>⚡ Kırılma anı{s.turn.min != null ? ` · ${s.turn.min}′` : ""}</span>{s.turn.text}</p>}
      {(s.final || s.scores.length > 0) && (
        <div className="final">
          {!reveal ? <button type="button" className="final-btn" onClick={() => setReveal(true)}>Final düdüğü: skoru göster</button> : (
            <div className="final-show">
              {s.final && <b className="final-score">{s.final.replace("-", " – ")}</b>}
              {s.scores.length > 0 && <span className="score-chips">{s.scores.slice(0, 4).map((x, j) => <i key={j}>{x.s}{x.p != null && <small> %{Math.round(x.p * 100)}</small>}</i>)}</span>}
            </div>
          )}
        </div>
      )}
      {s.markets.length > 0 && (
        <div className="scn-mk">
          {s.markets.slice(0, 12).map((x, j) => <span key={j} className={x.win === true ? "w" : x.win === false ? "l" : x.value != null ? "x" : ""}><b>{x.label}</b>{x.p != null ? <small>%{Math.round(x.p * 100)}</small> : x.value != null ? <small>~{num(x.value)} beklenen</small> : null}</span>)}
        </div>
      )}
      {s.signals.length > 0 && (
        <div className="signals"><span className="kicker">Canlıda izle</span><ul>{s.signals.slice(0, 4).map((x, j) => (
          <li key={j}>{x.cond && x.from != null && x.to != null
            ? <><span>{x.cond}</span><b className={x.to > x.from ? "up" : "down"}>%{Math.round(x.from * 100)} → %{Math.round(x.to * 100)}</b></>
            : x.text}</li>
        ))}</ul><small className="muted tiny">Bu senaryonun olasılığı, olay gerçekleşirse böyle değişir.</small></div>
      )}
      {s.pick && <p className={`scn-pick ${s.pick.win === true ? "w" : s.pick.win === false ? "l" : ""}`}><span>Meclis'in kararı bu senaryoda</span>{s.pick.text}{s.pick.p != null && <small> · tutma olasılığı %{Math.round(s.pick.p * 100)}</small>}</p>}
      {s.basis.length > 0 && <details className="scn-basis"><summary>Dayanaklar</summary><ul>{s.basis.map((x, j) => <li key={j}>{x}</li>)}</ul></details>}
      <p className="sr-only">{m.home_name} – {m.away_name}</p>
    </article>
  );
}

function TopScenario({ m, d, go }: { m: Match; d: Dossier; go: (k: TabKey) => void }) {
  const top = normalizeScenarios(d.a as unknown as Record<string, unknown>, m.home_name, m.away_name).filter((x) => x.p != null && x.kind === "ana").sort((x, y) => y.p! - x.p!)[0];
  if (!top) return null;
  return (
    <button type="button" className="topscn" onClick={() => go("senaryo")}>
      <Ring p={top.p} hue={SCN_HUES[0]} />
      <span><small>En olası senaryo</small><b>{top.title}</b>{top.story && <em>{top.story}</em>}</span>
      <i aria-hidden="true">›</i>
    </button>
  );
}

function ScenarioTab({ m, d }: { m: Match; d: Dossier }) {
  const a = d.a;
  const published = d.picks.length > 0;
  const list = useMemo(() => normalizeScenarios(a as unknown as Record<string, unknown>, m.home_name, m.away_name)
    .sort((x, y) => (x.kind === y.kind ? 0 : x.kind === "ana" ? -1 : 1) || (y.p ?? -1) - (x.p ?? -1)), [a, m.home_name, m.away_name]);
  const meta = useMemo(() => scenarioMeta(a as unknown as Record<string, unknown>), [a]);
  if (!a) return null;
  return (
    <>
      {list.length > 0 && (
        <section className="scn-wrap" aria-label="Senaryolar">
          <div className="scn-intro"><h2>Maçı kafanda oynat</h2><p className="muted small">Meclis modelinin olası akışları, en olasıdan başlayarak. Kaydır, perdelere dokun, finali aç.</p></div>
          <div className="scn-rail">{list.map((s, i) => <ScenarioCard key={i} s={s} i={i} m={m} />)}</div>
          <p className="muted tiny">{meta.mainSum != null
            ? `Numaralı senaryolar birbirini dışlar ve maçın %${Math.round(meta.mainSum * 100)}'ini kapsar; yan hikâyeler (erken gol, son 20 dakika, hakem) bunların üstüne biner.${meta.sims ? ` ${meta.sims.toLocaleString("tr-TR")} maçlık benzetimden.` : ""}`
            : `Olasılıklar birbirini dışlamaz (ör. "gollü akış" ile "ev sahibi oyunu kurar" aynı maçta birlikte olabilir); her biri kendi başına modelden okunur.`}</p>
        </section>
      )}
      {meta.whatIf && <Card title="Eksikler oynasaydı"><p className="small">{meta.whatIf}</p></Card>}
      {a.narrative && <Card title="Meclis'in notu"><div className="an"><MiniMd text={a.narrative} skipFirst published={published} /></div></Card>}
      <Card title="Meclis'in yaklaşımı"><Approach a={a} m={m} /></Card>
    </>
  );
}

/** Kararın gerekçesi, kaydedilmiş sayılardan düz Türkçe cümleyle (teknik kısaltma yok). */
function why(p: Prediction, a: AnalysisPayload | undefined, m: Match): string {
  const out: string[] = [];
  out.push(`Meclis bu sonuca ${pct(p.probability)} olasılık veriyor${p.fair_odds ? `; adil oranı ${num(p.fair_odds)}` : ""}.`);
  if (p.odds && p.edge != null) out.push(`Piyasa ${num(p.odds)} ödüyor: beklenen değer ${signed(p.edge * 100, 1)}%.`);
  else out.push("Kayıt anında piyasa oranı yoktu; karar modelin olasılığına dayanıyor.");
  if (a?.lambdas) out.push(`Gol beklentisi ${m.home_name} ${num(a.lambdas.home)}, ${m.away_name} ${num(a.lambdas.away)}.`);
  const ie = (a?.injury_effect ?? {}) as Record<string, number | string>;
  if (typeof ie.home_tee === "number" && typeof ie.away_tee === "number" && (ie.home_tee >= 25 || ie.away_tee >= 25))
    out.push(`Eksikler hesaba katıldı (Eksik Etkisi ${num(ie.home_tee, 0)} / ${num(ie.away_tee, 0)}).`);
  return out.join(" ");
}

/** Yayımlanmış karar: Meclis kararını net ve kararlı bir sesle söyler. */
function Verdict({ picks, a, m }: { picks: Prediction[]; a?: AnalysisPayload; m: Match }) {
  const p = picks[0];
  const label = pickLabel(p.market, p.selection, p.line, m.home_name, m.away_name);
  const odds = p.odds ?? p.fair_odds;
  const tags = [...new Set(picks.map((x) => x.tag))];
  const scen = (a?.scenarios ?? []).filter((x) => x.olasılık !== null).sort((x, y) => (y.olasılık ?? 0) - (x.olasılık ?? 0)).slice(0, 2);
  const live = p.status === "bekliyor";
  return (
    <section className={`verdict st-border-${p.status}`} aria-label="Meclis'in kararı">
      <div className="v-top">
        <span className="kicker">🗳️ Meclis'in kararı</span>
        <span className="v-tags">{tags.map((t) => <TagPill key={t} tag={t} />)}<StatusPill status={p.status} /></span>
      </div>
      <div className="v-main">
        <div>
          <h2 className="v-pick">{label}</h2>
          <p className="v-say">{live ? <>Meclis bu maçta kararını verdi: <b>{label}</b>. Maç bunu söylüyor.</> : <>Meclis'in kararı buydu: <b>{label}</b>.</>}</p>
        </div>
        {odds && <div className="v-odds"><b>{num(odds)}</b><small>{p.odds ? sourceLabel(p.odds_source) || "piyasa oranı" : "adil oran"}</small></div>}
      </div>
      <div className="v-stats">
        <span>Olasılık <b>{pct(p.probability)}</b></span>
        {p.edge !== null && <span>Değer <b className={p.edge > 0 ? "pos" : ""}>{signed(p.edge * 100, 1)}%</b></span>}
        {p.result_value && <span>Sonuç <b>{p.result_value}</b></span>}
        {p.profit !== null && !live && <span>K/Z <b className={p.profit >= 0 ? "pos" : "neg"}>{signed(p.profit)}</b></span>}
      </div>
      {p.confidence !== null && <Meter value={p.confidence * 100} label={`Meclis güveni ${num(p.confidence * 100, 0)}/100`} />}
      <div className="v-why"><h3>Neden?</h3><p>{why(p, a, m)}</p></div>
      {(p.scenario_note || scen.length > 0) && (
        <div className="v-scn"><h3>Maçın akışı</h3>
          {p.scenario_note && !scen.length && <p>{p.scenario_note}</p>}
          {scen.length > 0 && <ul>{scen.map((x) => <li key={x.ad}><b>{x.ad}</b> ({pct(x.olasılık)}): {x.anlatım}</li>)}</ul>}
        </div>
      )}
      <p className="v-lock"><span aria-hidden="true">🔒</span> Maçtan {hoursBefore(p.recorded_at, p.kickoff_at)} kilitlendi · kayıt {dateTime(p.recorded_at)} TSİ</p>
      <p className="v-note">18+ · Garanti yoktur; karar bir olasılık değerlendirmesidir.</p>
    </section>
  );
}

/** Sistemin yaklaşımı: bu maçta modelin neye dayandığı (saklanan analizden). */
function Approach({ a, m }: { a: AnalysisPayload; m: Match }) {
  const cs = a.current_season_matches;
  const ie = (a.injury_effect ?? {}) as Record<string, number | string>;
  const items: string[] = [];
  if (a.basis) items.push(`Gol beklentisinin dayanağı: ${a.basis}.`);
  if (cs && (cs.home || cs.away)) items.push(`Bu sezon oynanan maçlar: ${m.home_name} ${cs.home ?? 0}, ${m.away_name} ${cs.away ?? 0}. Model bu sezon genelinde çalışır.`);
  if (typeof ie.home_tee === "number" && typeof ie.away_tee === "number")
    items.push(`Eksikler ağırlıklı okundu: Eksik Etkisi ${m.home_name} ${num(ie.home_tee, 0)} (${ie.home_band ?? ""}), ${m.away_name} ${num(ie.away_tee, 0)} (${ie.away_band ?? ""}).`);
  if (a.weather?.summary) items.push(`Hava: ${a.weather.summary}, ${num(a.weather.temperature_c, 0)}°C, rüzgâr ${num(a.weather.wind_kmh, 0)} km/sa.`);
  items.push("Her pazar (skor, gol, korner, kart, isabetli şut, kale vuruşu) ayrı hesaplanır; yalnızca piyasa fiyatına göre değer taşıyan seçim karara dönüşür.");
  return (
    <div className="approach"><ul>{items.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
  );
}


/** Sezon simülasyonundan iki takımın sezon sonu tablosu (yalnızca bugünkü puan durumuyla tutan hesap). */
function SeasonStakes({ m }: { m: Match }) {
  const q = useAsync(`simmd:${m.league}`, async () => {
    const [sim, tb] = await Promise.all([seasonSim(m.league), leagueTables([m.league])]);
    return sim && tb && simConsistent(sim, tb) ? sim : null;
  }, [m.league]);
  const rows = (q.data ?? []).filter((r) => sameTeam(r.team_id, m.home_team_id) || sameTeam(r.team_id, m.away_team_id));
  if (rows.length !== 2) return null;
  const [h, a] = sameTeam(rows[0].team_id, m.home_team_id) ? rows : [rows[1], rows[0]];
  const cell = (p: number) => (p <= 0 ? "%0" : p < 0.005 ? "<%1" : `%${Math.round(p * 100)}`);
  const hasK = h.kume > 0 || a.kume > 0;
  return (
    <Card title="Sezon sonu ne diyor?" aside={<Link to={`/sezon-simulasyonu?lig=${m.league}`} className="more">Bütün tablo →</Link>}>
      <div className="sim2">
        {[h, a].map((r) => (
          <div key={r.team_id} className="sim2-t">
            <b>{r.team_name}</b>
            <span className="sim2-rank">{r.tahmini_sira}.<small> bitirir</small></span>
            <span className="muted small">{r.mevcut_puan} puan → ~{Math.round(r.ort_puan)}</span>
            {([["Şampiyon", r.sampiyon, "g"], ["İlk 4", r.ilk4, "g"], ...(hasK ? [["Düşme", r.kume, "r"]] : [])] as [string, number, string][]).map(([l, p, c]) => (
              <span key={l} className="sim2-bar"><em>{l}</em><i><u className={c} style={{ width: `${Math.max(p > 0 ? 2 : 0, p * 100)}%` }} /></i><strong>{cell(p)}</strong></span>
            ))}
          </div>
        ))}
      </div>
      <p className="muted tiny">Kalan fikstür {h.kosu.toLocaleString("tr-TR")} kez oynatıldı.</p>
    </Card>
  );
}
