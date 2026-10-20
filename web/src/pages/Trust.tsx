import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { num, pct, signed } from "../lib/format";
import { MARKET_LABELS, TAG_LABELS, league } from "../lib/labels";
import { usePageMeta, ROUTES } from "../lib/seo";
import { calibration, clvStat, curves, groupBy, isoWeek, sampleLevel, summarize, toBets, verdictLine, wilson, type Bet, type Summary } from "../lib/trust";
import { CalibrationChart, EquityChart } from "../components/charts";
import { PickCard } from "../components/PickCard";
import { Card, Disclaimer, Empty, Gate, PageHead, Stat } from "../components/ui";
import type { Tag } from "../lib/types";

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
  const lost = preds.filter((p) => p.status === "kaybetti").slice(0, 6);

  return (
    <>
      <PageHead kicker="Herkese açık kayıt" title="Güven Panosu">
        Arşivin dürüst yüzü: isabet, kâr/zarar, ROI ve kasa eğrisi. Kayıplar dahil hiçbir şey gizlenmez. Tekliler ve kuponlar ayrı, toplam ayrıca gösterilir; hepsi 1 birim sabit stake ile.
      </PageHead>
      <Gate loading={d.loading} error={d.error} rows={5}>
        {bets.length === 0 ? <Empty title="Henüz kayıt yok" icon="◈">İlk kararlar maçtan önce deftere düştüğünde burada görünecek.</Empty> : (
          <>
            <div className="kpis">
              <Stat label="Toplam kâr (birim)" value={T.profit !== null ? signed(T.profit) : "—"} tone={(T.profit ?? 0) > 0 ? "pos" : (T.profit ?? 0) < 0 ? "neg" : "muted"} sub="tekliler + kuponlar" />
              <Stat label="Toplam ROI" value={roiTxt(T)} sub={`${T.priced} piyasa oranlı bahis`} />
              <Stat label="Tekli isabet" value={pct(S.hit, 1)} sub={`${S.won} / ${S.won + S.lost} sonuçlanan`} />
              <Stat label="Tekli kâr" value={S.profit !== null ? signed(S.profit) : "—"} tone={(S.profit ?? 0) > 0 ? "pos" : (S.profit ?? 0) < 0 ? "neg" : "muted"} sub={`ROI ${roiTxt(S)}`} />
              <Stat label="Kupon kâr" value={C.profit !== null ? signed(C.profit) : "—"} tone={(C.profit ?? 0) > 0 ? "pos" : (C.profit ?? 0) < 0 ? "neg" : "muted"} sub={`${C.won} / ${C.won + C.lost} kupon tuttu`} />
              <Stat label="Brier (tekli)" value={S.brier !== null ? num(S.brier, 3) : "—"} sub="düşük = iyi kalibrasyon" />
            </div>
            <p className="note">{sampleNote(S.won + S.lost)}</p>

            <Card title="Piyasayı yeniyor muyuz?" aside={<Lvl n={clvAll?.n ?? 0} />}>
              <p className="verdict-line">{verdictLine(clvAll, S.won + S.lost + C.won + C.lost)}</p>
              {clvAll && <p className="muted tiny">CLV: kayıt anındaki oranın kapanış oranına göre farkı. Uzun vadede kazancı en iyi öngören ölçüt; isabet ve ROI'den çok daha az şansa bağlıdır.</p>}
            </Card>

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

            {cal.length > 0 && <Card title="Kalibrasyon" aside={<span className="muted small">Tekliler · söylenen olasılık ↔ gerçekleşen</span>}>
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

            <Card title="Son kayıplar" aside={<span className="muted small">Gizlenmez</span>}>
              {lost.length ? <div className="picks grid">{lost.map((p) => <PickCard key={p.id} p={p} compact />)}</div> : <p className="muted small">Henüz kaybeden kayıt yok.</p>}
            </Card>
          </>
        )}
      </Gate>
      <Card title="Ölçütler nasıl hesaplanıyor?" className="how">
        <ul className="steps">
          <li><b>Tekliler</b>: Meclis Görüşü kayıtları. <b>Kuponlar</b>: Günün Kararı ve Karar Birliği, kupon düzeyinde; kupon ayakları ayrı bahis sayılmaz. <b>Toplam</b> = tekliler + kuponlar.</li>
          <li><b>İsabet</b> = kazanan / (kazanan + kaybeden). İadeler hariç.</li>
          <li><b>Kâr ve ROI</b> yalnızca kayıt anında gerçek <i>piyasa oranı</i> olan bahislerde, 1 birim sabit stake ile. ROI = kâr / piyasa oranlı, iade olmayan sonuçlanmış bahis sayısı. Yalnızca modelin adil oranı olan kararlar isabete dahildir, kâr/zarara dahil değildir.</li>
          <li><b>Brier skoru</b> olasılıkların ne kadar iyi kalibre edildiğini ölçer (0 mükemmel, 0,25 yazı-tura).</li>
          <li><b>Değiştirilemezlik</b>: maç başladıktan sonra ekleme, düzenleme ve silme veritabanı tetikleyicileriyle engellenir.</li>
        </ul>
      </Card>
      <Disclaimer />
    </>
  );
}
