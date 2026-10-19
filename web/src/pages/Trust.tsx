import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { num, pct, signed } from "../lib/format";
import { MARKET_LABELS, TAG_LABELS } from "../lib/labels";
import { usePageMeta, ROUTES } from "../lib/seo";
import { calibration, couponSummary, equity, groupBy, isoWeek, summarize, type Summary } from "../lib/trust";
import { EquityChart } from "../components/charts";
import { PickCard } from "../components/PickCard";
import { Card, Disclaimer, Empty, Gate, PageHead, Stat } from "../components/ui";
import type { Prediction, Tag } from "../lib/types";

function Breakdown({ title, groups, keyLabel }: { title: string; groups: [string, Prediction[]][]; keyLabel: string }) {
  return (
    <Card title={title}>
      <div className="table-wrap">
        <table className="tbl">
          <thead><tr><th>{keyLabel}</th><th>Tahmin</th><th>K / K / İ</th><th>İsabet</th><th>Kâr</th><th>ROI</th></tr></thead>
          <tbody>
            {groups.map(([k, rows]) => {
              const s = summarize(rows);
              return (
                <tr key={k}>
                  <td>{k}</td><td>{s.total}{s.pending ? <small className="muted"> ({s.pending} bekliyor)</small> : null}</td>
                  <td>{s.won} / {s.lost} / {s.voids}</td><td>{pct(s.hit, 1)}</td>
                  <td className={s.profit > 0 ? "pos" : s.profit < 0 ? "neg" : ""}>{s.priced ? signed(s.profit) : "—"}</td>
                  <td>{s.roi !== null ? `${signed(s.roi * 100, 1)}%` : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function sampleNote(s: Summary) {
  const n = s.won + s.lost;
  if (n === 0) return "Henüz sonuçlanmış karar yok. Rakamlar ilk sonuçlarla birlikte oluşur.";
  if (n < 30) return `Örneklem küçük (${n} sonuç). Bu aşamada isabet ve ROI rastlantıya çok açıktır; anlamlı bir değerlendirme için en az birkaç yüz karar gerekir.`;
  if (n < 200) return `${n} sonuç: eğilim görünmeye başlar ama hâlâ dalgalanma yüksektir.`;
  return `${n} sonuçlanmış karar.`;
}

export default function Trust() {
  const meta = ROUTES[4];
  usePageMeta(meta.title, meta.description);
  const d = useAsync("trust", async () => {
    const [preds, coupons] = await Promise.all([api.allPredictions(), api.allCoupons()]);
    return { preds, coupons };
  });
  const preds = d.data?.preds ?? [];
  const coupons = d.data?.coupons ?? [];
  const singles = preds.filter((p) => p.tag === "meclis_gorusu");
  const s = summarize(singles);
  const curve = equity(singles, coupons);
  const cs = couponSummary(coupons);
  const cal = calibration(singles);
  const lost = preds.filter((p) => p.status === "kaybetti").slice(0, 6);

  return (
    <>
      <PageHead kicker="Herkese açık kayıt" title="Güven Panosu">
        Arşivin dürüst yüzü: isabet, kâr/zarar, ROI ve kasa eğrisi. Kayıplar dahil, hiçbir şey gizlenmez. Hesaplar 1 birim sabit stake ile yapılır.
      </PageHead>
      <Gate loading={d.loading} error={d.error} rows={5}>
        {preds.length === 0 ? <Empty title="Henüz kayıt yok" icon="◈">İlk kararlar maçtan önce deftere düştüğünde burada görünecek.</Empty> : (
          <>
            <div className="kpis">
              <Stat label="Meclis Görüşü" value={s.total} sub={`${s.pending} bekliyor`} />
              <Stat label="Kazanan / Kaybeden" value={`${s.won} / ${s.lost}`} sub={`${s.voids} iade`} />
              <Stat label="İsabet" value={pct(s.hit, 1)} sub="iadeler hariç" />
              <Stat label="Kâr (birim)" value={s.priced ? signed(s.profit) : "—"} tone={s.profit > 0 ? "pos" : s.profit < 0 ? "neg" : "muted"} sub={`${s.priced} piyasa oranlı`} />
              <Stat label="ROI" value={s.roi !== null ? `${signed(s.roi * 100, 1)}%` : "—"} sub="piyasa oranlı tekliler" />
              <Stat label="Brier" value={s.brier !== null ? num(s.brier, 3) : "—"} sub="düşük = iyi kalibrasyon" />
            </div>
            <p className="note">{sampleNote(s)}</p>

            <Card title="Kasa eğrisi" aside={<span className="muted small">Piyasa oranlı tekliler + kuponlar, 1 birim</span>}>
              {curve.length ? <EquityChart points={curve} /> : <p className="muted small">Henüz piyasa oranlı sonuçlanmış karar yok. Piyasa oranı olmayan kararlar isabete dahil edilir ama kâr hesabına katılmaz.</p>}
            </Card>

            <div className="grid-2">
              <Card title="Kuponlar">
                <div className="kpis small">
                  <Stat label="Kupon" value={cs.total} />
                  <Stat label="Kazanan / Kaybeden" value={`${cs.won} / ${cs.lost}`} />
                  <Stat label="Kâr (birim)" value={signed(cs.profit)} tone={cs.profit > 0 ? "pos" : cs.profit < 0 ? "neg" : "muted"} />
                </div>
              </Card>
              <Card title="Kalibrasyon" aside={<span className="muted small">Söylenen olasılık ↔ gerçekleşen</span>}>
                {cal.length ? (
                  <div className="calib">
                    {cal.map((c) => (
                      <div key={c.range} className="cal-row">
                        <span className="cal-k">{c.range}</span>
                        <div className="cal-bars"><span className="cal-exp" style={{ width: `${c.avg * 100}%` }} /><span className="cal-real" style={{ width: `${c.real * 100}%` }} /></div>
                        <span className="cal-v">{pct(c.real)} <small className="muted">/ {pct(c.avg)} · {c.n}</small></span>
                      </div>
                    ))}
                    <p className="muted tiny"><span className="lg exp" /> beklenen <span className="lg real" /> gerçekleşen</p>
                  </div>
                ) : <p className="muted small">Yeterli sonuç yok.</p>}
              </Card>
            </div>

            <div className="grid-2">
              <Breakdown title="Haftalık" keyLabel="Hafta" groups={groupBy(singles, (p) => isoWeek(p.kickoff_at)).sort((a, b) => b[0].localeCompare(a[0]))} />
              <Breakdown title="Pazar bazında" keyLabel="Pazar" groups={groupBy(singles, (p) => MARKET_LABELS[p.market] ?? p.market)} />
            </div>
            <Breakdown title="Etiket bazında (kupon ayakları dahil)" keyLabel="Etiket" groups={groupBy(preds, (p) => TAG_LABELS[p.tag as Tag] ?? p.tag)} />

            <Card title="Son kayıplar" aside={<span className="muted small">Gizlenmez</span>}>
              {lost.length ? <div className="picks grid">{lost.map((p) => <PickCard key={p.id} p={p} compact />)}</div> : <p className="muted small">Henüz kaybeden kayıt yok.</p>}
            </Card>
          </>
        )}
      </Gate>
      <Card title="Ölçütler nasıl hesaplanıyor?" className="how">
        <ul className="steps">
          <li><b>İsabet</b> = kazanan / (kazanan + kaybeden). İadeler hariç.</li>
          <li><b>Kâr ve ROI</b> yalnızca kayıt anında gerçek <i>piyasa oranı</i> olan kararlarda, 1 birim sabit stake ile hesaplanır. Yalnızca modelin adil oranı olan kararlar isabete dahildir, kâr/zarara dahil değildir; adil oranla kâr hesaplamak gerçeği yansıtmaz.</li>
          <li><b>Brier skoru</b> olasılıkların ne kadar iyi kalibre edildiğini ölçer (0 mükemmel, 0,25 yazı-tura).</li>
          <li><b>Değiştirilemezlik</b>: maç başladıktan sonra ekleme, düzenleme ve silme veritabanı tetikleyicileriyle engellenir.</li>
        </ul>
      </Card>
      <Disclaimer />
    </>
  );
}
