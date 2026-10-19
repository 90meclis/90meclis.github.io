import { Link, useParams, useSearchParams } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { dateLong, dateShort, num, pct, relTime, signed, time } from "../lib/format";
import { MARKET_GROUPS, league, pickLabel, sourceLabel, fmtLine } from "../lib/labels";
import { hasScore, matchPath, matchState, result } from "../lib/match";
import { usePageMeta } from "../lib/seo";
import type { AnalysisPayload, Injury, Lineup, Match, MatchStat, Prediction } from "../lib/types";
import { Card, Disclaimer, Empty, Gate, Meter, Skeleton, Stat } from "../components/ui";
import { ProbBar } from "../components/charts";
import { MiniMd } from "../components/MiniMd";
import { PickCard } from "../components/PickCard";

export default function MatchDetail() {
  const { id } = useParams();
  const [sp] = useSearchParams();
  const mid = sp.get("id") ?? (id ? decodeURIComponent(id) : "");
  const mq = useAsync(`match:${mid}`, () => api.match(mid), [mid]);
  const m = mq.data;
  usePageMeta(m ? `${m.home_name} – ${m.away_name}` : "Maç", m ? `${m.home_name} – ${m.away_name} maç analizi: form, istatistik, eksikler, ilk 11, oranlar ve Meclis senaryoları.` : undefined);

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

function Detail({ m }: { m: Match }) {
  const an = useAsync(`an:${m.id}`, () => api.analysisFor(m.id), [m.id]);
  const preds = useAsync(`mp:${m.id}`, () => api.predictionsForMatch(m.id), [m.id]);
  const a: AnalysisPayload | undefined = an.data?.[0]?.payload;
  const st = matchState(m);
  const sc = hasScore(m);
  const l = league(m.league);

  return (
    <div className="detail">
      <nav className="crumbs" aria-label="Konum"><Link to="/mac-merkezi">Maç Merkezi</Link> <span aria-hidden="true">/</span> <Link to={`/mac-merkezi?gun=${m.kickoff_at.slice(0, 10)}&lig=${m.league}`}>{l.name}</Link></nav>
      <section className="scoreboard">
        <div className="sb-meta"><span>{l.flag} {l.name}</span><span>{dateLong(m.kickoff_at)} · {time(m.kickoff_at)} TSİ</span></div>
        <div className="sb-main">
          <h1 className="sb-team home">{m.home_name}</h1>
          <div className="sb-score">
            {sc ? <span className="sb-goals">{m.home_goals}<i>–</i>{m.away_goals}</span> : <span className="sb-time">{time(m.kickoff_at)}</span>}
            {st.label && <span className={`mstate ${st.key}`}>{st.label}</span>}
            {m.ht_home_goals !== null && sc && <small className="muted">İY {m.ht_home_goals}-{m.ht_away_goals}</small>}
          </div>
          <h1 className="sb-team away">{m.away_name}</h1>
        </div>
        <div className="sb-foot">
          {m.venue && <span>🏟 {m.venue}{m.city ? `, ${m.city}` : ""}</span>}
          {m.referee && <span>Hakem: {m.referee}</span>}
        </div>
      </section>

      <div className="detail-grid">
        <div className="col-main">
          <Card title="Meclisin analizi" className="analysis">
            <Gate loading={an.loading} error={an.error} rows={3}>
              {a?.ready || a?.markets?.length ? <AnalysisView a={a} m={m} /> : <PreAnalysis m={m} />}
            </Gate>
          </Card>

          {!!preds.data?.length && (
            <Card title="Bu maçtaki kararlar">
              <div className="picks">{preds.data.map((p) => <PickCard key={p.id} p={p} />)}</div>
            </Card>
          )}

          <FormAndStats m={m} />
          <Squads m={m} a={a} />
        </div>

        <aside className="col-side">
          <OddsCard m={m} />
          <WeatherCard m={m} a={a} />
          <H2H m={m} />
          <NewsCard m={m} />
          <ConfidenceCard a={a} preds={preds.data ?? []} m={m} />
        </aside>
      </div>
      <Disclaimer />
    </div>
  );
}

function ConfidenceCard({ a, preds, m }: { a?: AnalysisPayload; preds: Prediction[]; m: Match }) {
  const single = preds.find((p) => p.tag === "meclis_gorusu");
  const c = single?.confidence ?? a?.best_pick?.confidence ?? null;
  const all = (m.sources as { _all?: string[] })?._all ?? [];
  if (c === null && !all.length) return null;
  return (
    <Card title="Meclis güveni">
      {c !== null ? (
        <>
          <div className="q-score"><b>{num(c * 100, 0)}</b><span>/100</span></div>
          <Meter value={c * 100} label="Meclis güveni" />
          <p className="muted tiny">Kararın sağlamlığı: model olasılığı, piyasayla uyum ve veri derinliği birlikte değerlendirilir.</p>
        </>
      ) : <p className="muted small">Güven göstergesi kararla birlikte yayımlanır.</p>}
      {all.length > 0 && <p className="muted tiny">Veri kaynakları: {all.join(", ")}</p>}
    </Card>
  );
}

type Wdl = { n: number; w: number; d: number; l: number; gf: number; ga: number; o25: number; btts: number };
function wdl(games: Match[], teamId: string): Wdl {
  const r: Wdl = { n: 0, w: 0, d: 0, l: 0, gf: 0, ga: 0, o25: 0, btts: 0 };
  for (const g of games) {
    if (!hasScore(g)) continue;
    const home = g.home_team_id === teamId;
    const gf = home ? g.home_goals! : g.away_goals!, ga = home ? g.away_goals! : g.home_goals!;
    r.n++; r.gf += gf; r.ga += ga;
    if (gf > ga) r.w++; else if (gf === ga) r.d++; else r.l++;
    if (gf + ga > 2.5) r.o25++;
    if (gf > 0 && ga > 0) r.btts++;
  }
  return r;
}

/** Model analizi henüz kaydedilmemişse: yalnızca veri havuzundaki gerçek bilgilerden çıkarılan özet. Uydurma sayı yok. */
function PreAnalysis({ m }: { m: Match }) {
  const upcoming = new Date(m.kickoff_at).getTime() > Date.now();
  const d = useAsync(`pre:${m.id}`, async () => {
    const [h, a, h2h, inj] = await Promise.all([
      api.teamHistory(m.home_team_id, m.kickoff_at, 10), api.teamHistory(m.away_team_id, m.kickoff_at, 10),
      api.headToHead(m.home_team_id, m.away_team_id, m.kickoff_at), api.injuriesFor(m),
    ]);
    return { h, a, h2h, inj };
  }, [m.id]);
  const o = m.odds ?? {};
  const g = (k: string, s: string) => { const v = o[k]?.[s]; return typeof v === "number" && v > 1 ? v : null; };
  const implied = (k: string, sels: string[]) => {
    const odds = sels.map((s) => g(k, s));
    if (odds.some((x) => x === null)) return null;
    const inv = odds.map((x) => 1 / x!);
    const sum = inv.reduce((a, b) => a + b, 0);
    return { p: inv.map((x) => x / sum), margin: sum - 1, src: sourceLabel(String(o[k]?.src ?? "")) };
  };
  const x12 = implied("1X2", ["1", "X", "2"]);
  const ou = implied("OU_GOALS_2.5", ["ALT", "ÜST"]);
  const kg = implied("BTTS", ["VAR", "YOK"]);
  const avg = (x: number, n: number) => (n ? num(x / n, 2) : "—");

  return (
    <div className="an pre">
      <p className="pre-note">
        <b>{upcoming ? "Meclisin model analizi henüz yayımlanmadı." : "Bu maç için model analizi yayımlanmadı."}</b>{" "}
        {upcoming ? "Meclis her maçı analiz eder; değerli bir seçim çıkarsa başlama saatinden saatler önce yayımlar. " : ""}
        Aşağıdakiler veri havuzundaki ham bilgilerden çıkarılmıştır; Meclis'in olasılıkları değildir.
      </p>
      {x12 && (
        <div className="pre-block">
          <h3>Piyasanın gördüğü</h3>
          <ProbBar p1={x12.p[0]} px={x12.p[1]} p2={x12.p[2]} home={m.home_name} away={m.away_name} />
          <p className="muted tiny">
            Oranlardan çıkarılan, marjı arındırılmış olasılıklar{ou ? ` · 2,5 Üst ${pct(ou.p[1])}` : ""}{kg ? ` · KG Var ${pct(kg.p[0])}` : ""}.
            {" "}Bahis marjı %{num(x12.margin * 100, 1)}{x12.src ? ` · Kaynak: ${x12.src}` : ""}.
          </p>
        </div>
      )}
      <Gate loading={d.loading} error={d.error} rows={2}>
        {d.data && (() => {
          const H = wdl(d.data.h, m.home_team_id), A = wdl(d.data.a, m.away_team_id);
          const hh = wdl(d.data.h2h, m.home_team_id);
          const injH = d.data.inj.filter((x) => x.team_id === m.home_team_id), injA = d.data.inj.filter((x) => x.team_id === m.away_team_id);
          const keyN = (r: Injury[]) => r.filter((x) => x.is_key).length;
          return (
            <>
              {(H.n > 0 || A.n > 0) && (
                <div className="pre-block">
                  <h3>Form (son maçlar)</h3>
                  <div className="table-wrap">
                    <table className="tbl tight">
                      <thead><tr><th>Takım</th><th>Maç</th><th>G-B-M</th><th>Attığı / maç</th><th>Yediği / maç</th><th>2,5 Üst</th><th>KG Var</th></tr></thead>
                      <tbody>
                        {([[m.home_name, H], [m.away_name, A]] as const).map(([n, r]) => (
                          <tr key={n}><td><b>{n}</b></td><td>{r.n}</td><td>{r.w}-{r.d}-{r.l}</td><td>{avg(r.gf, r.n)}</td><td>{avg(r.ga, r.n)}</td>
                            <td>{r.n ? `${r.o25}/${r.n}` : "—"}</td><td>{r.n ? `${r.btts}/${r.n}` : "—"}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              <div className="pre-facts">
                {hh.n > 0 ? (
                  <div><span className="kicker">Aralarındaki son {hh.n} maç</span>
                    <p>{m.home_name} {hh.w} galibiyet, {hh.d} beraberlik, {m.away_name} {hh.l} galibiyet · maç başı {avg(hh.gf + hh.ga, hh.n)} gol</p></div>
                ) : <div><span className="kicker">Aralarındaki maçlar</span><p className="muted">Veri havuzunda son karşılaşma yok.</p></div>}
                <div><span className="kicker">Eksikler</span>
                  <p>{m.home_name}: {injH.length ? `${injH.length} oyuncu${keyN(injH) ? ` (${keyN(injH)} kilit)` : ""}` : "bildirilen yok"} · {m.away_name}: {injA.length ? `${injA.length} oyuncu${keyN(injA) ? ` (${keyN(injA)} kilit)` : ""}` : "bildirilen yok"}</p></div>
              </div>
              {!x12 && H.n === 0 && A.n === 0 && <p className="muted small">Bu maç için veri havuzunda henüz yeterli bilgi yok.</p>}
            </>
          );
        })()}
      </Gate>
    </div>
  );
}

function AnalysisView({ a, m }: { a: AnalysisPayload; m: Match }) {
  const p = Object.fromEntries((a.markets ?? []).filter((x) => x.market === "1X2").map((x) => [x.selection, x.probability]));
  const bp = a.best_pick;
  return (
    <div className="an">
      {p["1"] !== undefined && <ProbBar p1={p["1"]} px={p["X"]} p2={p["2"]} home={m.home_name} away={m.away_name} />}
      <div className="stats-row">
        {a.lambdas && <Stat label={`${m.home_name} gol bekl.`} value={num(a.lambdas.home)} />}
        {a.lambdas && <Stat label={`${m.away_name} gol bekl.`} value={num(a.lambdas.away)} />}
        {a.count_info?.corners && <Stat label="Korner bekl." value={num(a.count_info.corners.total, 1)} />}
        {a.count_info?.cards && <Stat label="Kart bekl." value={num(a.count_info.cards.total, 1)} />}
        {a.count_info?.shots_on_target && <Stat label="İsabetli şut bekl." value={num(a.count_info.shots_on_target.total, 1)} />}
      </div>
      {bp && (
        <div className="best-pick">
          <span className="kicker">Meclisin seçimi</span>
          <strong>{pickLabel(bp.market, bp.selection, bp.line, m.home_name, m.away_name)}</strong>
          <span className="muted">olasılık {pct(bp.probability)} · {bp.odds ? `oran ${num(bp.odds)}` : `adil oran ${num(bp.fair_odds)}`}</span>
        </div>
      )}
      {a.narrative && <MiniMd text={a.narrative} skipFirst />}
      {!!a.scenarios?.length && (
        <div className="scenarios">
          <h3>Senaryolar</h3>
          {a.scenarios.map((s) => (
            <div key={s.ad} className="scn">
              <div className="scn-head"><b>{s.ad}</b><span>{s.olasılık !== null ? pct(s.olasılık) : ""}</span></div>
              <div className="scn-bar"><span style={{ width: `${(s.olasılık ?? 0) * 100}%` }} /></div>
              <p className="muted small">{s.anlatım}</p>
            </div>
          ))}
        </div>
      )}
      {!!a.top_scores?.length && (
        <div className="topscores"><h3>En olası skorlar</h3>
          <div className="ts-list">{a.top_scores.map(([s, pr]) => <span key={s} className="ts"><b>{s}</b>{pct(pr)}</span>)}</div>
        </div>
      )}
      {!!a.markets?.length && (
        <details className="markets">
          <summary>Tüm pazarlar ({a.markets.length})</summary>
          {Object.entries(MARKET_GROUPS).map(([g, mks]) => {
            const rows = a.markets!.filter((x) => mks.includes(x.market));
            if (!rows.length) return null;
            return (
              <div key={g} className="table-wrap">
                <table className="tbl">
                  <caption>{g}</caption>
                  <thead><tr><th>Seçim</th><th>Olasılık</th><th>Adil</th><th>Piyasa</th><th>Değer</th></tr></thead>
                  <tbody>
                    {rows.map((x, i) => (
                      <tr key={i}>
                        <td>{pickLabel(x.market, x.selection, x.line, "Ev", "Dep")}</td>
                        <td>{pct(x.probability, 1)}</td><td>{num(x.fair_odds)}</td><td>{num(x.odds)}</td>
                        <td className={x.edge && x.edge > 0 ? "pos" : ""}>{x.edge !== null && x.edge !== undefined ? `${signed(x.edge * 100, 1)}%` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </details>
      )}
    </div>
  );
}

function FormAndStats({ m }: { m: Match }) {
  const hist = useAsync(`hist:${m.id}`, async () => {
    const [h, a] = await Promise.all([api.teamHistory(m.home_team_id, m.kickoff_at, 10), api.teamHistory(m.away_team_id, m.kickoff_at, 10)]);
    const stats = await api.statsFor([...h, ...a].map((x) => x.id));
    return { h, a, stats };
  }, [m.id]);
  return (
    <Card title="Form ve maç maç istatistik" aside={<span className="muted small">Son 10 maç · ortalama değil, her maçın kendi değeri</span>}>
      <Gate loading={hist.loading} error={hist.error} rows={4}>
        {hist.data && (
          <div className="two-teams">
            <TeamSeries name={m.home_name} teamId={m.home_team_id} games={hist.data.h} stats={hist.data.stats} />
            <TeamSeries name={m.away_name} teamId={m.away_team_id} games={hist.data.a} stats={hist.data.stats} />
          </div>
        )}
      </Gate>
    </Card>
  );
}

export function TeamSeries({ name, teamId, games, stats }: { name: string; teamId: string; games: Match[]; stats: MatchStat[] }) {
  const sidx = new Map(stats.map((s) => [`${s.match_id}:${s.side}`, s]));
  if (!games.length) return <div><h3 className="ts-name">{name}</h3><p className="muted small">Geçmiş maç verisi yok.</p></div>;
  const hasXg = games.some((g) => sidx.get(`${g.id}:${g.home_team_id === teamId ? "home" : "away"}`)?.xg != null);
  return (
    <div className="team-series">
      <h3 className="ts-name">{name}</h3>
      <div className="form-dots" aria-label="Son 5 maç">
        {games.slice(0, 5).map((g) => { const r = result(g, teamId); return <span key={g.id} className={`fd r-${r}`} title={`${g.home_name} ${g.home_goals}-${g.away_goals} ${g.away_name}`}>{r}</span>; })}
      </div>
      <div className="table-wrap">
        <table className="tbl tight">
          <thead><tr><th>Tarih</th><th>Rakip</th><th>Skor</th><th title="Şut">Şut</th><th title="İsabetli şut">İsb.</th><th title="Korner">Krn</th><th title="Kart (sarı+kırmızı)">Kart</th>{hasXg && <th>xG</th>}</tr></thead>
          <tbody>
            {games.map((g) => {
              const home = g.home_team_id === teamId;
              const s = sidx.get(`${g.id}:${home ? "home" : "away"}`);
              const r = result(g, teamId);
              const card = s && (s.yellow !== null || s.red !== null) ? (s.yellow ?? 0) + (s.red ?? 0) : null;
              return (
                <tr key={g.id}>
                  <td>{dateShort(g.kickoff_at)}</td>
                  <td><Link to={matchPath(g.id)}>{home ? "" : "@ "}{home ? g.away_name : g.home_name}</Link></td>
                  <td><span className={`res r-${r}`}>{home ? `${g.home_goals}-${g.away_goals}` : `${g.away_goals}-${g.home_goals}`}</span></td>
                  <td>{s?.shots ?? "–"}</td><td>{s?.shots_on_target ?? "–"}</td><td>{s?.corners ?? "–"}</td><td>{card ?? "–"}</td>
                  {hasXg && <td>{s?.xg != null ? num(s.xg, 1) : "–"}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted tiny">Skor takımın bakış açısıyla; "@" deplasman maçı.</p>
    </div>
  );
}

function Squads({ m, a }: { m: Match; a?: AnalysisPayload }) {
  const d = useAsync(`sq:${m.id}`, async () => {
    const [inj, lu] = await Promise.all([api.injuriesFor(m), api.lineupsFor(m.id)]);
    return { inj, lu };
  }, [m.id]);
  const ie = (a?.injury_effect ?? {}) as Record<string, number | string>;
  return (
    <Card title="Eksikler ve ilk 11">
      <Gate loading={d.loading} error={d.error} rows={3}>
        {d.data && (
          <div className="two-teams">
            {(["home", "away"] as const).map((side) => {
              const teamId = side === "home" ? m.home_team_id : m.away_team_id;
              const name = side === "home" ? m.home_name : m.away_name;
              const inj = d.data!.inj.filter((x) => x.team_id === teamId).sort((x, y) => (y.weight_score ?? 0) - (x.weight_score ?? 0));
              const tee = ie[`${side}_tee`];
              return (
                <div key={side}>
                  <h3 className="ts-name">{name}</h3>
                  {typeof tee === "number" && a?.injuries_known && (
                    <div className="tee"><span>Eksik Etkisi</span><b>{num(tee, 0)}</b><small>/100 · {String(ie[`${side}_band`] ?? "")}</small></div>
                  )}
                  <Injuries rows={inj} />
                  <Lineups rows={d.data!.lu} side={side} a={a} />
                </div>
              );
            })}
          </div>
        )}
      </Gate>
    </Card>
  );
}

function Injuries({ rows }: { rows: Injury[] }) {
  if (!rows.length) return <p className="muted small">Bildirilen sakat/cezalı oyuncu yok.</p>;
  return (
    <ul className="injuries">
      {rows.map((r) => (
        <li key={r.id}>
          <div className="inj-head">
            <b>{r.player_name}</b>
            {r.is_key && <span className="key-badge">Kilit</span>}
            <span className={`inj-st ${/şüpheli/i.test(r.injury_status ?? "") ? "doubt" : /ceza/i.test(r.injury_status ?? "") ? "susp" : "out"}`}>{r.injury_status ?? "eksik"}</span>
          </div>
          <div className="inj-w" title={`Önem ağırlığı: ${num(r.weight_score)} / 1`}>
            <span style={{ width: `${Math.round((r.weight_score ?? 0) * 100)}%` }} />
          </div>
          <span className="muted tiny">{r.reason ?? ""}{r.minutes_share != null ? ` · dakika payı ${pct(r.minutes_share)}` : ""}{r.goal_contribution != null ? ` · G+A payı ${pct(r.goal_contribution)}` : ""}</span>
        </li>
      ))}
    </ul>
  );
}

function isOfficial(lu: Lineup) {
  return lu.lineup_status ? lu.lineup_status === "resmi" : !/tahmin/i.test(lu.source ?? "");
}

type XiPlayer = { name: string; position?: string | null; score?: number; note?: string | null };
const POS_TR: Record<string, string> = { Goalkeeper: "K", Defender: "D", Midfielder: "O", Attacker: "F", Forward: "F", G: "K", D: "D", M: "O", F: "F" };
const POS_ORDER: Record<string, number> = { K: 0, D: 1, O: 2, F: 3 };

/** Resmî ilk 11 (açıklandıysa) + Meclis tahmini 11 (analiz yükündeki predicted_xi). */
function Lineups({ rows, side, a }: { rows: Lineup[]; side: "home" | "away"; a?: AnalysisPayload }) {
  const mine = rows.filter((x) => x.side === side);
  const official = mine.find(isOfficial);
  const px = (a as { predicted_xi?: Record<string, { players?: XiPlayer[] }> } | undefined)?.predicted_xi?.[side];
  let predicted: Lineup | undefined;
  if (px?.players?.length) {
    const list = [...px.players]
      .map((p) => ({ name: p.name, pos: POS_TR[p.position ?? ""] ?? (p.position ?? "").slice(0, 1), note: p.note }))
      .sort((x, y) => (POS_ORDER[x.pos] ?? 9) - (POS_ORDER[y.pos] ?? 9));
    predicted = { match_id: "", side, formation: null, start_xi: list.map((p) => ({ name: p.note ? `${p.name} (${p.note})` : p.name, pos: p.pos })), subs: [], coach: null, source: "meclis" };
  }
  const external = !predicted ? mine.find((x) => !isOfficial(x)) : undefined;
  if (!official && !predicted && !external) return <p className="muted small">Meclis tahmini 11 maçtan önce yayımlanır; resmî ilk 11 açıklandığında burada görünür.</p>;
  return (
    <>
      {official && <LineupView lu={official} label="Resmî ilk 11" kind="off" />}
      {predicted && <LineupView lu={predicted} label="Meclis tahmini 11" kind="pred" collapsed={!!official} />}
      {external && <LineupView lu={external} label="Tahmini ilk 11" kind="pred" collapsed={!!official} />}
    </>
  );
}

function LineupView({ lu, label, kind, collapsed = false }: { lu: Lineup; label: string; kind: "off" | "pred"; collapsed?: boolean }) {
  const body = (
    <>
      <ol className="lu-list">
        {lu.start_xi.map((p, i) => <li key={i}><span className="lu-no">{p.number ?? ""}</span>{p.name}<small>{p.pos ?? ""}</small></li>)}
      </ol>
      {!!lu.subs?.length && <p className="muted tiny">Yedekler: {lu.subs.map((p) => p.name).join(", ")}</p>}
    </>
  );
  const head = (
    <div className="lu-head">
      <span className={`lu-badge ${kind}`}>{label}</span>
      {lu.formation && <b>{lu.formation}</b>}
      {lu.coach && <span className="muted small">TD: {lu.coach}</span>}
    </div>
  );
  return collapsed ? (
    <details className="lineup"><summary>{head}</summary>{body}</details>
  ) : <div className="lineup">{head}{body}</div>;
}

function OddsCard({ m }: { m: Match }) {
  const o = m.odds ?? {};
  const keys = Object.keys(o);
  const g = (k: string, s: string) => (typeof o[k]?.[s] === "number" ? (o[k][s] as number) : null);
  const ou = keys.filter((k) => k.startsWith("OU_GOALS_")).sort();
  return (
    <Card title="Oranlar">
      {!keys.length ? <p className="muted small">Bu maç için piyasa oranı henüz yok.</p> : (
        <div className="odds">
          {o["1X2"] && (
            <div className="odds-row"><span className="odds-k">MS</span>
              <span className="o"><small>1</small>{num(g("1X2", "1"))}</span><span className="o"><small>X</small>{num(g("1X2", "X"))}</span><span className="o"><small>2</small>{num(g("1X2", "2"))}</span>
            </div>
          )}
          {ou.map((k) => (
            <div key={k} className="odds-row"><span className="odds-k">{fmtLine(Number(k.replace("OU_GOALS_", "")))} Gol</span>
              <span className="o"><small>Alt</small>{num(g(k, "ALT"))}</span><span className="o"><small>Üst</small>{num(g(k, "ÜST"))}</span>
            </div>
          ))}
          {o["BTTS"] && (
            <div className="odds-row"><span className="odds-k">KG</span>
              <span className="o"><small>Var</small>{num(g("BTTS", "VAR"))}</span><span className="o"><small>Yok</small>{num(g("BTTS", "YOK"))}</span>
            </div>
          )}
          <p className="muted tiny">Kaynak: {[...new Set(keys.map((k) => sourceLabel(String(o[k]?.src ?? ""))).filter(Boolean))].join(", ")}. Oranlar değişebilir.</p>
        </div>
      )}
    </Card>
  );
}

function WeatherCard({ m, a }: { m: Match; a?: AnalysisPayload }) {
  const w = useAsync(`w:${m.id}`, () => api.weatherFor(m.id), [m.id]);
  const d = w.data?.[0]?.data ?? a?.weather;
  if (w.loading) return null;
  if (!d) return null;
  return (
    <Card title="Hava durumu">
      <div className="weather">
        <b className="w-temp">{num(d.temperature_c, 0)}°</b>
        <div><strong>{d.summary}</strong><p className="muted small">Yağış %{d.precip_prob ?? "—"} · Rüzgâr {num(d.wind_kmh, 0)} km/sa · Nem %{d.humidity ?? "—"}</p></div>
      </div>
      <p className="muted tiny">{d.location} · Open-Meteo</p>
    </Card>
  );
}

function H2H({ m }: { m: Match }) {
  const h = useAsync(`h2h:${m.id}`, () => api.headToHead(m.home_team_id, m.away_team_id, m.kickoff_at), [m.id]);
  return (
    <Card title="Son karşılaşmalar">
      <Gate loading={h.loading} error={h.error} rows={2}>
        {h.data?.length ? (
          <ul className="h2h">{h.data.map((g) => (
            <li key={g.id}><span className="muted small">{dateShort(g.kickoff_at)}.{g.kickoff_at.slice(2, 4)}</span><Link to={matchPath(g.id)}>{g.home_name} <b>{g.home_goals}-{g.away_goals}</b> {g.away_name}</Link></li>
          ))}</ul>
        ) : <p className="muted small">Veri havuzunda son karşılaşma yok.</p>}
      </Gate>
    </Card>
  );
}

function NewsCard({ m }: { m: Match }) {
  const n = useAsync(`mn:${m.id}`, () => api.newsForMatch(m.id), [m.id]);
  if (n.loading || !n.data?.length) return null;
  return (
    <Card title="Maçın gündemi">
      <ul className="news-mini">
        {n.data.map((x) => (
          <li key={x.id}><a href={x.link} target="_blank" rel="noopener noreferrer">{x.title}</a><span className="muted small">{x.source} · {relTime(x.published_at)}</span></li>
        ))}
      </ul>
    </Card>
  );
}

