import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { dateShort } from "../lib/format";
import { league } from "../lib/labels";
import { hasScore } from "../lib/match";
import { usePageMeta, ROUTES } from "../lib/seo";
import { GameBars } from "../components/charts";
import { Card, Chips, Empty, Gate, PageHead } from "../components/ui";
import { TeamSeries } from "../components/TeamSeries";
import type { Match, MatchStat, Trend } from "../lib/types";

type Tab = "seri" | "takim" | "puan";

function threshold(cond: string | null): number | null {
  if (!cond) return null;
  const m = cond.match(/>\s*([\d.,]+)/);
  if (m) return Number(m[1].replace(",", "."));
  if (/var/i.test(cond)) return 0.5;
  return null;
}

const MARKET_ORDER = ["gol", "KG var/yok", "ilk yarı gol", "korner", "takım kornerı", "şut sayısı", "isabetli şut", "kart"];
const MARKET_NICE: Record<string, string> = { "gol": "Toplam gol", "KG var/yok": "Karşılıklı gol", "ilk yarı gol": "İlk yarı gol", korner: "Toplam korner", "takım kornerı": "Takım korneri", "şut sayısı": "Şut", "isabetli şut": "İsabetli şut", kart: "Kart" };

export default function Lab() {
  const meta = ROUTES[6];
  usePageMeta(meta.title, meta.description);
  const lgQ = useAsync("leagues", api.leaguesInDb);
  const leagues = useMemo(() => [...(lgQ.data ?? [])].sort((a, b) => league(a).order - league(b).order), [lgQ.data]);
  const [lgSel, setLg] = useState<string>("");
  const lg = lgSel || (leagues.includes("T1") ? "T1" : leagues[0]) || "";
  const [tab, setTab] = useState<Tab>("seri");

  return (
    <>
      <PageHead kicker="Ortalamanın arkasındaki gerçek" title="Veri Laboratuvarı">
        Takımların maç maç değerleri: ortalama yerine her maçın kendi rakamı. Seriler, takım grafikleri ve güncel puan durumu.
      </PageHead>
      <Gate loading={lgQ.loading} error={lgQ.error} rows={4}>
        <div className="toolbar">
          <Chips label="Lig" options={leagues} value={lg} onChange={setLg} render={(l) => <><span aria-hidden="true">{league(l).flag}</span> {league(l).name}</>} />
          <div className="seg" role="tablist" aria-label="Laboratuvar görünümü">
            {([["seri", "Seriler"], ["takim", "Takım serisi"], ["puan", "Puan durumu"]] as const).map(([k, l]) => (
              <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>
            ))}
          </div>
        </div>
        {lg && tab === "seri" && <Streaks lg={lg} />}
        {lg && tab === "takim" && <TeamTab lg={lg} />}
        {lg && tab === "puan" && <Table lg={lg} />}
      </Gate>
    </>
  );
}

function Streaks({ lg }: { lg: string }) {
  const q = useAsync(`trends:${lg}`, () => api.trends(lg), [lg]);
  const markets = useMemo(() => [...new Set((q.data ?? []).map((t) => t.market))].sort((a, b) => MARKET_ORDER.indexOf(a) - MARKET_ORDER.indexOf(b)), [q.data]);
  const [mk, setMk] = useState("");
  const market = mk && markets.includes(mk) ? mk : markets[0];
  const rows: Trend[] = (q.data ?? []).filter((t) => t.market === market).sort((a, b) => (b.hits_last10 ?? 0) - (a.hits_last10 ?? 0) || b.streak - a.streak);
  return (
    <Gate loading={q.loading} error={q.error} rows={6}>
      {!rows.length ? <Empty title="Bu lig için seri tablosu henüz hesaplanmadı" icon="▦" /> : (
        <>
          <Chips label="Pazar" options={markets} value={market} onChange={setMk} render={(m) => MARKET_NICE[m] ?? m} />
          <p className="muted small">Koşul: <b>{rows[0].condition}</b>. Çubuklar eskiden yeniye son 10 maç; yeşil = koşul tuttu.</p>
          <div className="trend-list">
            {rows.map((t) => {
              const vals = [...t.match_values].reverse();
              return (
                <div key={t.id} className="trend">
                  <div className="trend-head">
                    <b>{t.team_name}</b>
                    <span className={`streak ${t.streak > 0 ? "on" : "off"}`}>{t.streak > 0 ? `${t.streak} maçtır tutuyor` : `${-t.streak} maçtır tutmuyor`}</span>
                    <span className="hits"><b>{t.hits_last10 ?? "–"}</b>/10</span>
                  </div>
                  <GameBars values={vals.map((v) => v.değer)} threshold={threshold(t.condition)} labels={vals.map((v) => `${dateShort(v.tarih)} ${v.yer === "İ" ? "" : "@"}${v.rakip}`)} height={70} />
                </div>
              );
            })}
          </div>
        </>
      )}
    </Gate>
  );
}

const METRICS: { k: keyof MatchStat | "goals" | "cards"; label: string }[] = [
  { k: "goals", label: "Gol" }, { k: "shots", label: "Şut" }, { k: "shots_on_target", label: "İsabetli şut" },
  { k: "corners", label: "Korner" }, { k: "cards", label: "Kart" }, { k: "fouls", label: "Faul" }, { k: "xg", label: "xG" },
];

function TeamTab({ lg }: { lg: string }) {
  const sm = useAsync(`season:${lg}`, () => api.seasonMatches(lg), [lg]);
  const teams = useMemo(() => {
    const m = new Map<string, string>();
    for (const g of sm.data ?? []) { m.set(g.home_team_id, g.home_name); m.set(g.away_team_id, g.away_name); }
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1], "tr"));
  }, [sm.data]);
  const [teamSel, setTeam] = useState("");
  const team = teamSel && teams.some(([id]) => id === teamSel) ? teamSel : teams[0]?.[0];
  const [metric, setMetric] = useState<string>("shots_on_target");
  const h = useAsync(team ? `labteam:${team}` : null, async () => {
    const games = await api.teamHistory(team!, new Date().toISOString(), 15);
    return { games, stats: await api.statsFor(games.map((g) => g.id)) };
  }, [team]);
  const name = teams.find(([id]) => id === team)?.[1] ?? "";
  const series = useMemo(() => {
    if (!h.data || !team) return [];
    const idx = new Map(h.data.stats.map((s) => [`${s.match_id}:${s.side}`, s]));
    return [...h.data.games].reverse().map((g) => {
      const home = g.home_team_id === team;
      const s = idx.get(`${g.id}:${home ? "home" : "away"}`);
      let v: number | null;
      if (metric === "goals") v = home ? g.home_goals : g.away_goals;
      else if (metric === "cards") v = s && (s.yellow !== null || s.red !== null) ? (s.yellow ?? 0) + (s.red ?? 0) : null;
      else v = (s?.[metric as keyof MatchStat] as number | null | undefined) ?? null;
      return { v, label: `${dateShort(g.kickoff_at)} ${home ? "" : "@"}${home ? g.away_name : g.home_name}` };
    });
  }, [h.data, team, metric]);

  return (
    <Gate loading={sm.loading} error={sm.error} rows={4}>
      {!teams.length ? <Empty title="Bu lig için bu sezon maç yok" icon="▦" /> : (
        <Card>
          <div className="filters inline">
            <label><span>Takım</span><select value={team} onChange={(e) => setTeam(e.target.value)}>{teams.map(([id, n]) => <option key={id} value={id}>{n}</option>)}</select></label>
            <Chips label="Metrik" options={METRICS.map((m) => String(m.k))} value={metric} onChange={setMetric} render={(k) => METRICS.find((m) => m.k === k)?.label ?? k} />
          </div>
          <Gate loading={h.loading} error={h.error} rows={3}>
            {series.length > 0 && (
              <>
                <h3 className="sub">{name} · {METRICS.find((m) => m.k === metric)?.label} · maç maç</h3>
                <GameBars values={series.map((s) => s.v)} labels={series.map((s) => s.label)} height={160} />
                <div className="gb-labels">{series.map((s, i) => <span key={i}>{s.label}</span>)}</div>
              </>
            )}
            {h.data && team && <TeamSeries name={name} teamId={team} games={h.data.games} stats={h.data.stats} />}
          </Gate>
        </Card>
      )}
    </Gate>
  );
}

interface Row { id: string; name: string; o: number; g: number; b: number; m: number; ag: number; yg: number; p: number; form: string[] }

function Table({ lg }: { lg: string }) {
  const sm = useAsync(`season:${lg}`, () => api.seasonMatches(lg), [lg]);
  const rows = useMemo(() => {
    const t = new Map<string, Row>();
    const get = (id: string, name: string) => {
      if (!t.has(id)) t.set(id, { id, name, o: 0, g: 0, b: 0, m: 0, ag: 0, yg: 0, p: 0, form: [] });
      return t.get(id)!;
    };
    const done = (sm.data ?? []).filter((x: Match) => hasScore(x) && (x.durum === "bitti" || x.status === "bitti"));
    for (const x of [...done].reverse()) {
      const h = get(x.home_team_id, x.home_name), a = get(x.away_team_id, x.away_name);
      const hg = x.home_goals!, ag = x.away_goals!;
      h.o++; a.o++; h.ag += hg; h.yg += ag; a.ag += ag; a.yg += hg;
      if (hg > ag) { h.g++; a.m++; h.p += 3; h.form.push("G"); a.form.push("M"); }
      else if (hg < ag) { a.g++; h.m++; a.p += 3; a.form.push("G"); h.form.push("M"); }
      else { h.b++; a.b++; h.p++; a.p++; h.form.push("B"); a.form.push("B"); }
    }
    return [...t.values()].sort((x, y) => y.p - x.p || (y.ag - y.yg) - (x.ag - x.yg) || y.ag - x.ag || x.name.localeCompare(y.name, "tr"));
  }, [sm.data]);
  return (
    <Gate loading={sm.loading} error={sm.error} rows={8}>
      {!rows.length ? <Empty title="Bu sezon için bitmiş maç yok" icon="▦" /> : (
        <Card title={`${league(lg).name} puan durumu`} aside={<span className="muted small">Veri havuzundaki sonuçlardan hesaplanır</span>}>
          <div className="table-wrap">
            <table className="tbl standings">
              <thead><tr><th>#</th><th>Takım</th><th>O</th><th>G</th><th>B</th><th>M</th><th>A</th><th>Y</th><th>Av</th><th>P</th><th className="hide-sm">Form</th></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={r.id}>
                    <td>{i + 1}</td><td><b>{r.name}</b></td><td>{r.o}</td><td>{r.g}</td><td>{r.b}</td><td>{r.m}</td><td>{r.ag}</td><td>{r.yg}</td>
                    <td>{r.ag - r.yg > 0 ? "+" : ""}{r.ag - r.yg}</td><td><b>{r.p}</b></td>
                    <td className="hide-sm"><span className="form-dots sm">{r.form.slice(-5).map((f, j) => <span key={j} className={`fd r-${f}`}>{f}</span>)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted tiny">Resmî puan durumu değildir; ertelenen maçlar ve puan silme cezaları yansımayabilir. <Link to="/mac-merkezi">Maç Merkezi</Link></p>
        </Card>
      )}
    </Gate>
  );
}
