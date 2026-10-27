import { motor as motorRow, groupOf, GROUP_TR, type Motor } from "../lib/editorial";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { num, pct, signed } from "../lib/format";
import { MARKET_LABELS, TAG_LABELS, league } from "../lib/labels";
import { usePageMeta, ROUTES } from "../lib/seo";
import { calibration, clvStat, curves, groupBy, isoWeek, sampleLevel, summarize, toBets, verdictLine, wilson, type Bet, type Summary } from "../lib/trust";
import { CalibrationChart, EquityChart } from "../components/charts";
import { PickCard } from "../components/PickCard";
import { Card, Empty, Gate, PageHead, Stat, StatusPill } from "../components/ui";
import { Link } from "react-router-dom";
import type { Tag, Coupon, Prediction } from "../lib/types";
import { asBt, backtest, streaks, weekly, type Bt, type WeekPt } from "../lib/trust2";
import { Ring } from "../components/elite/viz";
import { dateShort } from "../lib/format";
import "../styles/elite.css";

function WeekChart({ w }: { w: WeekPt[] }) {
  const max = Math.max(1, ...w.map((x) => Math.abs(x.profit)));
  return (
    <div className="wk">
      {w.map((x) => (
        <div key={x.week} className="wk-col" title={`${x.week}: ${x.won}-${x.lost}, ${signed(x.profit)} birim`}>
          <div className="wk-pos">{x.profit > 0 && <span style={{ height: `${(x.profit / max) * 100}%` }} />}</div>
          <div className="wk-neg">{x.profit < 0 && <span style={{ height: `${(-x.profit / max) * 100}%` }} />}</div>
          <small>{x.week.split("-")[1]}</small>
          <small className="muted">{x.won}-{x.lost}</small>
        </div>
      ))}
    </div>
  );
}

const btMarket = (m: string) => {
  const x = m.match(/^(.*)_(\d+(?:\.\d+)?)$/);
  return x ? `${MARKET_LABELS[x[1]] ?? x[1]} ${x[2].replace(".", ",")}` : MARKET_LABELS[m] ?? m;
};

function Backtest({ rows }: { rows: Bt[] }) {
  return (
    <Card title="Model testi (backtest)" className="bt-card" aside={<span className="bt-tag">Backtest · kilitli kayıt değildir</span>}>
      <p className="muted small">Model bu sezonun oynanmış maçlarında, yalnızca maçtan önce bilinen veriyle yeniden çalıştırıldı ve piyasanın (yabancı kapanış oranları) olasılıklarıyla yarıştırıldı. Bu test kilitli canlı kayıttan <b>ayrıdır</b>; kâr/zarar toplamına girmez. Düşük Brier ve log-loss daha iyidir.</p>
      {rows.map((r) => {
        const better = r.brier_model !== null && r.brier_market !== null ? r.brier_model < r.brier_market : null;
        const cal = (r.kalibrasyon ?? []).filter((c) => c.n > 0).map((c) => {
          const w = wilson(Math.round(c.gercek * c.n), c.n)!;
          return { range: `%${c.kutu.split("-").map((x) => Math.round(Number(x) * 100)).join("–")}`, n: c.n, avg: c.model_ort, real: c.gercek, lo: w[0], hi: w[1] };
        });
        return (
          <div key={r.market + (r.segment ?? "")} className="bt-row">
            <h3>{btMarket(r.market)} <small className="muted">· {num(r.n, 0)} maç{r.leagues?.length ? ` · ${r.leagues.length} lig` : ""}</small></h3>
            <div className="bt-duel">
              <div className={better === true ? "win" : ""}><small>Model</small><b>{num(r.brier_model, 3)}</b><span>Brier · log-loss {num(r.ll_model, 3)}</span></div>
              <div className={better === false ? "win" : ""}><small>Piyasa</small><b>{num(r.brier_market, 3)}</b><span>Brier · log-loss {num(r.ll_market, 3)}</span></div>
            </div>
            <p className="bt-verdict">{better === null ? "Karşılaştırma için veri yetersiz." : better
              ? `Model bu pazarda piyasadan daha isabetli olasılık veriyor (Brier ${num(r.brier_model, 3)} / ${num(r.brier_market, 3)}).`
              : `Bu pazarda piyasa, modelden daha isabetli (Brier ${num(r.brier_market, 3)} / ${num(r.brier_model, 3)}). Meclis bu yüzden piyasayı taban alır ve yalnızca model piyasadan anlamlı biçimde ayrıldığında karar verir.`}
              {r.deger_secim_sayisi ? ` Değer kuralını geçen ${r.deger_secim_sayisi} seçimde isabet ${pct(r.deger_isabet, 1)}, ROI ${r.deger_roi !== null ? signed(r.deger_roi * 100, 1) + "%" : "—"}.` : ""}</p>
            {cal.length > 1 && <details className="mm-list"><summary>Kalibrasyon ({btMarket(r.market)})</summary><CalibrationChart bins={cal} /></details>}
          </div>
        );
      })}
      {rows[0]?.computed_at && <p className="muted tiny">Hesaplandı: {dateShort(rows[0].computed_at)} · model {rows[0].model_version ?? "—"}</p>}
    </Card>
  );
}

function calibGap(cal: { n: number; avg: number; real: number }[]) {
  const n = cal.reduce((a, c) => a + c.n, 0);
  return n ? { n, gap: cal.reduce((a, c) => a + c.n * Math.abs(c.real - c.avg), 0) / n } : null;
}

function Glance({ T, S, clv, cal, bt, settled }: { T: Summary; S: Summary; clv: ReturnType<typeof clvStat>; cal: ReturnType<typeof calibration>; bt: Bt[] | null; settled: number }) {
  const g0 = calibGap(cal);
  const g = g0 && g0.n >= 10 ? g0 : null;
  const w = wilson(T.won, T.won + T.lost);
  const liveTone = settled < 30 ? "gold" : (T.roi ?? 0) > 0 ? "lime" : "loss";
  return (
    <section className="glance" aria-label="Tahminler iyi mi?">
      <h2 className="glance-q">Tahminler iyi mi?</h2>
      <div className="glance-grid">
        <div className="gl">
          <Ring value={T.hit} size={58} tone={liveTone} />
          <div><small>Kilitli canlı kayıt</small><b>{T.won}–{T.lost}{T.voids ? ` (${T.voids} iade)` : ""}</b>
            <p>{settled < 30 ? `Henüz erken: ${settled} sonuç var. İsabet %95 aralığı ${w ? `${pct(w[0])}–${pct(w[1])}` : "—"}; bu genişlikte bir aralık hiçbir şey kanıtlamaz.` : `İsabet ${pct(T.hit, 1)} (%95: ${w ? `${pct(w[0])}–${pct(w[1])}` : "—"}), ROI ${T.roi !== null ? signed(T.roi * 100, 1) + "%" : "—"}.`}</p></div>
        </div>
        <div className="gl">
          <Ring value={clv ? clv.beat : null} size={58} tone={clv && clv.n >= 30 ? (clv.lo > 0 ? "lime" : clv.hi < 0 ? "loss" : "gold") : "gold"} label={clv ? `${clv.mean >= 0 ? "+" : "−"}${Math.abs(clv.mean * 100).toFixed(1)}` : "—"} />
          <div><small>Piyasaya karşı (CLV)</small><b>{clv ? `${clv.n} karar ölçüldü` : "Ölçüm bekliyor"}</b><p>{verdictLine(clv, settled)}</p></div>
        </div>
        <div className="gl">
          <Ring value={g ? 1 - g.gap * 2 : null} size={58} tone={g && g.n >= 30 ? (g.gap < 0.06 ? "lime" : "gold") : "gold"} label={g ? `±${Math.round(g.gap * 100)}` : "—"} />
          <div><small>Kalibrasyon</small><b>{g ? `${g.n} tekli` : "Ölçüm bekliyor"}</b>
            <p>{!g ? `Söylediğimiz olasılıklar ile gerçekleşenler en az 10 sonuçla karşılaştırılır${g0 ? ` (şu an ${g0.n})` : ""}.${bt?.length ? " Bu arada modelin geniş örneklemli testi backtest kutusunda." : ""}` : g.n < 30 ? `Söylenen ile gerçekleşen arasında ortalama ${Math.round(g.gap * 100)} puan fark var; ${g.n} sonuçla bu henüz gürültü.` : `Söylediğimiz olasılıklar gerçekleşenden ortalama ${Math.round(g.gap * 100)} puan sapıyor${g.gap < 0.06 ? ": iyi kalibre." : "."}`}</p></div>
        </div>
        {bt && bt.length > 0 && (() => {
          const top = [...bt].sort((x, y) => y.n - x.n)[0];
          const wins = bt.filter((r) => r.brier_model !== null && r.brier_market !== null && r.brier_model < r.brier_market).length;
          return (
            <div className="gl gl-bt">
              <Ring value={wins / bt.length} size={58} tone="mint" label={`${wins}/${bt.length}`} />
              <div><small>Model testi · backtest</small><b>{num(top.n, 0)} geçmiş maç</b>
                <p>{wins === bt.length ? "Test edilen bütün pazarlarda model piyasadan daha isabetli." : wins === 0 ? "Test edilen pazarlarda piyasa modelden daha isabetli; Meclis bu yüzden piyasayı taban alıp yalnızca belirgin farkta oynar." : `${bt.length} pazarın ${wins}'inde model piyasadan daha isabetli.`} Kilitli kayıt değildir.</p></div>
            </div>
          );
        })()}
      </div>
      {S.won + S.lost < 30 && <p className="muted tiny">Eşikler: 30 sonuçtan önce hiçbir ölçüt "anlamlı" sayılmaz, 100 piyasa oranlı bahisten önce ROI gri gösterilir.</p>}
    </section>
  );
}

const roiTxt = (s: Summary) => (s.roi !== null ? `${signed(s.roi * 100, 1)}%` : "—");

function Row({ k, s, cls }: { k: string; s: Summary; cls?: string }) {
  return (
    <tr className={cls}>
      <td>{k}</td><td>{s.total}{s.pending ? <small className="muted"> ({s.pending} bekliyor)</small> : null}</td>
      <td>{s.won} / {s.lost} / {s.voids}</td><td>{pct(s.hit, 1)}{(() => { const w = wilson(s.won, s.won + s.lost); return w && s.won + s.lost >= 5 ? <span className="ci-txt">%95: {pct(w[0])}–{pct(w[1])}</span> : null; })()}</td>
      <td className={(s.profit ?? 0) > 0 ? "pos" : (s.profit ?? 0) < 0 ? "neg" : ""}>{s.profit !== null ? signed(s.profit) : "—"}</td>
      <td className={s.priced < 100 ? "badge-grey" : ""} title={s.priced < 100 ? "100 piyasa oranlı bahisten önce ROI gürültüdür" : undefined}>{roiTxt(s)}</td><td>{s.priced}</td>
    </tr>
  );
}

function Head({ k }: { k: string }) {
  return <thead><tr><th>{k}</th><th>Bahis</th><th>K / K / İ</th><th>İsabet</th><th>Kâr (birim)</th><th>ROI</th><th>Piyasa oranlı</th></tr></thead>;
}

function Breakdown({ title, groups, keyLabel, note }: { title: string; groups: [string, Bet[]][]; keyLabel: string; note?: string }) {
  if (!groups.length) return null;
  return (
    <Card title={title} aside={note ? <span className="muted small">{note}</span> : undefined}>
      <div className="table-wrap">
        <table className="tbl"><Head k={keyLabel} />
          <tbody>{groups.map(([k, rows]) => <Row key={k} k={k} s={summarize(rows)} />)}</tbody>
        </table>
      </div>
    </Card>
  );
}

const LVL: Record<string, string> = { erken: "anlamlı değil", gelisen: "erken", okunur: "okunur" };
function Lvl({ n }: { n: number }) {
  const l = sampleLevel(n);
  return l === "yok" ? null : <span className={`lvl ${l}`} title={`${n} örnek`}>{LVL[l]}</span>;
}

/** Pazar/lig bazında CLV ve %95 aralık; kapanış oranı olmayan grup gösterilmez. */
function ClvBreakdown({ title, groups }: { title: string; groups: [string, Bet[]][] }) {
  const rows = groups.map(([k, v]) => [k, clvStat(v)] as const).filter((r) => r[1] !== null);
  if (!rows.length) return null;
  return (
    <Card title={title} aside={<span className="muted small">Kapanış oranına göre</span>}>
      <div className="table-wrap">
        <table className="tbl">
          <thead><tr><th>Grup</th><th>n</th><th>Ort. CLV</th><th>%95 aralık</th><th>Kapanışı yenen</th></tr></thead>
          <tbody>{rows.map(([k, c]) => (
            <tr key={k}><td>{k}<Lvl n={c!.n} /></td><td>{c!.n}</td>
              <td className={c!.mean > 0 ? "pos" : c!.mean < 0 ? "neg" : ""}>{signed(c!.mean * 100, 1)}%</td>
              <td>{c!.n > 1 ? `${signed(c!.lo * 100, 1)}% – ${signed(c!.hi * 100, 1)}%` : "—"}</td><td>{pct(c!.beat)}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </Card>
  );
}

function sampleNote(n: number) {
  if (n === 0) return "Henüz sonuçlanmış karar yok. Rakamlar ilk sonuçlarla birlikte oluşur.";
  if (n < 30) return `Örneklem küçük (${n} sonuçlanmış tekli). Bu aşamada isabet ve ROI rastlantıya çok açıktır; anlamlı bir değerlendirme için en az birkaç yüz karar gerekir.`;
  if (n < 200) return `${n} sonuçlanmış tekli: eğilim görünmeye başlar ama dalgalanma hâlâ yüksektir.`;
  return `${n} sonuçlanmış tekli.`;
}

type LiveAgg = { n: number; won: number; roi: number | null; priced: number };
function liveAgg(ps: Prediction[]): LiveAgg {
  const st = ps.filter((p) => p.status === "kazandi" || p.status === "kaybetti");
  const pr = st.filter((p) => p.odds);
  const prof = pr.reduce((a, p) => a + (p.status === "kazandi" ? (p.odds as number) - 1 : -1), 0);
  return { n: st.length, won: st.filter((p) => p.status === "kazandi").length, roi: pr.length ? prof / pr.length : null, priced: pr.length };
}
const pctOr = (x: number | null | undefined) => (x == null ? "—" : `%${Math.round(x * 100)}`);

/** Motorun örneklem dışı geri testi ile yayımlanan seçimlerin canlı sonuçları, aynı bant/pazar kırılımında. */
function MotorVsLive({ m, preds }: { m: Motor; preds: Prediction[] }) {
  const bands = m.geritest.bantlar.filter((b) => b.n >= 20);
  const inBand = (p: Prediction, lo: number, hi: number) => (p.probability ?? 0) >= lo && (p.probability ?? 0) < hi;
  const groups = m.geritest.pazarlar.filter((g) => g.n >= 20);
  const t = m.geritest.toplam;
  return (
    <Card title="Geri test ↔ canlı" aside={<span className="muted small">Bant ve pazar bazında · tekliler + kupon ayakları</span>}>
      <p className="muted small">Geri test: {num(m.geritest.mac, 0)} geçmiş maçta, karar anı oranlarıyla, örneklem dışı (bir yarıyla öğrenilip öbür yarıda ölçüldü). Toplam {num(t.n, 0)} seçim, isabet {pctOr(t.isabet)}, ROI {t.roi != null ? `${signed(t.roi * 100, 1)}%` : "—"}. Canlı sütun yalnızca kilitli kayıttan sayılır; örneklem küçükken farklar şansa bağlıdır.</p>
      <div className="table-wrap"><table className="tbl">
        <thead><tr><th>Olasılık bandı</th><th>Geri test isabet</th><th>n</th><th>Canlı isabet</th><th>n</th><th>Canlı ROI</th></tr></thead>
        <tbody>{bands.map((b) => { const L = liveAgg(preds.filter((p) => inBand(p, b.alt, b.ust >= 1 ? 1.01 : b.ust))); return (
          <tr key={b.bant}><td>{b.bant}</td><td>{pctOr(b.isabet)}</td><td>{b.n}</td><td>{L.n ? pctOr(L.won / L.n) : "—"}</td><td>{L.n}</td><td>{L.roi != null ? `${signed(L.roi * 100, 1)}%` : "—"}</td></tr>); })}</tbody>
      </table></div>
      <div className="table-wrap"><table className="tbl">
        <thead><tr><th>Pazar</th><th>Geri test isabet</th><th>n</th><th>Canlı isabet</th><th>n</th><th>Yayına açık</th></tr></thead>
        <tbody>{groups.map((g) => { const L = liveAgg(preds.filter((p) => groupOf(p.market, p.line) === g.pazar)); return (
          <tr key={g.pazar}><td>{GROUP_TR[g.pazar] ?? g.pazar}</td><td>{pctOr(g.isabet)}</td><td>{g.n}</td><td>{L.n ? pctOr(L.won / L.n) : "—"}</td><td>{L.n}</td><td>{m.derin_pazarlar.includes(g.pazar) ? "evet" : "hayır"}</td></tr>); })}</tbody>
      </table></div>
      <p className="muted tiny">Geri testte ROI negatif: piyasa marjı yüzünden yüksek isabet tek başına kâr demek değildir. Meclis isabeti öne alır; değer (edge) yalnızca bilgi amaçlı gösterilir. Yayına yalnızca geri test derinliği yeten pazarlar açılır.</p>
    </Card>
  );
}

export default function Trust() {
  const meta = ROUTES[4];
  usePageMeta(meta.title, meta.description);
  const d = useAsync("trust", async () => {
    const [preds, coupons] = await Promise.all([api.allPredictions(), api.allCoupons()]);
    return { preds, coupons };
  });
  const preds = d.data?.preds ?? [];
  const bets = toBets(preds, d.data?.coupons ?? []);
  const singles = bets.filter((b) => b.kind === "tekli");
  const cps = bets.filter((b) => b.kind === "kupon");
  const S = summarize(singles), C = summarize(cps), T = summarize(bets);
  const cv = curves(bets);
  const cal = calibration(singles);
  const clvAll = clvStat(singles);
  const lost = preds.filter((p) => p.status === "kaybetti" && p.tag === "meclis_gorusu");
  const lostC: Coupon[] = (d.data?.coupons ?? []).filter((c) => c.status === "kaybetti");
  const bt = useAsync("trust:backtest", backtest);
  const mq = useAsync("trust:motor", motorRow);
  const sk = streaks(bets);
  const wk = weekly(bets);

  return (
    <>
      <PageHead kicker="Herkese açık kayıt" title="Güven Panosu">
        Tahminler iyi mi? Cevabı burada, kayıplar dahil. İsabet, kâr/zarar, kapanış oranına karşı performans (CLV) ve kalibrasyon; hepsi kilitli kayıttan, 1 birim sabit stake ile.
        <span className="muted tiny" style={{ display: "block", marginTop: 6 }}>Kayıt 27 Ekim 2026'da başladı.</span>
      </PageHead>
      <Gate loading={d.loading} error={d.error} rows={5}>
        {bets.length === 0 ? <Empty title="Kayıt 27 Ekim 2026'da başladı" icon="◈">İlk kararlar sonuçlandığında isabet, kâr/zarar ve CLV burada görünecek.</Empty> : (
          <>
            <Glance T={T} S={S} clv={clvAll} cal={cal} bt={bt.data ? bt.data.map(asBt) : null} settled={T.won + T.lost} />
            <div className="kpis">
              <Stat label="Toplam kâr (birim)" value={T.profit !== null ? signed(T.profit) : "—"} tone={(T.profit ?? 0) > 0 ? "pos" : (T.profit ?? 0) < 0 ? "neg" : "muted"} sub="tekliler + kuponlar" />
              <Stat label="Toplam ROI" value={roiTxt(T)} sub={`${T.priced} piyasa oranlı bahis`} />
              <Stat label="Tekli isabet" value={pct(S.hit, 1)} sub={`${S.won} / ${S.won + S.lost} sonuçlanan`} />
              <Stat label="Tekli kâr" value={S.profit !== null ? signed(S.profit) : "—"} tone={(S.profit ?? 0) > 0 ? "pos" : (S.profit ?? 0) < 0 ? "neg" : "muted"} sub={`ROI ${roiTxt(S)}`} />
              <Stat label="Kupon kâr" value={C.profit !== null ? signed(C.profit) : "—"} tone={(C.profit ?? 0) > 0 ? "pos" : (C.profit ?? 0) < 0 ? "neg" : "muted"} sub={`${C.won} / ${C.won + C.lost} kupon tuttu`} />
              {S.won + S.lost >= 10 && <Stat label="Brier (tekli)" value={S.brier !== null ? num(S.brier, 3) : "—"} sub="düşük = iyi kalibrasyon" />}
              {sk.n >= 3 && <Stat label="Güncel seri" value={sk.current ? `${sk.current.len} ${sk.current.kind === "kazandi" ? "K" : "Y"}` : "—"} tone={sk.current?.kind === "kazandi" ? "pos" : "neg"} sub={`en uzun: ${sk.bestWin} kazanç · ${sk.bestLoss} kayıp`} />}
            </div>
            <p className="note">{sampleNote(S.won + S.lost)}</p>

            <Card title="Piyasayı yeniyor muyuz?" aside={<Lvl n={clvAll?.n ?? 0} />}>
              <p className="verdict-line">{verdictLine(clvAll, S.won + S.lost + C.won + C.lost)}</p>
              {clvAll && <p className="muted tiny">CLV: kayıt anındaki oranın kapanış oranına göre farkı. Uzun vadede kazancı en iyi öngören ölçüt; isabet ve ROI'den çok daha az şansa bağlıdır.</p>}
            </Card>

            {mq.data && <MotorVsLive m={mq.data} preds={preds} />}
            {bt.data && <Backtest rows={bt.data.map(asBt)} />}

            <Card title="Özet">
              <div className="table-wrap">
                <table className="tbl sum-table"><Head k="Grup" />
                  <tbody>
                    <Row k="Tekliler (Meclis Görüşü)" s={S} />
                    <Row k="Kuponlar (Günün Kararı + Karar Birliği)" s={C} />
                    <Row k="Toplam" s={T} cls="total" />
                  </tbody>
                </table>
              </div>
              {clvAll && <p className="muted small">Ortalama CLV (kapanış oranına göre): {signed(clvAll.mean * 100, 2)}%{clvAll.n > 1 ? ` · %95 aralık ${signed(clvAll.lo * 100, 1)}% – ${signed(clvAll.hi * 100, 1)}%` : ""} · {clvAll.n} tekli</p>}
            </Card>

            <Card title="Kasa eğrisi" aside={<span className="muted small">Yalnızca piyasa oranlı sonuçlanmış bahisler, 1 birim</span>}>
              {cv.toplam.length ? (
                <EquityChart series={[
                  { name: "Tekliler", points: cv.tekli, cls: "l-tekli" },
                  { name: "Kuponlar", points: cv.kupon, cls: "l-kupon" },
                  { name: "Toplam", points: cv.toplam, cls: "l-toplam" },
                ]} />
              ) : <p className="muted small">Henüz piyasa oranlı sonuçlanmış bahis yok. Piyasa oranı olmayan kararlar isabete dahil edilir ama kâr hesabına katılmaz.</p>}
            </Card>

            {wk.length >= 2 && <Card title="Haftalık gidiş" aside={<span className="muted small">Kâr (birim), piyasa oranlı · toplam {signed(wk[wk.length - 1].cum)}</span>}><WeekChart w={wk} /></Card>}

            <div className="grid-2">
              <Breakdown title="Lig bazında" keyLabel="Lig" note="Tekliler"
                groups={groupBy(singles, (b) => b.league ?? "—").sort((a, b) => league(a[0]).order - league(b[0]).order).map(([k, v]) => [league(k).name, v] as [string, Bet[]])} />
              <Breakdown title="Kupon türüne göre" keyLabel="Kupon" note="Kupon düzeyinde"
                groups={groupBy(cps, (b) => TAG_LABELS[b.market as Tag] ?? b.market)} />
            </div>
            <div className="grid-2">
              <Breakdown title="Haftalık" keyLabel="Hafta" note="Tekliler" groups={groupBy(singles, (b) => isoWeek(b.t)).sort((a, b) => b[0].localeCompare(a[0]))} />
              <Breakdown title="Pazar bazında" keyLabel="Pazar" note="Tekliler" groups={groupBy(singles, (b) => MARKET_LABELS[b.market] ?? b.market)} />
            </div>

            <div className="grid-2">
              <ClvBreakdown title="CLV · pazar bazında" groups={groupBy(singles, (b) => MARKET_LABELS[b.market] ?? b.market)} />
              <ClvBreakdown title="CLV · lig bazında" groups={groupBy(singles, (b) => league(b.league).name)} />
            </div>

            {cal.reduce((a, c) => a + c.n, 0) >= 20 && <Card title="Kalibrasyon" aside={<span className="muted small">Tekliler · söylenen olasılık ↔ gerçekleşen</span>}>
              <CalibrationChart bins={cal} />
              <div className="calib">
                {cal.map((c) => (
                  <div key={c.range} className="cal-row">
                    <span className="cal-k">{c.range}</span>
                    <div className="cal-bars"><span className="cal-exp" style={{ width: `${c.avg * 100}%` }} /><span className="cal-real" style={{ width: `${c.real * 100}%` }} /></div>
                    <span className="cal-v">{pct(c.real)} <small className="muted">/ {pct(c.avg)} · {c.n}</small><Lvl n={c.n} /></span>
                  </div>
                ))}
                <p className="muted tiny"><span className="lg exp" /> söylenen <span className="lg real" /> gerçekleşen</p>
              </div>
            </Card>}

            <Card title={`Her kayıp burada (${lost.length + lostC.length})`} aside={<span className="muted small">Silinmez, gizlenmez</span>}>
              {lostC.length > 0 && (
                <ul className="res-list">
                  {lostC.map((c) => <li key={c.id}><Link to="/tahmin-arsivi"><span><b>{TAG_LABELS[c.tag]} · {dateShort(c.first_kickoff_at)}</b><span className="muted tiny">{c.legs_count} maç · toplam oran {num(c.total_odds)} · {signed(c.profit)} birim</span></span><StatusPill status={c.status} /></Link></li>)}
                </ul>
              )}
              {lost.length ? <div className="picks grid">{lost.map((p) => <PickCard key={p.id} p={p} compact />)}</div> : !lostC.length ? <p className="muted small">Henüz kaybeden kayıt yok.</p> : null}
            </Card>

          </>
        )}
      </Gate>
      {/* veriler gelmeden çizilmez: aksi halde yükleme sonrası aşağı kayar (CLS) */}
      {d.data && <Card title="Ölçütler nasıl hesaplanıyor?" className="how">
        <ul className="steps">
          <li><b>Tekliler</b>: Meclis Görüşü kayıtları. <b>Kuponlar</b>: Günün Kararı ve Karar Birliği, kupon düzeyinde; kupon ayakları ayrı bahis sayılmaz. <b>Toplam</b> = tekliler + kuponlar.</li>
          <li><b>İsabet</b> = kazanan / (kazanan + kaybeden). İadeler hariç.</li>
          <li><b>Kâr ve ROI</b> yalnızca kayıt anında gerçek <i>piyasa oranı</i> olan bahislerde, 1 birim sabit stake ile. ROI = kâr / piyasa oranlı, iade olmayan sonuçlanmış bahis sayısı. Yalnızca modelin adil oranı olan kararlar isabete dahildir, kâr/zarara dahil değildir.</li>
          <li><b>Brier skoru</b> olasılıkların ne kadar iyi kalibre edildiğini ölçer (0 mükemmel, 0,25 yazı-tura).</li>
          <li><b>Değiştirilemezlik</b>: maç başladıktan sonra ekleme, düzenleme ve silme veritabanı tetikleyicileriyle engellenir.</li>
        </ul>
      </Card>}
    </>
  );
}
