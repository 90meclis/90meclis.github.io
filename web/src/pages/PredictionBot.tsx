import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { addDays, dateLong, num, pct, signed, time, trDay, dayBoundsUtc } from "../lib/format";
import { MARKET_GROUPS, TAG_LABELS, league, pickLabel } from "../lib/labels";
import { matchPath } from "../lib/match";
import { usePageMeta, ROUTES } from "../lib/seo";
import { scanMatch, EDGE_MIN, type ScanRow } from "../lib/scan";
import { ScanTable } from "../components/ScanTable";
import { Chips, Disclaimer, Empty, Gate, PageHead } from "../components/ui";
import type { Prediction } from "../lib/types";
import type { BotAnalysis, BotBultenRow } from "../lib/data";

type Verdict = { kind: "secim" | "deger" | "pas" | "bekliyor"; text: string };

function verdictOf(a: BotAnalysis | undefined, rows: ScanRow[], pub: Prediction[], saved: BotBultenRow[]): Verdict {
  if (pub.length) return { kind: "secim", text: pub.map((p) => `${TAG_LABELS[p.tag]}`).filter((x, i, l) => l.indexOf(x) === i).join(" + ") };
  if (saved.some((x) => x.arsiv_durumu && x.arsiv_durumu !== "aday")) return { kind: "secim", text: "Masaya alındı" };
  if (!a) return { kind: "bekliyor", text: "Model analizi bu tarama turunda henüz yazılmadı" };
  if (!a.ready) return { kind: "pas", text: "Model kurulamadı: takımların bu sezonki maç verisi yetersiz" };
  const mm = a.model_matches ?? {};
  const modelBased = (a.basis ?? "").startsWith("model");
  if (!modelBased) return { kind: "pas", text: "Olasılıklar piyasa oranından türetildi; piyasaya karşı değer iddiası kurulamaz" };
  if (Math.min(mm.home ?? 0, mm.away ?? 0) < (a.min_team_matches ?? 4)) return { kind: "pas", text: `Modelde takım başına bu sezon az maç var (${mm.home ?? 0}/${mm.away ?? 0})` };
  const val = rows.filter((r) => r.value);
  if (val.length) return { kind: "deger", text: `${val.length} pazarda değer` };
  const best = rows.filter((r) => r.edge != null && r.pModel != null && r.odds).sort((x, y) => (y.edge ?? 0) - (x.edge ?? 0))[0];
  const priced = rows.filter((r) => r.odds && r.pModel != null).length;
  if (!priced) return { kind: "pas", text: "Modelin hesapladığı pazarlarda piyasa oranı yok" };
  return { kind: "pas", text: `Piyasa doğru fiyatlamış: en iyi fark ${best ? `${signed((best.edge ?? 0) * 100, 1)}%` : "—"} (eşik +%${EDGE_MIN * 100})` };
}

const WINDOWS = ["Tümü", "3 saat", "Akşam"] as const;

export default function PredictionBot() {
  const meta = ROUTES[2];
  usePageMeta(meta.title, meta.description);
  const today = trDay();
  const [day, setDay] = useState(today);
  const [lg, setLg] = useState("");
  const [grp, setGrp] = useState("Tümü");
  const [win, setWin] = useState<(typeof WINDOWS)[number]>("Tümü");
  const [onlyValue, setOnlyValue] = useState(false);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const d = useAsync(`bot:wb:${day}`, async () => {
    const [lo, hi] = dayBoundsUtc(day);
    const [b, preds, saved] = await Promise.all([api.bulletin(day), api.predictionsBetween(lo, hi), api.botBulten(day)]);
    return { ...b, preds, saved: saved ?? [] };
  }, [day]);

  const all = useMemo(() => {
    if (!d.data) return [];
    return d.data.matches.map((m) => {
      const a = d.data!.analyses[m.id];
      const rows = scanMatch(m, a?.markets, (a?.basis ?? "").startsWith("model") && !!a?.ready &&
        Math.min(a?.model_matches?.home ?? 0, a?.model_matches?.away ?? 0) >= (a?.min_team_matches ?? 4));
      const pub = d.data!.preds.filter((p) => p.match_id === m.id);
      const saved = d.data!.saved.filter((x) => x.match_id === m.id);
      return { m, a, rows, pub, v: verdictOf(a, rows, pub, saved) };
    });
  }, [d.data]);
  const leagues = [...new Set(all.map((x) => x.m.league))].sort((a, b) => league(a).order - league(b).order);
  const now = Date.now();
  const list = all.filter(({ m, v }) =>
    (!lg || m.league === lg) &&
    (win === "Tümü" || (win === "3 saat" ? new Date(m.kickoff_at).getTime() - now < 3 * 3600e3 && new Date(m.kickoff_at).getTime() > now - 2 * 3600e3 : Number(time(m.kickoff_at).slice(0, 2)) >= 18)) &&
    (!onlyValue || v.kind === "deger" || v.kind === "secim") &&
    (!q || `${m.home_name} ${m.away_name}`.toLocaleLowerCase("tr-TR").includes(q.toLocaleLowerCase("tr-TR"))));
  const groups = grp === "Tümü" ? undefined : [grp];
  const scanned = all.filter((x) => x.a).length;
  const nRows = all.reduce((s, x) => s + x.rows.filter((r) => r.pModel != null).length, 0);
  const nValue = all.reduce((s, x) => s + x.rows.filter((r) => r.value).length, 0);
  const nPick = all.filter((x) => x.v.kind === "secim").length;
  const last = Object.values(d.data?.analyses ?? {}).map((x) => x.created_at).sort().pop();
  const days = [0, 1, 2].map((i) => addDays(today, i));

  return (
    <div className="bot-wb">
      <PageHead kicker={`Bülten · ${dateLong(day + "T12:00:00+03:00")}`} title="Tahmin Botu">
        Botun çalışma masası: günün bütün maçları, her maçta bütün pazarlar. Model olasılığı ile piyasa fiyatı yan yana; değer nerede, bot neyi seçti, neyi neden geçti.
      </PageHead>
      <Chips label="Bülten günü" value={day} onChange={(x) => { setDay(x); setOpen({}); }} options={days}
        render={(x) => x === today ? "Bugün" : x === days[1] ? "Yarın" : dateLong(x + "T12:00:00+03:00").split(" ").slice(0, 2).join(" ")} />
      <Gate loading={d.loading} error={d.error} rows={6}>
        <div className="term" role="status">
          <span><b>{all.length}</b> maç tarandı</span>
          <span><b>{scanned}</b> model analizi</span>
          <span><b>{nRows}</b> pazar</span>
          <span className="pos"><b>{nValue}</b> değer bulundu</span>
          <span><b>{nPick}</b> maç masada</span>
          {last && <span className="muted">son tarama {time(last)} TSİ</span>}
        </div>
        <div className="filters wb-filters">
          <label><span>Lig</span><select value={lg} onChange={(e) => setLg(e.target.value)}><option value="">Bütün ligler ({all.length})</option>{leagues.map((x) => <option key={x} value={x}>{league(x).name} ({all.filter((y) => y.m.league === x).length})</option>)}</select></label>
          <label><span>Saat</span><select value={win} onChange={(e) => setWin(e.target.value as typeof win)}>{WINDOWS.map((w) => <option key={w}>{w}</option>)}</select></label>
          <label className="grow"><span>Takım</span><input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Takım ara" /></label>
          <label className="toggle"><input type="checkbox" checked={onlyValue} onChange={(e) => setOnlyValue(e.target.checked)} /> Yalnızca değer</label>
        </div>
        <div className="chips scroll" role="radiogroup" aria-label="Pazar">
          {["Tümü", ...Object.keys(MARKET_GROUPS)].map((g) => <button key={g} type="button" role="radio" aria-checked={grp === g} className={`chip ${grp === g ? "on" : ""}`} onClick={() => setGrp(g)}>{g}</button>)}
        </div>
        {!list.length ? <Empty title="Bu filtrede maç yok" icon="◆" /> : (
          <div className="wb-list">
            {list.map(({ m, rows, pub, v, a }) => {
              const isOpen = open[m.id] ?? false;
              const g = groups ? rows.filter((r) => groups.includes(r.group)) : rows;
              const top = g.filter((r) => r.value).sort((x, y) => (y.edge ?? 0) - (x.edge ?? 0)).slice(0, 3);
              const r1 = (s: string) => rows.find((r) => r.market === "1X2" && r.selection === s);
              const picked = new Set(pub.map((p) => `${p.market}|${p.selection}|${p.line ?? ""}`));
              return (
                <article key={m.id} className={`wb-match v-${v.kind}`}>
                  <button className="wb-head" onClick={() => setOpen({ ...open, [m.id]: !isOpen })} aria-expanded={isOpen}>
                    <span className="wb-time">{time(m.kickoff_at)}</span>
                    <span className="wb-teams"><small>{league(m.league).flag} {league(m.league).name}</small><b>{m.home_name} – {m.away_name}</b></span>
                    <span className="wb-1x2">{(["1", "X", "2"] as const).map((s) => { const r = r1(s); return <span key={s}><small>{s}</small>{r?.pModel != null ? pct(r.pModel) : "—"}<i>{r?.odds ? num(r.odds) : ""}</i></span>; })}</span>
                    <span className={`wb-v ${v.kind}`}>{v.kind === "secim" ? "SEÇİM" : v.kind === "deger" ? "DEĞER" : v.kind === "pas" ? "PAS" : "SIRADA"}</span>
                  </button>
                  <div className="wb-line">
                    {v.kind === "secim" ? pub.map((p) => <span key={p.id} className="wb-pick">▸ {pickLabel(p.market, p.selection, p.line, m.home_name, m.away_name)} <b>{num(p.odds ?? p.fair_odds)}</b> · {TAG_LABELS[p.tag]}</span>)
                      : top.length ? top.map((r, i) => <span key={i} className="wb-val">▸ {pickLabel(r.market, r.selection, r.line, m.home_name, m.away_name)} <b>{num(r.odds)}</b> <em className="pos">{signed((r.edge ?? 0) * 100, 1)}%</em></span>)
                      : <span className="muted">{v.text}</span>}
                    {a?.lambdas && <span className="muted">xG {num(a.lambdas.home)}–{num(a.lambdas.away)}</span>}
                    <Link to={matchPath(m.id)} className="wb-link">Maç dosyası →</Link>
                  </div>
                  {isOpen && <div className="wb-body"><ScanTable rows={g} home={m.home_name} away={m.away_name} groups={groups} picked={picked} />{v.kind !== "secim" && v.kind !== "deger" && <p className="muted small">Bot kararı: {v.text}.</p>}</div>}
                </article>
              );
            })}
          </div>
        )}
      </Gate>
      <Disclaimer />
    </div>
  );
}
