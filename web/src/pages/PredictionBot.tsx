// Ortak: Meclis'in yapay zekâ analisti. Arşivden farklı olarak bir "analist masası": günün radarı, Ortak'ın kendi
// cümleleriyle günü, en büyük farklar, piyasa nabzı, seri avı ve maç maç model ↔ piyasa. Boş görünen satır yok.
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { addDays, dateLong, num, pct, signed, time, trDay, dayBoundsUtc } from "../lib/format";
import { MARKET_GROUPS, TAG_LABELS, league, pickLabel } from "../lib/labels";
import { matchPath } from "../lib/match";
import { usePageMeta, ROUTES } from "../lib/seo";
import { scanMatch, EDGE_MIN, type ScanRow } from "../lib/scan";
import { huntFinds, type Find } from "../lib/hunt";
import { ScanTable } from "../components/ScanTable";
import { Card, Chips, Empty, Gate } from "../components/ui";
import type { Match, Prediction } from "../lib/types";
import type { BotAnalysis, BotBultenRow } from "../lib/data";

type Verdict = { kind: "secim" | "deger" | "pas" | "bekliyor"; text: string };

/** Bir sonraki tarama: iş akışı her 2 saatte bir (UTC tek saatler :15) ve 08:00 TSİ'de çalışır. */
function nextScan(now = new Date()): string {
  const d = new Date(now);
  for (let i = 0; i < 26; i++) {
    const t = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), d.getUTCHours() + i, 15));
    const h = t.getUTCHours();
    if (t > now && ((h % 2 === 1 && h <= 21) || h === 5)) return time(new Date(t.getTime() + 25 * 60e3).toISOString());
  }
  return "";
}

function verdictOf(a: BotAnalysis | undefined, rows: ScanRow[], pub: Prediction[], saved: BotBultenRow[], ns: string): Verdict {
  if (pub.length) return { kind: "secim", text: `Kararımı verdim: ${[...new Set(pub.map((p) => TAG_LABELS[p.tag]))].join(" + ")}` };
  if (saved.some((x) => x.arsiv_durumu && x.arsiv_durumu !== "aday")) return { kind: "secim", text: "Masaya aldım" };
  if (!a) return { kind: "bekliyor", text: `Bu maçı henüz analiz etmedim; ${ns ? `yaklaşık ${ns} TSİ'deki taramada` : "bir sonraki taramada"} hazır olur.` };
  if (!a.ready) return { kind: "pas", text: "Geçiyorum: iki takımın bu sezonki maç verisi model kurmaya yetmiyor." };
  const mm = a.model_matches ?? {};
  if (!(a.basis ?? "").startsWith("model")) return { kind: "pas", text: "Geçiyorum: bu maçta kendi modelim yok (takımların lig geçmişi yetersiz); olasılıklar piyasadan, değer iddiam olamaz." };
  if (Math.min(mm.home ?? 0, mm.away ?? 0) < (a.min_team_matches ?? 4)) return { kind: "pas", text: `Geçiyorum: takımların bu sezon modelde ${mm.home ?? 0} ve ${mm.away ?? 0} maçı var, en az ${a.min_team_matches ?? 4} isterim.` };
  const val = rows.filter((r) => r.value);
  const wild = rows.filter((r) => r.wild && r.odds);
  const chk = rows.filter((r) => r.check && r.odds);
  if (!val.length && chk.length && chk.length === wild.length) return { kind: "pas", text: `Geçiyorum: ${chk.length} pazarda hesaplanan değer %25'in üstünde. Bu kadarı gerçek olmaz; oran ya da maç eşleşmesi kontrol ediliyor.` };
  if (val.length) return { kind: "deger", text: `${val.length} pazarda piyasadan iyi fiyat görüyorum.${wild.length - chk.length > 0 ? ` ${wild.length - chk.length} pazarda modelim piyasadan aşırı ayrışıyor; onları oynamıyorum.` : ""}${chk.length ? ` ${chk.length} pazarda değer %25'in üstünde çıkıyor; oran ya da eşleşme kontrol edilene kadar saymıyorum.` : ""}` };
  if (wild.length) return { kind: "pas", text: `Geçiyorum: modelim bu maçta piyasadan aşırı ayrışıyor (${wild.length} pazar). Bu büyüklükte fark değer değil, büyük olasılıkla ölçüm hatası.` };
  const priced = rows.filter((r) => r.odds && r.pModel != null && !r.wild);
  if (!priced.length) return { kind: "pas", text: "Geçiyorum: hesapladığım pazarlarda piyasa oranı yok." };
  const best = priced.sort((x, y) => (y.edge ?? 0) - (x.edge ?? 0))[0];
  return { kind: "pas", text: `Geçiyorum: piyasa doğru fiyatlamış. En iyi fark ${signed((best.edge ?? 0) * 100, 1)}% (${pickLabel(best.market, best.selection, best.line)}), eşiğim +%${EDGE_MIN * 100}.` };
}

const RADAR_GROUPS = Object.keys(MARKET_GROUPS);
const SHORT: Record<string, string> = { "Skor / Sonuç": "MS", Gol: "Gol", Korner: "Krn", Kart: "Kart", "İsabetli Şut": "Şut", "Kale Vuruşu": "KV" };

/** Model ↔ piyasa 1X2 çubukları (yalnızca ikisi de varsa). */
function DualBar({ rows, m }: { rows: ScanRow[]; m: Match }) {
  const r = (s: string) => rows.find((x) => x.market === "1X2" && x.selection === s);
  const mod = ["1", "X", "2"].map((s) => r(s)?.pModel ?? null), mk = ["1", "X", "2"].map((s) => r(s)?.pMarket ?? null);
  const bar = (v: (number | null)[], cls: string, lab: string) => v.every((x) => x != null) ? (
    <div className={`db-row ${cls}`}><span className="db-k">{lab}</span>
      <div className="db-bar">{v.map((x, i) => <span key={i} className={`s${i}`} style={{ width: `${x! * 100}%` }}>{x! >= 0.12 ? pct(x) : ""}</span>)}</div></div>) : null;
  const a = bar(mod, "mod", "Ortak"), b = bar(mk, "mkt", "Piyasa");
  if (!a && !b) return null;
  return <div className="db" aria-label={`${m.home_name} / beraberlik / ${m.away_name}`}>{a}{b}<div className="db-legend"><span>{m.home_name}</span><span>X</span><span>{m.away_name}</span></div></div>;
}


export default function PredictionBot() {
  const meta = ROUTES[2];
  usePageMeta(meta.title, meta.description);
  const today = trDay();
  const [day, setDay] = useState(today);
  const [lg, setLg] = useState("");
  const [grp, setGrp] = useState("Tümü");
  const [onlyValue, setOnlyValue] = useState(false);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const ns = nextScan();
  const d = useAsync(`ortak:${day}`, async () => {
    const [lo, hi] = dayBoundsUtc(day);
    const [b, preds, saved] = await Promise.all([api.bulletin(day), api.predictionsBetween(lo, hi), api.botBulten(day)]);
    return { ...b, preds, saved: saved ?? [] };
  }, [day]);
  // İkinci aşama (ağır): seri avı için takım istatistikleri ve oran hareketleri; maç kartları beklemeden çizilir
  const d2 = useAsync(d.data ? `ortak2:${day}` : null, async () => {
    const ms = d.data!.matches, [lo] = dayBoundsUtc(day);
    const slugs = [...new Set(ms.flatMap((m) => [api.slugOf(m.home_team_id), api.slugOf(m.away_team_id)]))];
    const [stat, moves] = await Promise.all([api.statRowsForSlugs(slugs, api.seasonStartIso(new Date(lo)), lo), api.oddsMovesFor(ms.map((m) => m.id))]);
    return { stat, moves };
  }, [day, !!d.data]);

  const all = useMemo(() => {
    if (!d.data) return [];
    return d.data.matches.map((m) => {
      const a = d.data!.analyses[m.id];
      const own = (a?.basis ?? "").startsWith("model") && !!a?.ready && Math.min(a?.model_matches?.home ?? 0, a?.model_matches?.away ?? 0) >= (a?.min_team_matches ?? 4);
      const rows = scanMatch(m, a?.markets, own);
      const pub = d.data!.preds.filter((p) => p.match_id === m.id);
      const saved = d.data!.saved.filter((x) => x.match_id === m.id);
      return { m, a, own, rows, pub, v: verdictOf(a, rows, pub, saved, ns) };
    });
  }, [d.data, ns]);
  const scans = useMemo(() => new Map(all.map((x) => [x.m.id, x.rows])), [all]);
  const finds: Find[] = useMemo(() => d.data && d2.data?.stat ? huntFinds(d.data.matches, d2.data.stat, api.slugOf, scans) : [], [d.data, d2.data, scans]);
  const leagues = [...new Set(all.map((x) => x.m.league))].sort((a, b) => league(a).order - league(b).order);
  const list = all.filter(({ m, v }) => (!lg || m.league === lg) && (!onlyValue || v.kind === "deger" || v.kind === "secim") &&
    (!q || `${m.home_name} ${m.away_name}`.toLocaleLowerCase("tr-TR").includes(q.toLocaleLowerCase("tr-TR"))));
  const groups = grp === "Tümü" ? undefined : [grp];
  const own = all.filter((x) => x.own);
  const vals = own.flatMap((x) => x.rows.filter((r) => r.value).map((r) => ({ x, r }))).sort((a, b) => (b.r.edge ?? 0) - (a.r.edge ?? 0));
  const picks = all.filter((x) => x.v.kind === "secim");
  const wildM = own.filter((x) => x.rows.some((r) => r.wild));
  const pending = all.filter((x) => x.v.kind === "bekliyor").length;
  const fair = own.filter((x) => x.v.kind === "pas").length;
  const radar = own.map((x) => ({ x, cells: RADAR_GROUPS.map((g) => {
    const rs = x.rows.filter((r) => r.group === g && r.pModel != null && r.odds && !r.wild);
    if (!rs.length) return null;
    return Math.max(...rs.map((r) => r.edge ?? -1));
  }) })).filter((r) => r.cells.some((c) => c != null)).sort((a, b) => Math.max(...b.cells.map((c) => c ?? -1)) - Math.max(...a.cells.map((c) => c ?? -1))).slice(0, 14);
  const radarCols = RADAR_GROUPS.filter((_, i) => radar.some((r) => r.cells[i] != null));
  const moves = (d2.data?.moves ?? []).map((mv) => {
    const m = d.data!.matches.find((x) => x.id === mv.match_id);
    const o = mv.acilis?.["1X2"], c = mv.guncel?.["1X2"];
    if (!m || !o || !c) return null;
    const ch = (["1", "X", "2"] as const).map((s) => ({ s, a: Number(o[s]), b: Number(c[s]) })).filter((z) => z.a > 1 && z.b > 1).map((z) => ({ ...z, d: z.b / z.a - 1 }));
    const big = ch.sort((p, q2) => p.d - q2.d)[0];
    if (!big || big.d > -0.03) return null;
    const mod = scans.get(m.id)?.find((r) => r.market === "1X2" && r.selection === big.s);
    return { m, big, agree: mod?.pModel != null && mod.pMarket != null ? mod.pModel > mod.pMarket : null };
  }).filter((x): x is NonNullable<typeof x> => !!x).sort((a, b) => a.big.d - b.big.d).slice(0, 8);
  const days = [0, 1, 2].map((i) => addDays(today, i));
  const top = vals[0];
  const sent: string[] = d.data ? [
    `${dateLong(day + "T12:00:00+03:00").split(" ").slice(0, 2).join(" ")} bülteninde ${all.length} maç var; ${own.length} tanesinde kendi modelimle karar verecek kadar veri topladım.`,
    vals.length && top ? `${vals.length} pazarda piyasadan daha iyi fiyat görüyorum. En güçlüsü ${top.x.m.home_name} – ${top.x.m.away_name} maçında ${pickLabel(top.r.market, top.r.selection, top.r.line, top.x.m.home_name, top.x.m.away_name)}: oran ${num(top.r.odds)}, değer ${signed((top.r.edge ?? 0) * 100, 1)}%.` : own.length ? "Bugün piyasa iyi fiyatlamış; zorlama bir karar vermiyorum." : "",
    picks.length ? `${picks.length} maçta kararımı masaya koydum.` : "",
    wildM.length ? `${wildM.length} maçta modelim piyasadan 20 puandan fazla ayrışıyor; bu kadar büyük fark çoğu zaman değer değil, ölçüm hatasıdır. O pazarlarda karar vermiyorum.` : "",
    fair ? `${fair} maçı geçtim: ya piyasa doğru fiyatlamış ya da verim yetersiz. Nedenleri her maçın altında.` : "",
    finds.length ? `Seri avında ${finds.length} belirgin seri buldum; ${finds.filter((f) => f.row?.value).length} tanesinde değer de var.` : "",
    pending ? `${pending} maçın analizi sırada${ns ? `; yaklaşık ${ns} TSİ'de hazır` : ""}.` : "",
  ].filter(Boolean) : [];

  return (
    <div className="ortak">
      <header className="ortak-hero">
        <p className="kicker">Meclis'in yapay zekâ analisti</p>
        <h1>Ortak</h1>
        <p className="lead">Bütün maçları, bütün pazarları kendi modeliyle fiyatlar ve piyasayla karşılaştırır. Değer gördüğünü söyler, görmediği maçı nedeniyle geçer.</p>
      </header>
      <Chips label="Bülten günü" value={day} onChange={(x) => { setDay(x); setOpen({}); }} options={days}
        render={(x) => x === today ? "Bugün" : x === days[1] ? "Yarın" : dateLong(x + "T12:00:00+03:00").split(" ").slice(0, 2).join(" ")} />
      <Gate loading={d.loading} error={d.error} rows={6}>
        {!all.length ? <Empty title="Bu gün için bültende maç yok" icon="◆" /> : (
          <>
            <section className="ortak-day card">
              <div className="od-avatar" aria-hidden="true">◆</div>
              <div><h2>Ortak'ın günü</h2>{sent.map((s, i) => <p key={i}>{s}</p>)}</div>
            </section>

            {radar.length > 0 && (
              <Card title="Günün radarı" aside={<span className="muted small">maç × pazar · en iyi değer</span>} className="radar-card">
                <div className="radar" style={{ gridTemplateColumns: `minmax(0, 1fr) repeat(${radarCols.length}, 38px)` }}>
                  <span />{radarCols.map((g) => <span key={g} className="rh">{SHORT[g] ?? g}</span>)}
                  {radar.map(({ x, cells }) => (
                    <Link key={x.m.id} to={matchPath(x.m.id)} className="rrow" style={{ display: "contents" }}>
                      <span className="rn"><small>{time(x.m.kickoff_at)}</small> {x.m.home_name} – {x.m.away_name}</span>
                      {RADAR_GROUPS.map((g, i) => radarCols.includes(g) && (
                        <span key={g} className={`rc ${cells[i] == null ? "na" : cells[i]! >= EDGE_MIN ? "hot" : cells[i]! >= 0 ? "warm" : "cold"}`}
                          style={cells[i] != null && cells[i]! >= EDGE_MIN ? { opacity: Math.min(1, 0.45 + cells[i]! * 6) } : undefined}
                          title={cells[i] == null ? "oran yok" : `en iyi değer ${signed(cells[i]! * 100, 1)}%`}>
                          {cells[i] != null && cells[i]! >= EDGE_MIN ? `+${Math.round(cells[i]! * 100)}` : ""}
                        </span>
                      ))}
                    </Link>
                  ))}
                </div>
                <p className="muted tiny">Yeşil: piyasaya karşı +%{EDGE_MIN * 100} ve üstü değer (sayı = yüzde). Gri: fiyat var, değer yok. Koyu: o pazarda oran yok.</p>
              </Card>
            )}

            {vals.length > 0 && (
              <Card title="En büyük farklar" aside={<span className="muted small">Ortak ↔ piyasa</span>}>
                <ul className="edges">
                  {vals.slice(0, 6).map(({ x, r }, i) => (
                    <li key={i}>
                      <Link to={matchPath(x.m.id)}><small>{league(x.m.league).flag} {time(x.m.kickoff_at)} · {x.m.home_name} – {x.m.away_name}</small>
                        <b>{pickLabel(r.market, r.selection, r.line, x.m.home_name, x.m.away_name)}</b></Link>
                      <div className="eb"><span className="eb-m" style={{ width: `${(r.pModel ?? 0) * 100}%` }} /><span className="eb-k" style={{ width: `${(r.pMarket ?? 1 / (r.odds ?? 1)) * 100}%` }} /></div>
                      <span className="ev"><b>{num(r.odds)}</b><em className="pos">{signed((r.edge ?? 0) * 100, 1)}%</em><small>Ortak {pct(r.pModel)} · piyasa {pct(r.pMarket ?? 1 / (r.odds ?? 1))}</small></span>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {moves.length > 0 && (
              <Card title="Piyasa nabzı" aside={<span className="muted small">açılıştan bu yana en çok düşen oranlar</span>}>
                <ul className="moves">
                  {moves.map((x) => (
                    <li key={x.m.id}><Link to={matchPath(x.m.id, "oran")}>{x.m.home_name} – {x.m.away_name}</Link>
                      <span>MS {x.big.s}: {num(x.big.a)} → <b>{num(x.big.b)}</b> <em className="neg">{signed(x.big.d * 100, 1)}%</em></span>
                      {x.agree !== null && <small className={x.agree ? "pos" : "muted"}>{x.agree ? "Ortak da bu tarafta" : "Ortak bu tarafta değil"}</small>}</li>
                  ))}
                </ul>
              </Card>
            )}

            {finds.length > 0 && (
              <Card title="Seri avı" aside={<span className="muted small">sahaya göre, bu sezon</span>}>
                <ul className="finds">
                  {finds.slice(0, 10).map((f, i) => (
                    <li key={i}>
                      <Link to={matchPath(f.m.id, "form")}><small>{time(f.m.kickoff_at)} · {f.m.home_name} – {f.m.away_name}</small><b>{f.team} {f.text}</b></Link>
                      <span className="fk">{f.k}/{f.n}</span>
                      <span className={`fv ${f.row?.value ? "pos" : ""}`}>{f.row?.value ? `seri var, değer de var: ${num(f.row.odds)} (${signed((f.row.edge ?? 0) * 100, 1)}%)`
                        : f.row?.odds ? `seri var, değer yok: oran ${num(f.row.odds)}${f.row.pModel != null ? `, Ortak %${Math.round(f.row.pModel * 100)}` : ""}` : "seri var, piyasada oran yok"}</span>
                    </li>
                  ))}
                </ul>
                <p className="muted tiny">Seri geçmişi anlatır, geleceği garanti etmez. Ortak seriyi değil fiyatı oynar: seri güçlü ama oran düşükse "değer yok" der.</p>
              </Card>
            )}

            <h2 className="sec-title">Maç maç</h2>
            <div className="filters wb-filters">
              <label><span>Lig</span><select value={lg} onChange={(e) => setLg(e.target.value)}><option value="">Bütün ligler ({all.length})</option>{leagues.map((x) => <option key={x} value={x}>{league(x).name} ({all.filter((y) => y.m.league === x).length})</option>)}</select></label>
              <label className="grow"><span>Takım</span><input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Takım ara" /></label>
              <label className="toggle"><input type="checkbox" checked={onlyValue} onChange={(e) => setOnlyValue(e.target.checked)} /> Yalnızca değer ve karar</label>
            </div>
            <div className="chips scroll" role="radiogroup" aria-label="Pazar">
              {["Tümü", ...RADAR_GROUPS].map((g) => <button key={g} type="button" role="radio" aria-checked={grp === g} className={`chip ${grp === g ? "on" : ""}`} onClick={() => setGrp(g)}>{g}</button>)}
            </div>
            {!list.length ? <Empty title="Bu filtrede maç yok" icon="◆" /> : (
              <div className="oc-list">
                {list.map(({ m, rows, pub, v, a }) => {
                  const isOpen = open[m.id] ?? false;
                  const g = (groups ? rows.filter((r) => groups.includes(r.group)) : rows).filter((r) => r.odds || r.pModel != null);
                  const best = g.filter((r) => r.value).sort((x, y) => (y.edge ?? 0) - (x.edge ?? 0)).slice(0, 2);
                  const picked = new Set(pub.map((p) => `${p.market}|${p.selection}|${p.line ?? ""}`));
                  return (
                    <article key={m.id} className={`oc v-${v.kind}`}>
                      <header>
                        <span className="oc-t">{time(m.kickoff_at)}<small>{league(m.league).flag} {league(m.league).name}</small></span>
                        <Link to={matchPath(m.id)} className="oc-m">{m.home_name} <i>–</i> {m.away_name}</Link>
                        {rows.some((r) => r.check && r.odds) && <span className="vk" title="Bazı pazarlarda değer %25'in üstünde: oran ya da eşleşme kontrol ediliyor">veri kontrol</span>}
                        <span className={`wb-v ${v.kind}`}>{v.kind === "secim" ? "KARAR" : v.kind === "deger" ? "DEĞER" : v.kind === "pas" ? "PAS" : "SIRADA"}</span>
                      </header>
                      <DualBar rows={rows} m={m} />
                      {pub.length > 0 && <p className="oc-pick">{pub.map((p) => <span key={p.id}>◆ {pickLabel(p.market, p.selection, p.line, m.home_name, m.away_name)} <b>{num(p.odds ?? p.fair_odds)}</b> · {TAG_LABELS[p.tag]}</span>)}</p>}
                      {!pub.length && best.length > 0 && <p className="oc-val">{best.map((r, i) => <span key={i}>▸ {pickLabel(r.market, r.selection, r.line, m.home_name, m.away_name)} <b>{num(r.odds)}</b> <em className="pos">{signed((r.edge ?? 0) * 100, 1)}%</em></span>)}</p>}
                      <p className="oc-say">{v.text}{a?.lambdas ? ` Gol beklentim ${num(a.lambdas.home)} – ${num(a.lambdas.away)}.` : ""}</p>
                      {g.length > 0 && <button type="button" className="oc-more" onClick={() => setOpen({ ...open, [m.id]: !isOpen })} aria-expanded={isOpen}>{isOpen ? "Pazarları gizle" : `Bütün pazarlar (${g.length})`}</button>}
                      {isOpen && <div className="wb-body"><ScanTable rows={g} home={m.home_name} away={m.away_name} groups={groups} picked={picked} /></div>}
                    </article>
                  );
                })}
              </div>
            )}
          </>
        )}
      </Gate>
    </div>
  );
}
