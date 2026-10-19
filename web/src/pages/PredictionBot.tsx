import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { addDays, dateLong, trDay } from "../lib/format";
import { TAG_HINT } from "../lib/labels";
import { usePageMeta, ROUTES } from "../lib/seo";
import { groupBy } from "../lib/trust";
import { Link } from "react-router-dom";
import { PickCard } from "../components/PickCard";
import { CouponCard } from "../components/CouponCard";
import { Card, Disclaimer, Empty, Gate, PageHead, TagPill } from "../components/ui";
import type { Prediction } from "../lib/types";

export default function PredictionBot() {
  const meta = ROUTES[2];
  usePageMeta(meta.title, meta.description);
  const today = trDay();
  const d = useAsync("bot:data", async () => {
    const [preds, coupons] = await Promise.all([api.upcomingPredictions(), api.allCoupons()]);
    return { preds, coupons };
  });

  const preds = d.data?.preds ?? [];
  const byDay = groupBy(preds, (p) => trDay(p.kickoff_at)).sort((a, b) => a[0].localeCompare(b[0]));
  const focusDay = byDay.find(([k]) => k === today)?.[0] ?? byDay.find(([k]) => k > today)?.[0] ?? null;
  const dayPreds: Prediction[] = focusDay ? byDay.find(([k]) => k === focusDay)![1] : [];
  const later = byDay.filter(([k]) => focusDay && k > focusDay);
  const yesterday = byDay.find(([k]) => k === addDays(today, -1))?.[1] ?? [];
  const coupons = (d.data?.coupons ?? []).filter((c) => c.coupon_date === focusDay);
  const singles = dayPreds.filter((p) => p.tag === "meclis_gorusu");

  return (
    <>
      <PageHead kicker={dateLong(new Date().toISOString())} title="Tahmin Botu">
        Bot bülteni tarar, her pazarı modeller, senaryo kurar ve kararını maçtan <b>önce</b> deftere kilitler. Her maç analiz edilir; yalnızca değer taşıyan seçimler saatler önce yayımlanır.
      </PageHead>
      <Gate loading={d.loading} error={d.error} rows={5}>
        {!focusDay ? (
          <Empty title="Yeni kararlar yakında" icon="◆">Meclis her maçı analiz eder; değerli bir seçim bulduğunda maçtan saatler önce yayımlar ve kilitler. Geçmiş kararlar için <Link to="/tahmin-arsivi">Tahmin Arşivi</Link>.</Empty>
        ) : (
          <>
            <h2 className="day-title">{focusDay === today ? "Bugünün kararları" : `Sıradaki kararlar · ${dateLong(focusDay + "T12:00:00+03:00")}`}</h2>
            <div className="tag-legend">
              {(["gunun_karari", "meclis_gorusu", "karar_birligi"] as const).map((t) => <span key={t}><TagPill tag={t} /> <small className="muted">{TAG_HINT[t]}</small></span>)}
            </div>
            {coupons.length > 0 && (
              <div className="coupons">{coupons.map((c) => <CouponCard key={c.id} c={c} legs={dayPreds.filter((p) => p.coupon_id === c.id)} />)}</div>
            )}
            <h3 className="sub">Meclis Görüşleri <span className="muted">· {singles.length}</span></h3>
            {singles.length ? <div className="picks grid">{singles.map((p) => <PickCard key={p.id} p={p} />)}</div>
              : <p className="muted">Bu gün için tekli karar yok.</p>}
          </>
        )}

        {later.map(([k, ps]) => (
          <section key={k}>
            <h3 className="sub">{dateLong(k + "T12:00:00+03:00")}</h3>
            <div className="picks grid">{ps.filter((p) => p.tag === "meclis_gorusu" || !p.coupon_id).map((p) => <PickCard key={p.id} p={p} />)}</div>
          </section>
        ))}

        {yesterday.length > 0 && focusDay !== addDays(today, -1) && (
          <section>
            <h3 className="sub">Dünün kararları</h3>
            {(d.data?.coupons ?? []).filter((c) => c.coupon_date === addDays(today, -1)).map((c) => (
              <div className="coupons" key={c.id}><CouponCard c={c} legs={yesterday.filter((p) => p.coupon_id === c.id)} /></div>
            ))}
            <div className="picks grid">{yesterday.filter((p) => !p.coupon_id).map((p) => <PickCard key={p.id} p={p} compact />)}</div>
          </section>
        )}
      </Gate>

      <Card title="Bot nasıl karar verir?" className="how">
        <ol className="steps">
          <li><b>Bülten taraması.</b> Önümüzdeki maçlar çok kaynaklı veri havuzundan alınır; her maç analiz edilir.</li>
          <li><b>Veri.</b> Fikstür, son maçlar, maç maç istatistik, oranlar, eksik oyuncular, hakem ve Meclis tahmini 11 birlikte değerlendirilir. Her kararın yanında bir güven göstergesi yayımlanır.</li>
          <li><b>Modeller.</b> Gol için zaman ağırlıklı Dixon-Coles (Poisson) ve Meclis Elo; korner, kart ve isabetli şut için negatif binom/Poisson. Eksik oyuncular önemlerine göre ağırlıklandırılır.</li>
          <li><b>Seçim.</b> Maç başına tek <i>Meclis Görüşü</i>. <i>Günün Kararı</i>: 2–3 maç, toplam oran 2,30–4,00. <i>Karar Birliği</i>: günde 5+ görüş varsa en güvenilenlerden kombine.</li>
          <li><b>Kilit.</b> Kayıt maçtan önce yazılır; sonra değiştirilemez, silinemez. Sonuç otomatik işlenir.</li>
        </ol>
      </Card>
      <Disclaimer />
    </>
  );
}
