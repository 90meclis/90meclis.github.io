import { useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { dateShort, num, pct, time, dayLabel, trDay } from "../lib/format";
import { fmtLine, league, registerLeagues } from "../lib/labels";
import { matchPath } from "../lib/match";
import { usePageMeta, ROUTES } from "../lib/seo";
import { Card, Disclaimer, Empty, Gate } from "../components/ui";
import { HBar, LineBars, Ring, Seg } from "../components/elite/viz";
import {
  STATS, YON_LABEL, SAHA_LABEL, KULVAR_LABEL, statDef, linesFor, defaultLine, filterRows, series, avg, hits, streak,
  leagueRows, bulletinRows, inde, scanFor, allTeams, teamsOf, rowsOfTeam, leaderboard, hunt, streakMarket, streakText, standings, isEuroLeague,
  type StatDef, type Yon, type Saha, type Kulvar, type LabRow, type TeamInfo, type Streak, type ScanRow,
} from "../lib/lab";
import "../styles/elite.css";

type Gor = "takim" | "lider" | "seri" | "vs" | "puan";
const GOR: [Gor, string, string][] = [
  ["takim", "Takım", "Bir takımın bütün istatistikleri maç maç"],
  ["lider", "Liderler", "Ligde kim en çok yapıyor, kim en çok veriyor"],
  ["seri", "Seri Avcısı", "Bugünün maçlarında süren en güçlü seriler"],
  ["vs", "Karşılaştır", "İki takım yan yana"],
  ["puan", "Puan durumu", "Bu sezonki lig tablosu"],
];
const POPULAR = ["T1", "CL", "EL", "ECL", "E0", "SP1", "I1", "D1", "F1", "N1", "P1"];

interface Preset { q: string; icon: string; p: Record<string, string> }
const PRESETS: Preset[] = [
  { q: "Bugünün en güçlü serileri", icon: "🔥", p: { gor: "seri", kapsam: "bulten" } },
  { q: "En çok korner yaptıran deplasman takımları", icon: "⛳", p: { gor: "lider", stat: "korner", yon: "lehte", saha: "dis", sira: "cok" } },
  { q: "Evinde en çok gol yiyenler", icon: "🥅", p: { gor: "lider", stat: "gol", yon: "aleyhte", saha: "ic", sira: "cok" } },
  { q: "Maçları en çok kartlı geçenler", icon: "🟨", p: { gor: "lider", stat: "kart", yon: "toplam", saha: "tum", sira: "cok" } },
  { q: "Karşılıklı golün en çok olduğu takımlar", icon: "⚽", p: { gor: "lider", stat: "kg", yon: "toplam", saha: "tum", sira: "cok" } },
  { q: "İlk yarısı en gollü takımlar", icon: "⏱", p: { gor: "lider", stat: "iy", yon: "toplam", saha: "tum", sira: "cok", cizgi: "1.5" } },
  { q: "Rakibine en az isabetli şut verenler", icon: "🛡", p: { gor: "lider", stat: "isabet", yon: "aleyhte", saha: "tum", sira: "az" } },
  { q: "Avrupa'da en golcü takımlar", icon: "🇪🇺", p: { gor: "lider", stat: "gol", yon: "lehte", saha: "tum", kulvar: "avrupa", sira: "cok", lig: "CL" } },
];

const lbl = (r: LabRow) => `${dateShort(r.kickoff_at)} ${r.side === "home" ? "" : "@"}${r.opponent}${r.competition === "Avrupa" ? " 🇪🇺" : ""}`;
const n1 = (v: number | null) => (v === null ? "—" : num(v, Number.isInteger(v) ? 0 : 1));

export default function Lab() {
  const meta = ROUTES[6];
  usePageMeta(meta.title, meta.description);
  const [sp, setSp] = useSearchParams();
  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(patch)) { if (v === null || v === "") next.delete(k); else next.set(k, v); }
    setSp(next, { replace: false });
  };
  const lgQ = useAsync("lab:leagues", async () => {
    const [codes, names] = await Promise.all([api.leaguesInDb(), api.leagueNames().catch(() => [])]);
    registerLeagues(names);
    return codes;
  });
  const leagues = useMemo(() => [...(lgQ.data ?? [])].sort((a, b) => league(a).order - league(b).order), [lgQ.data]);
  const lg = sp.get("lig") || (leagues.includes("T1") ? "T1" : leagues[0]) || "";
  const gor = (sp.get("gor") as Gor) || "takim";
  const st = statDef(sp.get("stat") || "korner");
  const yonRaw = (sp.get("yon") as Yon) || "lehte";
  const yon: Yon = st.k === "kg" ? "toplam" : yonRaw;
  const saha = (sp.get("saha") as Saha) || "tum";
  const kulvar = (sp.get("kulvar") as Kulvar) || "tum";
  const lineP = Number(sp.get("cizgi"));
  const line = linesFor(st, yon).includes(lineP) ? lineP : defaultLine(st, yon);
  const ctl = { lg, st, yon, saha, kulvar, line, set, sp };

  return (
    <div className="elite lab">
      <header className="lab-hero">
        <p className="kicker">Kendi analizini yap · bu sezon · maç maç</p>
        <h1>Veri Laboratuvarı</h1>
        <p className="lab-lead">Ortalama yalan söyler; seri söylemez. Bir takım seç, her maçın kendi rakamını gör: yaptığı, rakibe verdiği, evinde, deplasmanda, Avrupa'da.</p>
        <TeamSearch onPick={(t) => set({ lig: t.league, gor: "takim", takim: t.id.slice(t.id.indexOf(":") + 1), rakip: null })} />
      </header>

      <section className="presets" aria-label="Hazır sorular">
        <p className="eyebrow">Tek dokunuşla sor</p>
        <div className="preset-grid">
          {PRESETS.map((p) => (
            <button key={p.q} type="button" className="preset" onClick={() => set({ cizgi: null, kulvar: null, ...p.p })}>
              <span aria-hidden="true">{p.icon}</span>{p.q}
            </button>
          ))}
        </div>
      </section>

      <Gate loading={lgQ.loading} error={lgQ.error} rows={4}>
        <div className="lab-bar">
          <div className="lg-pick">
            <div className="chips scroll" role="radiogroup" aria-label="Popüler ligler">
              {POPULAR.filter((c) => leagues.includes(c)).map((c) => (
                <button key={c} type="button" role="radio" aria-checked={c === lg} className={`chip ${c === lg ? "on" : ""}`} onClick={() => set({ lig: c, takim: null, rakip: null })}>
                  <span aria-hidden="true">{league(c).flag}</span> {league(c).name}
                </button>
              ))}
            </div>
            <label className="lg-select"><span className="sr-only">Bütün ligler</span>
              <select value={lg} onChange={(e) => set({ lig: e.target.value, takim: null, rakip: null })}>
                {leagues.map((c) => <option key={c} value={c}>{league(c).flag} {league(c).name}{league(c).country ? ` · ${league(c).country}` : ""}</option>)}
              </select>
            </label>
          </div>
          <nav className="lab-tabs" aria-label="Laboratuvar görünümü">
            {GOR.map(([k, l]) => <button key={k} type="button" className={gor === k ? "on" : ""} aria-pressed={gor === k} onClick={() => set({ gor: k })}>{l}</button>)}
          </nav>
          <p className="muted small tab-hint">{GOR.find((g) => g[0] === gor)?.[2]}</p>
        </div>
        {gor === "seri" ? <Hunter {...ctl} /> : lg ? <LeagueLab gor={gor} {...ctl} /> : null}
      </Gate>

      <Card title="Nasıl okunur?" className="how lab-how">
        <ul className="steps">
          <li><b>Yaptığı</b>: takımın kendi değeri (attığı gol, kullandığı korner…). <b>Rakibe verdiği</b>: rakibinin o maçta ona karşı yaptığı. <b>Maç toplamı</b>: ikisinin toplamı; bahis pazarlarındaki "toplam" budur.</li>
          <li><b>Çizgi</b>: yeşil çubuk çizginin üstünde kaldı, gri altında. "Son 10 maçın 8'inde 9,5 üst" = 10 maçın 8'inde toplam 10 ya da daha fazla.</li>
          <li><b>Seri ≠ değer.</b> Bir seri piyasa tarafından zaten fiyatlanmış olabilir. Seri Avcısı bu yüzden her seriyi Ortak'ın oran taramasıyla karşılaştırır: oran adil değerin altındaysa "seri var, değer yok" yazar.</li>
          <li>Yalnızca <b>bu sezonun</b> maçları. Avrupa kupa maçları ayrı işaretlenir (🇪🇺) ve "Avrupa / Lig" seçimiyle ayrıştırılır. Kaynakta olmayan değer "–" görünür, tahmin edilmez.</li>
        </ul>
      </Card>
      <Disclaimer />
    </div>
  );
}

interface Ctl { lg: string; st: StatDef; yon: Yon; saha: Saha; kulvar: Kulvar; line: number; set: (p: Record<string, string | null>) => void; sp: URLSearchParams }

function TeamSearch({ onPick }: { onPick: (t: { id: string; name: string; league: string }) => void }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const tq = useAsync(open || q ? "lab:teams" : null, allTeams);
  const norm = (s: string) => s.toLocaleLowerCase("tr-TR").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/ı/g, "i");
  const res = useMemo(() => {
    if (q.trim().length < 2) return [];
    const k = norm(q.trim());
    const seen = new Set<string>();
    return (tq.data ?? []).filter((t) => norm(t.name).includes(k)).sort((a, b) => league(a.league).order - league(b.league).order)
      .filter((t) => { const key = `${t.name}|${t.league}`; if (seen.has(key)) return false; seen.add(key); return true; }).slice(0, 8);
  }, [q, tq.data]);
  return (
    <div className="tsearch">
      <input type="search" inputMode="search" placeholder="Takım ara: Galatasaray, Arsenal, Dortmund…" value={q} aria-label="Takım ara"
        onFocus={() => setOpen(true)} onChange={(e) => setQ(e.target.value)} />
      {res.length > 0 && (
        <ul className="ts-res" role="listbox">
          {res.map((t) => (
            <li key={t.id}><button type="button" onClick={() => { onPick(t); setQ(""); }}>
              <b>{t.name}</b><span className="muted small">{league(t.league).flag} {league(t.league).name}</span>
            </button></li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Controls({ st, yon, saha, kulvar, line, set, showLine = true, showKulvar = true }: Ctl & { showLine?: boolean; showKulvar?: boolean }) {
  return (
    <div className="ctl">
      <div className="chips scroll" role="radiogroup" aria-label="İstatistik">
        {STATS.map((s) => <button key={s.k} type="button" role="radio" aria-checked={s.k === st.k} className={`chip ${s.k === st.k ? "on" : ""}`} onClick={() => set({ stat: s.k, cizgi: null })}>{s.short}</button>)}
      </div>
      <div className="ctl-row">
        {st.k !== "kg" && <Seg label="Yön" value={yon} onChange={(v) => set({ yon: v, cizgi: null })} options={(["lehte", "aleyhte", "toplam"] as Yon[]).map((k) => [k, YON_LABEL[k]])} />}
        <Seg label="Saha" value={saha} onChange={(v) => set({ saha: v })} options={(["tum", "ic", "dis"] as Saha[]).map((k) => [k, SAHA_LABEL[k]])} />
        {showKulvar && <Seg label="Kulvar" value={kulvar} onChange={(v) => set({ kulvar: v })} options={(["tum", "lig", "avrupa"] as Kulvar[]).map((k) => [k, KULVAR_LABEL[k]])} />}
      </div>
      {showLine && st.k !== "kg" && (
        <div className="ctl-row lines"><span className="muted small">Çizgi</span>
          {linesFor(st, yon).map((l) => <button key={l} type="button" className={`lchip ${l === line ? "on" : ""}`} onClick={() => set({ cizgi: String(l) })}>{fmtLine(l)}</button>)}
        </div>
      )}
    </div>
  );
}

function LeagueLab({ gor, ...c }: Ctl & { gor: Gor }) {
  const q = useAsync(`lab:rows:${c.lg}`, () => leagueRows(c.lg), [c.lg]);
  const rows = useMemo(() => q.data ?? [], [q.data]);
  const teams = useMemo(() => teamsOf(rows, c.lg), [rows, c.lg]);
  return (
    <Gate loading={q.loading} error={q.error} rows={6}>
      {!teams.length ? <Empty title={`${league(c.lg).name} için bu sezon istatistik yok`} icon="▦">Başka bir lig seç ya da takım ara.</Empty> : (
        <>
          {gor === "takim" && <TeamView rows={rows} teams={teams} {...c} />}
          {gor === "lider" && <Leaders rows={rows} teams={teams} {...c} />}
          {gor === "vs" && <Versus rows={rows} teams={teams} {...c} />}
          {gor === "puan" && <Standings rows={rows} {...c} />}
        </>
      )}
    </Gate>
  );
}

function TeamPicker({ teams, value, onChange, label }: { teams: TeamInfo[]; value: string; onChange: (s: string) => void; label: string }) {
  return (
    <label className="tpick"><span className="eyebrow">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>{teams.map((t) => <option key={t.slug} value={t.slug}>{t.name}</option>)}</select>
    </label>
  );
}

function hitSentence(v: number[], line: number, s: StatDef, over = true): ReactNode {
  if (!v.length) return <span className="muted">Veri yok</span>;
  const last = v.slice(-10), h = hits(last, line, over);
  if (s.k === "kg") return <>Son {last.length} maçın <b>{inde(h)}</b> karşılıklı gol var</>;
  return <>Son {last.length} maçın <b>{inde(h)}</b> {fmtLine(line)} {over ? "üst" : "alt"}</>;
}

function TeamView({ rows, teams, st, yon, saha, kulvar, line, set, sp, lg }: Ctl & { rows: LabRow[]; teams: TeamInfo[] }) {
  const slug = sp.get("takim") && teams.some((t) => t.slug === sp.get("takim")) ? sp.get("takim")! : teams[0].slug;
  const team = teams.find((t) => t.slug === slug)!;
  const tr = rowsOfTeam(rows, slug);
  const fr = filterRows(tr, saha, kulvar);
  const hasEuro = tr.some((r) => r.competition === "Avrupa");
  const sr = series(fr, st, yon);
  const lines = linesFor(st, yon);
  const results = [...tr].sort((a, b) => a.kickoff_at.localeCompare(b.kickoff_at)).slice(-6).map((r) => (r.goals_for > r.goals_against ? "G" : r.goals_for < r.goals_against ? "M" : "B"));
  return (
    <>
      <div className="team-head">
        <TeamPicker teams={teams} value={slug} onChange={(v) => set({ takim: v })} label={`${league(lg).name} · takım`} />
        <div className="th-meta">
          <span className="muted small">{tr.length} maç bu sezon{hasEuro ? ` · ${tr.filter((r) => r.competition === "Avrupa").length} Avrupa` : ""}</span>
          <span className="form-dots">{results.map((x, i) => <i key={i} className={`fd fd-${x}`}>{x}</i>)}</span>
        </div>
      </div>
      <div className="ctl-row">
        <Seg label="Saha" value={saha} onChange={(v) => set({ saha: v })} options={(["tum", "ic", "dis"] as Saha[]).map((k) => [k, SAHA_LABEL[k]])} />
        {hasEuro && <Seg label="Kulvar" value={kulvar} onChange={(v) => set({ kulvar: v })} options={(["tum", "lig", "avrupa"] as Kulvar[]).map((k) => [k, KULVAR_LABEL[k]])} />}
        {st.k !== "kg" && <Seg label="Yön" value={yon} onChange={(v) => set({ yon: v, cizgi: null })} options={(["lehte", "aleyhte", "toplam"] as Yon[]).map((k) => [k, YON_LABEL[k]])} />}
      </div>

      <div className="stat-grid">
        {STATS.map((s) => {
          const y: Yon = s.k === "kg" ? "toplam" : yon;
          const ss = series(fr, s, y);
          if (!ss.known.length) return null;
          const l = s.k === st.k ? line : defaultLine(s, y);
          const fo = series(fr, s, "lehte").known, ag = series(fr, s, "aleyhte").known;
          return (
            <button key={s.k} type="button" className={`scard ${s.k === st.k ? "on" : ""}`} onClick={() => set({ stat: s.k, cizgi: null })}>
              <span className="sc-top"><b>{s.label}</b>{s.k !== "kg" ? <span className="muted tiny">{n1(avg(fo))} yaptı · {n1(avg(ag))} verdi</span> : <span className="muted tiny">{pct(avg(ss.known))} maçta var</span>}</span>
              <LineBars values={ss.vals.slice(-10)} line={s.k === "kg" ? 0.5 : l} height={44} compact />
              <span className="sc-line small">{s.k === "kg" ? hitSentence(ss.known, 0.5, s) : hitSentence(ss.known, l, s)}</span>
            </button>
          );
        })}
      </div>

      <Card className="detail" title={<>{team.name} · {st.label}</>} aside={<span className="muted small">{st.k === "kg" ? "Maç maç" : `${YON_LABEL[yon]} · ${SAHA_LABEL[saha]}${kulvar !== "tum" ? " · " + KULVAR_LABEL[kulvar] : ""}`}</span>}>
        {!sr.known.length ? <p className="muted small">Bu seçimde maç yok ya da kaynak bu istatistiği vermiyor.</p> : (
          <>
            {st.k !== "kg" && (
              <div className="ctl-row lines"><span className="muted small">Çizgi</span>
                {lines.map((l) => <button key={l} type="button" className={`lchip ${l === line ? "on" : ""}`} onClick={() => set({ cizgi: String(l) })}>{fmtLine(l)}</button>)}
              </div>
            )}
            <div className="det-kpi">
              <Ring value={hits(sr.known, st.k === "kg" ? 0.5 : line) / sr.known.length} size={64} />
              <div>
                <p className="det-big">{st.k === "kg" ? <>Karşılıklı gol <b>{hits(sr.known, 0.5)}/{sr.known.length}</b> maçta</> : <><b>{hits(sr.known, line)}/{sr.known.length}</b> maçta {fmtLine(line)} üst</>}</p>
                <p className="muted small">Ortalama {n1(avg(sr.known))} · en düşük {n1(Math.min(...sr.known))} · en yüksek {n1(Math.max(...sr.known))}
                  {st.k !== "kg" && (() => { const up = streak(sr.known, line, true), dn = streak(sr.known, line, false); return up >= 2 ? <> · <b className="pos">{up} maçtır üst</b></> : dn >= 2 ? <> · <b className="neg">{dn} maçtır alt</b></> : null; })()}</p>
              </div>
            </div>
            <LineBars values={sr.vals} line={st.k === "kg" ? null : line} labels={sr.rows.map(lbl)} height={150} />
            <div className="lb-axis">{sr.rows.map((r, i) => <Link key={i} to={matchPath(r.match_id)} title={lbl(r)}>{r.opponent.slice(0, 3)}</Link>)}</div>
            {st.k !== "kg" && (
              <div className="line-table">
                {lines.map((l) => { const h = hits(sr.known, l); return (
                  <button type="button" key={l} className={l === line ? "on" : ""} onClick={() => set({ cizgi: String(l) })}>
                    <span>{fmtLine(l)} üst</span><HBar value={h / sr.known.length} /><b>{pct(h / sr.known.length)}</b><span className="muted tiny">{h}/{sr.known.length}</span>
                  </button>
                ); })}
              </div>
            )}
            <details className="mm-list">
              <summary>Maç maç liste ({sr.rows.length})</summary>
              <table className="tbl">
                <thead><tr><th>Tarih</th><th>Rakip</th><th>Skor</th><th>{st.k === "kg" ? "KG" : YON_LABEL[yon]}</th></tr></thead>
                <tbody>{[...sr.rows].reverse().map((r, i) => { const v = sr.vals[sr.rows.length - 1 - i]; return (
                  <tr key={r.match_id}><td>{dateShort(r.kickoff_at)}</td><td><Link to={matchPath(r.match_id)}>{r.side === "home" ? "" : "@ "}{r.opponent}</Link>{r.competition === "Avrupa" && <span className="eu" title="Avrupa kupası"> 🇪🇺</span>}</td>
                    <td>{r.goals_for}–{r.goals_against}</td><td><b className={v === null ? "muted" : st.k === "kg" ? (v ? "pos" : "") : v > line ? "pos" : ""}>{v === null ? "–" : st.k === "kg" ? (v ? "Var" : "Yok") : n1(v)}</b></td></tr>
                ); })}</tbody>
              </table>
            </details>
          </>
        )}
      </Card>
    </>
  );
}

function Leaders({ rows, teams, ...c }: Ctl & { rows: LabRow[]; teams: TeamInfo[] }) {
  const { st, yon, saha, kulvar, line, set, sp } = c;
  const [all, setAll] = useState(false);
  const sira = sp.get("sira") === "az" ? "az" : "cok";
  const by = sp.get("olcu") === "isabet" ? "isabet" : "ort";
  const list = useMemo(() => {
    const L = leaderboard(rows, teams, st, yon, saha, kulvar, st.k === "kg" ? 0.5 : line);
    const k = (x: typeof L[number]) => (by === "isabet" || st.k === "kg" ? x.hit : x.avg);
    return L.sort((a, b) => (sira === "cok" ? k(b) - k(a) : k(a) - k(b)) || b.n - a.n);
  }, [rows, teams, st, yon, saha, kulvar, line, sira, by]);
  const maxAvg = Math.max(1, ...list.map((x) => x.avg));
  const shown = all ? list : list.slice(0, 10);
  const title = `${sira === "cok" ? "En çok" : "En az"} ${st.k === "kg" ? "karşılıklı gol" : `${st.label.toLocaleLowerCase("tr-TR")} ${yon === "lehte" ? "yapan" : yon === "aleyhte" ? "veren" : "(maç toplamı)"}`}`;
  return (
    <>
      <Controls {...c} />
      <div className="ctl-row">
        <Seg label="Sıra" value={sira} onChange={(v) => set({ sira: v })} options={[["cok", "En çok"], ["az", "En az"]]} />
        {st.k !== "kg" && <Seg label="Ölçü" value={by} onChange={(v) => set({ olcu: v === "ort" ? null : v })} options={[["ort", "Ortalama"], ["isabet", `${fmtLine(line)} üst oranı`]]} />}
      </div>
      <Card title={title} aside={<span className="muted small">{SAHA_LABEL[saha]}{kulvar !== "tum" ? ` · ${KULVAR_LABEL[kulvar]}` : ""} · en az 3 maç</span>}>
        {!list.length ? <p className="muted small">Bu seçimde yeterli maç yok{kulvar === "avrupa" ? " (bu ligin takımlarının bu sezon Avrupa maçı olmayabilir)" : ""}.</p> : (
          <ol className="leaders">
            {shown.map((x, i) => (
              <li key={x.t.slug}>
                <span className={`rk ${i < 3 ? "top" : ""}`}>{i + 1}</span>
                <button type="button" className="ld-name" onClick={() => set({ gor: "takim", takim: x.t.slug })}><b>{x.t.name}</b><span className="muted tiny">{x.n} maç</span></button>
                <span className="ld-bars"><LineBars values={x.last} line={st.k === "kg" ? null : line} height={26} compact /></span>
                <span className="ld-v">
                  {st.k === "kg" ? <b>{pct(x.hit)}</b> : <b>{num(x.avg, 1)}</b>}
                  {st.k !== "kg" && <span className="muted tiny">{fmtLine(line)}+ {pct(x.hit)}</span>}
                  {st.k !== "kg" && <HBar value={x.avg} max={maxAvg} tone={yon === "aleyhte" ? "loss" : "lime"} />}
                </span>
              </li>
            ))}
          </ol>
        )}
        {list.length > 10 && <button type="button" className="btn ghost wide" onClick={() => setAll((a) => !a)}>{all ? "İlk 10" : `Bütün takımlar (${list.length})`}</button>}
      </Card>
    </>
  );
}

function Versus({ rows, teams, set, sp, kulvar }: Ctl & { rows: LabRow[]; teams: TeamInfo[] }) {
  const a = sp.get("takim") && teams.some((t) => t.slug === sp.get("takim")) ? sp.get("takim")! : teams[0].slug;
  const b = sp.get("rakip") && teams.some((t) => t.slug === sp.get("rakip")) ? sp.get("rakip")! : (teams.find((t) => t.slug !== a)?.slug ?? a);
  const venue = sp.get("senaryo") !== "tum";
  const A = teams.find((t) => t.slug === a)!, B = teams.find((t) => t.slug === b)!;
  const ra = filterRows(rowsOfTeam(rows, a), venue ? "ic" : "tum", kulvar), rb = filterRows(rowsOfTeam(rows, b), venue ? "dis" : "tum", kulvar);
  return (
    <>
      <div className="vs-head">
        <TeamPicker teams={teams} value={a} onChange={(v) => set({ takim: v })} label="Ev sahibi" />
        <span className="vs-x">vs</span>
        <TeamPicker teams={teams} value={b} onChange={(v) => set({ rakip: v })} label="Deplasman" />
      </div>
      <div className="ctl-row">
        <Seg label="Senaryo" value={venue ? "saha" : "tum"} onChange={(v) => set({ senaryo: v === "tum" ? "tum" : null })} options={[["saha", `${A.name} evinde · ${B.name} deplasmanda`], ["tum", "Bütün maçlar"]]} />
      </div>
      <Card title={`${A.name} – ${B.name}`} aside={<span className="muted small">{ra.length} + {rb.length} maç · bu sezon</span>}>
        <div className="vs-table">
          <div className="vs-row vs-h"><span>{A.name}</span><span /><span>{B.name}</span></div>
          {STATS.filter((s) => s.k !== "kg").map((s) => {
            const af = avg(series(ra, s, "lehte").known), aa = avg(series(ra, s, "aleyhte").known);
            const bf = avg(series(rb, s, "lehte").known), ba = avg(series(rb, s, "aleyhte").known);
            if (af === null || bf === null) return null;
            const expA = aa !== null && ba !== null ? (af + ba) / 2 : null, expB = aa !== null ? (bf + aa) / 2 : null;
            const mx = Math.max(af, bf, aa ?? 0, ba ?? 0, 0.1);
            return (
              <div className="vs-block" key={s.k}>
                <p className="vs-stat">{s.label}{expA !== null && expB !== null && <span className="muted tiny"> · basit beklenti: {num(expA, 1)} – {num(expB, 1)} (toplam {num(expA + expB, 1)})</span>}</p>
                <div className="vs-row"><span className="vs-l"><b>{num(af, 1)}</b><HBar value={af} max={mx} /></span><span className="vs-k">yaptığı</span><span className="vs-r"><HBar value={bf} max={mx} tone="mint" /><b>{num(bf, 1)}</b></span></div>
                {aa !== null && ba !== null && <div className="vs-row"><span className="vs-l"><b>{num(aa, 1)}</b><HBar value={aa} max={mx} tone="loss" /></span><span className="vs-k">verdiği</span><span className="vs-r"><HBar value={ba} max={mx} tone="loss" /><b>{num(ba, 1)}</b></span></div>}
              </div>
            );
          })}
          {(() => {
            const ka = avg(series(ra, statDef("kg"), "toplam").known), kb = avg(series(rb, statDef("kg"), "toplam").known);
            return ka !== null && kb !== null ? <div className="vs-block"><p className="vs-stat">Karşılıklı gol</p><div className="vs-row"><span className="vs-l"><b>{pct(ka)}</b><HBar value={ka} /></span><span className="vs-k">KG var</span><span className="vs-r"><HBar value={kb} tone="mint" /><b>{pct(kb)}</b></span></div></div> : null;
          })()}
        </div>
        <p className="muted tiny">Basit beklenti = (takımın yaptığı + rakibin verdiği) / 2. Bu bir model değildir; Meclis'in olasılıkları maç sayfasındadır.</p>
      </Card>
    </>
  );
}

function Standings({ rows, lg, set }: Ctl & { rows: LabRow[] }) {
  const euro = isEuroLeague(lg);
  const ev = useAsync(euro ? `lab:eutable:${lg}` : null, () => api.europeTableView(lg), [lg]);
  const own = useMemo(() => standings(rows, lg), [rows, lg]);
  if (euro) return (
    <Gate loading={ev.loading} error={ev.error} rows={6}>
      {!ev.data?.length ? <Empty title="Lig aşaması tablosu henüz yok" icon="▦" /> : (
        <Card title={`${league(lg).name} · lig aşaması`}>
          <div className="table-wrap"><table className="tbl standings">
            <thead><tr><th>#</th><th>Takım</th><th>O</th><th>G</th><th>B</th><th>M</th><th>Av</th><th>P</th></tr></thead>
            <tbody>{ev.data.map((r) => <tr key={r.team_name} className={r.sira <= 8 ? "z-top" : r.sira <= 24 ? "z-mid" : "z-out"}><td>{r.sira}</td><td><b>{r.team_name}</b></td><td>{r.o}</td><td>{r.g}</td><td>{r.b}</td><td>{r.m}</td><td>{r.av > 0 ? "+" : ""}{r.av}</td><td><b>{r.puan}</b></td></tr>)}</tbody>
          </table></div>
          <p className="muted tiny">İlk 8 doğrudan son 16 · 9–24 play-off · 25+ elenir.</p>
        </Card>
      )}
    </Gate>
  );
  return !own.length ? <Empty title="Bu sezon için bitmiş lig maçı yok" icon="▦" /> : (
    <Card title={`${league(lg).name} puan durumu`} aside={<span className="muted small">Bu sezonki bitmiş maçlardan</span>}>
      <div className="table-wrap"><table className="tbl standings">
        <thead><tr><th>#</th><th>Takım</th><th>O</th><th>G</th><th>B</th><th>M</th><th>A</th><th>Y</th><th>Av</th><th>P</th><th className="hide-sm">Form</th></tr></thead>
        <tbody>{own.map((r, i) => (
          <tr key={r.t.slug}><td>{i + 1}</td><td><button type="button" className="linkish" onClick={() => set({ gor: "takim", takim: r.t.slug })}><b>{r.t.name}</b></button></td>
            <td>{r.o}</td><td>{r.g}</td><td>{r.b}</td><td>{r.m}</td><td>{r.ag}</td><td>{r.yg}</td><td>{r.ag - r.yg > 0 ? "+" : ""}{r.ag - r.yg}</td><td><b>{r.p}</b></td>
            <td className="hide-sm"><span className="form-dots">{r.form.slice(-5).map((x, k) => <i key={k} className={`fd fd-${x}`}>{x}</i>)}</span></td></tr>
        ))}</tbody>
      </table></div>
    </Card>
  );
}

// ------------------------------------------------------------------------------------------------
// Seri Avcısı
// ------------------------------------------------------------------------------------------------
function Hunter({ lg, sp, set }: Ctl) {
  const kapsam = sp.get("kapsam") === "lig" ? "lig" : "bulten";
  const filt = sp.get("hstat") ?? "";
  const bq = useAsync(kapsam === "bulten" ? `lab:bulletin:${trDay()}` : null, async () => {
    const b = await bulletinRows();
    return { ...b, scan: await scanFor(b.fixtures.map((f) => f.id)) };
  });
  const lq = useAsync(kapsam === "lig" && lg ? `lab:rows:${lg}` : null, () => leagueRows(lg), [lg]);
  const streaks: Streak[] = useMemo(() => {
    if (kapsam === "bulten") {
      if (!bq.data) return [];
      const slug = (id: string) => id.slice(id.indexOf(":") + 1);
      const names = new Map(bq.data.rows.map((r) => [r.team_slug, r]));
      const ts = bq.data.fixtures.flatMap((f) => (["home", "away"] as const).map((side) => {
        const s = slug(side === "home" ? f.home_team_id : f.away_team_id), r = names.get(s);
        return r ? { t: { slug: s, id: r.team_id, name: side === "home" ? f.home_name : f.away_name }, saha: (side === "home" ? "ic" : "dis") as Saha, fixture: f, side } : null;
      })).filter((x): x is NonNullable<typeof x> => x !== null);
      return hunt(bq.data.rows, ts, 4);
    }
    if (!lq.data) return [];
    return hunt(lq.data, teamsOf(lq.data, lg).map((t) => ({ t, saha: "tum" as Saha })), 4);
  }, [kapsam, bq.data, lq.data, lg]);
  const scan: ScanRow[] = bq.data?.scan ?? [];
  const list = streaks.filter((s) => !filt || s.s.k === filt).slice(0, 30);
  const loading = kapsam === "bulten" ? bq.loading : lq.loading, error = kapsam === "bulten" ? bq.error : lq.error;
  const valued = kapsam === "bulten" ? list.filter((s) => { const m = streakMarket(s, scan); return m && m.odds && (m.edge ?? 0) >= 0.03; }).length : 0;
  return (
    <>
      <div className="ctl">
        <Seg label="Kapsam" value={kapsam} onChange={(v) => set({ kapsam: v === "bulten" ? null : v })} options={[["bulten", "Bugün + yarın bülteni"], ["lig", `${league(lg).name} · bütün takımlar`]]} />
        <div className="chips scroll" role="radiogroup" aria-label="İstatistik süzgeci">
          <button type="button" className={`chip ${!filt ? "on" : ""}`} onClick={() => set({ hstat: null })}>Hepsi</button>
          {STATS.map((s) => <button key={s.k} type="button" className={`chip ${filt === s.k ? "on" : ""}`} onClick={() => set({ hstat: s.k })}>{s.short}</button>)}
        </div>
      </div>
      <Gate loading={loading} error={error} rows={6}>
        {!list.length ? <Empty title="Şu an kayda değer süren seri yok" icon="🔥">En az 4 maçtır süren ve ligde sıradan olmayan seriler burada çıkar.</Empty> : (
          <>
            <p className="muted small hunt-sum">{kapsam === "bulten"
              ? <>Bugün ve yarın oynanacak maçlarda <b>{streaks.length}</b> güçlü seri bulundu. Ev sahibi için iç saha, deplasman için deplasman maçları sayılır. {valued ? <><b className="pos">{valued}</b> tanesinde piyasa oranı da değer veriyor.</> : "Hiçbirinde piyasa oranı değer vermiyor: seriler fiyatlanmış."}</>
              : <>{league(lg).name}'de en az 4 maçtır süren seriler. Sıralama: seri uzunluğu × ligde ne kadar nadir olduğu.</>}</p>
            <div className="hunt-list">
              {list.map((s, i) => <HuntCard key={`${s.t.slug}-${s.s.k}-${i}`} s={s} m={kapsam === "bulten" ? streakMarket(s, scan) : null} bulletin={kapsam === "bulten"} onTeam={() => set({ gor: "takim", takim: s.t.slug, stat: s.s.k, yon: s.y, saha: s.saha, cizgi: String(s.line), lig: s.fixture ? (s.side === "home" ? s.fixture.home_team_id : s.fixture.away_team_id).split(":")[0] : lg })} />)}
            </div>
          </>
        )}
      </Gate>
    </>
  );
}

function HuntCard({ s, m, bulletin, onTeam }: { s: Streak; m: ScanRow | null; bulletin: boolean; onTeam: () => void }) {
  const f = s.fixture;
  let badge: ReactNode = null;
  if (bulletin) {
    if (m && m.odds && (m.edge ?? 0) >= 0.03) badge = <span className="vbadge v-yes">Değer var · oran {num(m.odds)} · +%{num((m.edge ?? 0) * 100, 1)}</span>;
    else if (m && m.odds) badge = <span className="vbadge v-no">Seri var, değer yok · oran {num(m.odds)}</span>;
    else if (m && m.p_model !== null) badge = <span className="vbadge v-na">Piyasa oranı yok · model %{Math.round((m.p_model ?? 0) * 100)}</span>;
  }
  const dl = f ? dayLabel(trDay(f.kickoff_at)).top : "";
  return (
    <article className="hunt">
      <div className="h-top">
        <span className="h-run"><b>{s.run}</b><small>maç</small></span>
        <div className="h-txt">
          <button type="button" className="linkish h-team" onClick={onTeam}>{s.t.name}</button>
          <p>{streakText(s)}</p>
          {f && <Link to={matchPath(f.id)} className="h-fx small">{league(f.league).flag} {f.home_name} – {f.away_name} · {dl} {time(f.kickoff_at)} →</Link>}
        </div>
      </div>
      <LineBars values={s.vals} line={s.s.k === "kg" ? null : s.line} over={s.over} height={34} compact />
      <div className="h-foot">
        <span className="muted tiny">Son {s.n10}: {s.hit10}/{s.n10} · genel taban oran %{Math.round(s.base * 100)}</span>
        {badge}
      </div>
    </article>
  );
}

