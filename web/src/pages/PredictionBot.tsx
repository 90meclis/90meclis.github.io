import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { addDays, dateLong, num, pct, relTime, signed, time, trDay, dayBoundsUtc } from "../lib/format";
import { league, pickLabel, sourceLabel } from "../lib/labels";
import { matchPath } from "../lib/match";
import { usePageMeta, ROUTES } from "../lib/seo";
import { valuePicks, type BotPick } from "../lib/bot";
import { Card, Chips, Disclaimer, Empty, Gate, PageHead, Stat, TagPill } from "../components/ui";
import type { Match, Prediction } from "../lib/types";

function reason(p: BotPick, top?: string): string {
  const bits = [`Model ${pct(p.probability)}`];
  if (p.odds) bits.push(`piyasa ${pct(1 / p.odds)} (oran ${num(p.odds)})`, `değer ${signed((p.edge ?? 0) * 100, 1)}%`);
  else bits.push(`adil oran ${num(p.fair_odds)}`, "piyasa oranı yok");
  if (top) bits.push(`akış: ${top.toLocaleLowerCase("tr-TR")}`);
  return bits.join(" · ");
}

export default function PredictionBot() {
  const meta = ROUTES[2];
  usePageMeta(meta.title, meta.description);
  const today = trDay();
  const [day, setDay] = useState(today);
  const [showPass, setShowPass] = useState(false);
  const d = useAsync(`bot:bulletin:${day}`, async () => {
    const [lo, hi] = dayBoundsUtc(day);
    const [b, preds] = await Promise.all([api.bulletin(day), api.predictionsBetween(lo, hi)]);
    return { ...b, preds };
  }, [day]);

  const rows = useMemo(() => {
    if (!d.data) return [];
    const pub = new Map<string, Prediction[]>();
    for (const p of d.data.preds) pub.set(p.match_id, [...(pub.get(p.match_id) ?? []), p]);
    return d.data.matches.map((m) => {
      const a = d.data!.analyses[m.id];
      const top = (a?.scenarios ?? []).filter((x) => x.olasılık !== null).sort((x, y) => (y.olasılık ?? 0) - (x.olasılık ?? 0))[0]?.ad;
      return { m, a, picks: valuePicks(a), pub: pub.get(m.id) ?? [], top };
    });
  }, [d.data]);
  const withValue = rows.filter((r) => r.picks.length || r.pub.length);
  const pass = rows.filter((r) => !r.picks.length && !r.pub.length);
  const analysed = rows.filter((r) => r.a).length;
  const nPicks = withValue.reduce((a, r) => a + r.picks.length, 0);
  const last = rows.map((r) => r.a?.created_at).filter(Boolean).sort().pop();
  const byLeague = groupLeague(withValue);
  const days = [0, 1, 2].map((i) => addDays(today, i));

  return (
    <>
      <PageHead kicker={`Bülten · ${dateLong(day + "T12:00:00+03:00")}`} title="Tahmin Botu">
        Botun ham çıktısı: bültendeki her maç taranır, her pazar modellenir; değer kuralını geçen <b>bütün</b> seçimler burada maç maç listelenir. Masanın seçtiği kararlar ise <Link to="/tahmin-arsivi">Tahmin Arşivi</Link>'nde.
      </PageHead>
      <Chips label="Bülten günü" value={day} onChange={setDay} options={days}
        render={(x) => x === today ? "Bugün" : x === days[1] ? "Yarın" : dateLong(x + "T12:00:00+03:00").split(" ").slice(0, 2).join(" ")} />
      <Gate loading={d.loading} error={d.error} rows={5}>
        <div className="kpis bot-kpis">
          <Stat label="Bültendeki maç" value={rows.length} />
          <Stat label="Analiz edilen" value={analysed} sub={last ? `son tarama ${relTime(last)}` : undefined} />
          <Stat label="Değer bulunan maç" value={withValue.length} />
          <Stat label="Değer seçimi" value={nPicks} sub="kuralı geçen tüm pazarlar" />
        </div>
        {!rows.length ? (
          <Empty title="Bu gün bültende maç yok" icon="◆" />
        ) : !withValue.length ? (
          <Empty title="Bot bu bültende henüz değer bulmadı" icon="◆">Maçlar her çalışmada (gece dahil) güncel veriyle yeniden hesaplanır. Analizler için <Link to="/mac-merkezi">Maç Merkezi</Link>.</Empty>
        ) : byLeague.map(([lg, list]) => (
          <section key={lg} className="bot-league">
            <h2 className="sub">{league(lg).flag} {league(lg).name} <span className="muted">· {list.length} maç</span></h2>
            <div className="bot-list">
              {list.map((r) => <BotMatch key={r.m.id} m={r.m} picks={r.picks} pub={r.pub} top={r.top} />)}
            </div>
          </section>
        ))}
        {pass.length > 0 && (
          <Card title={`Değer çıkmayan maçlar · ${pass.length}`} aside={<button className="btn ghost small" onClick={() => setShowPass(!showPass)}>{showPass ? "Gizle" : "Göster"}</button>}>
            {showPass ? (
              <ul className="bot-pass">{pass.map((r) => (
                <li key={r.m.id}><span className="muted small">{time(r.m.kickoff_at)}</span> <Link to={matchPath(r.m.id)}>{r.m.home_name} – {r.m.away_name}</Link> <span className="muted small">{league(r.m.league).name} · {r.a ? "pas: piyasa doğru fiyatlamış" : "analiz sırada"}</span></li>
              ))}</ul>
            ) : <p className="muted small">Bot bu maçları da analiz etti; değer kuralını geçen pazar çıkmadı. Pas da bir karardır.</p>}
          </Card>
        )}
      </Gate>

      <Card title="Bot nasıl karar verir?" className="how">
        <ol className="steps">
          <li><b>Bülten taraması.</b> Önümüzdeki maçlar çok kaynaklı veri havuzundan alınır; her maç analiz edilir.</li>
          <li><b>Veri.</b> Bu sezonun maçları, maç maç istatistik, oranlar, ağırlıklı eksikler, hakem, hava ve Meclis tahmini 11.</li>
          <li><b>Modeller.</b> Gol için zaman ağırlıklı Dixon-Coles (Poisson) ve Meclis Elo; korner, kart, isabetli şut ve kale vuruşu için negatif binom/Poisson.</li>
          <li><b>Değer kuralı.</b> Piyasa oranlı pazarda olasılık ≥ %40, değer ≥ %3, oran ≤ 3,20; oransız pazarda modelin olasılığı %72–86.</li>
          <li><b>Masa.</b> Bu listeden <i>Günün Kararı</i> (2–3 maç, 2,30–4,00), <i>Meclis Görüşü</i> (tekli) ve <i>Karar Birliği</i> (5+ görüş varsa) seçilir, maçtan saatler önce kilitlenir.</li>
        </ol>
      </Card>
      <Disclaimer />
    </>
  );
}

type Row = { m: Match; picks: BotPick[]; pub: Prediction[]; top?: string };
function groupLeague(rows: Row[]): [string, Row[]][] {
  const g = new Map<string, Row[]>();
  for (const r of rows) g.set(r.m.league, [...(g.get(r.m.league) ?? []), r]);
  return [...g.entries()].sort((a, b) => league(a[0]).order - league(b[0]).order)
    .map(([k, v]) => [k, v.sort((x, y) => x.m.kickoff_at.localeCompare(y.m.kickoff_at))] as [string, Row[]]);
}

function BotMatch({ m, picks, pub, top }: Row) {
  const pubKey = new Set(pub.map((p) => `${p.market}|${p.selection}|${p.line ?? ""}`));
  const extra = pub.filter((p) => !picks.some((x) => `${x.market}|${x.selection}|${x.line ?? ""}` === `${p.market}|${p.selection}|${p.line ?? ""}`));
  return (
    <article className="bot-match">
      <Link to={matchPath(m.id)} className="bot-head">
        <span className="bot-time">{time(m.kickoff_at)}</span>
        <strong>{m.home_name} – {m.away_name}</strong>
        <span className="muted small">{picks.length + extra.length} seçim →</span>
      </Link>
      <table className="tbl tight bot-picks">
        <thead><tr><th>Pazar</th><th>Oran</th><th>Model</th><th>Değer</th><th>Kısa gerekçe</th></tr></thead>
        <tbody>
          {picks.map((p, i) => {
            const k = `${p.market}|${p.selection}|${p.line ?? ""}`;
            const tag = pub.find((x) => `${x.market}|${x.selection}|${x.line ?? ""}` === k)?.tag;
            return (
              <tr key={i} className={pubKey.has(k) ? "on" : ""}>
                <td data-label="Pazar"><b>{pickLabel(p.market, p.selection, p.line, m.home_name, m.away_name)}</b>{tag && <> <TagPill tag={tag} /></>}</td>
                <td data-label="Oran">{p.odds ? <>{num(p.odds)} <small className="muted">{sourceLabel(p.odds_source ?? "")}</small></> : <>{num(p.fair_odds)}<sup>a</sup></>}</td>
                <td data-label="Model">{pct(p.probability)}</td>
                <td data-label="Değer" className={p.edge && p.edge > 0 ? "pos" : ""}>{p.edge != null ? `${signed(p.edge * 100, 1)}%` : "—"}</td>
                <td data-label="Gerekçe" className="muted small">{reason(p, top)}</td>
              </tr>
            );
          })}
          {extra.map((p) => (
            <tr key={p.id} className="on">
              <td data-label="Pazar"><b>{pickLabel(p.market, p.selection, p.line, m.home_name, m.away_name)}</b> <TagPill tag={p.tag} /></td>
              <td data-label="Oran">{p.odds ? num(p.odds) : <>{num(p.fair_odds)}<sup>a</sup></>}</td>
              <td data-label="Model">{pct(p.probability)}</td>
              <td data-label="Değer">{p.edge != null ? `${signed(p.edge * 100, 1)}%` : "—"}</td>
              <td data-label="Gerekçe" className="muted small">Kilitli kayıt · {p.scenario_note ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </article>
  );
}
