import { Link } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { summarize, toBets } from "../lib/trust";
import { pct, signed, trDay, addDays, relTime, num, time, dateLong } from "../lib/format";
import { league, pickLabel } from "../lib/labels";
import { matchPath } from "../lib/match";
import { dedupNews } from "../lib/news";
import { usePageMeta, ROUTES } from "../lib/seo";
import { MatchRow } from "../components/MatchRow";
import { Card, Disclaimer, Empty, Gate, Skeleton, Stat, StatusPill } from "../components/ui";
import { NAV } from "../lib/nav";
import type { Match } from "../lib/types";

const PILLARS: Record<string, string> = {
  "/mac-merkezi": "Maça tıkla: kadro, ağırlıklı eksikler, form, istatistik, hava ve senaryolar tek ekranda.",
  "/tahmin-botu": "Botun bülten çıktısı: değer kuralını geçen bütün seçimler, maç maç.",
  "/tahmin-arsivi": "Masanın kararları: Günün Kararı, Meclis Görüşleri, Karar Birliği ve kilitli defter.",
  "/guven-panosu": "Haftalık kayıt, isabet, ROI ve hangi pazarda tuttuğu. Kayıplar dahil.",
  "/gundem-masasi": "Transfer, sakatlık ve teknik direktör gündemi, maçlara bağlı.",
  "/veri-laboratuvari": "Bu sezonun pazar ligleri ve maç maç takım serileri.",
};

export default function Home() {
  const meta = ROUTES[0];
  usePageMeta(meta.title, meta.description);
  const today = trDay();
  const book = useAsync("home:book", async () => {
    const [p, c] = await Promise.all([api.allPredictions(), api.allCoupons()]);
    return { p, c };
  });
  const next = useAsync(`home:next:${today}`, async () => {
    const days = await api.matchDays(today, addDays(today, 10));
    const d = Object.keys(days).sort()[0];
    return d ? { day: d, matches: await api.matchesOnDay(d) } : null;
  });
  const newsQ = useAsync("news:home", () => api.news(60));

  const preds = book.data?.p ?? [];
  const bets = toBets(preds, book.data?.c ?? []);
  const S = summarize(bets.filter((b) => b.kind === "tekli"));
  const T = summarize(bets);
  const gkAll = (book.data?.c ?? []).filter((c) => c.tag === "gunun_karari");
  const gk = gkAll.filter((c) => c.coupon_date >= today).sort((a, b) => a.coupon_date.localeCompare(b.coupon_date))[0] ?? null;
  const gkLegs = gk ? preds.filter((p) => p.coupon_id === gk.id) : [];
  const lastGk = !gk ? gkAll.sort((a, b) => b.coupon_date.localeCompare(a.coupon_date))[0] : null;
  const news = dedupNews(newsQ.data ?? []).slice(0, 5);
  const offline = book.error === "offline";
  const nm = next.data?.matches ?? [];
  const leagues = new Set(nm.map((m) => m.league)).size;

  return (
    <div className="home landing">
      <section className="hero">
        <div className="hero-bg" aria-hidden="true" />
        <p className="kicker">Futbolun karar masası</p>
        <h1 className="hero-title">Her şey <em>tek masada.</em></h1>
        <p className="hero-lead">
          90 Meclis her maçı veriyle tartışır: kadro, eksik, form, istatistik, hava ve piyasa. Değer gördüğü yerde kararını maçtan saatler önce verir ve kilitler; kazancı da kaybı da herkesin önünde tutar.
        </p>
        <div className="hero-cta">
          <Link to="/tahmin-arsivi" className="btn primary">Günün Kararı</Link>
          <Link to="/mac-merkezi" className="btn ghost">Maç Merkezi</Link>
          <Link to="/guven-panosu" className="btn ghost">Güven Panosu</Link>
        </div>
      </section>

      <div className="grid-2 land-top">
        <Card title="Günün Kararı" aside={<Link to="/tahmin-arsivi" className="more">Masaya git →</Link>} className="gk-teaser">
          <Gate loading={book.loading} error={book.error} rows={2}>
            {gk ? (
              <>
                <div className="gk-head">
                  <span className="muted small">{gk.coupon_date === today ? "Bugün" : dateLong(gk.coupon_date + "T12:00:00+03:00")} · {gkLegs.length} maç</span>
                  <span className="gk-odds"><small>Toplam oran</small><b>{num(gk.total_odds)}</b></span>
                </div>
                <ul className="gk-legs">
                  {gkLegs.map((p) => (
                    <li key={p.id}><Link to={matchPath(p.match_id)}><span className="muted small">{time(p.kickoff_at)}</span> {p.home_name} – {p.away_name}</Link><b>{pickLabel(p.market, p.selection, p.line, p.home_name ?? "Ev", p.away_name ?? "Dep")}</b></li>
                  ))}
                </ul>
                <p className="muted tiny">Maçlardan önce kilitlendi · <StatusPill status={gk.status} /></p>
              </>
            ) : (
              <Empty title="Günün Kararı maçtan saatler önce yayımlanır" icon="◆">
                Masa, 2,30–4,00 bandında değer taşıyan 2–3 maçlık bir kombinasyon bulduğunda kuponu burada açar.
                {lastGk && <> Son kupon: {dateLong(lastGk.coupon_date + "T12:00:00+03:00")} · {num(lastGk.total_odds)} · <StatusPill status={lastGk.status} /></>}
              </Empty>
            )}
          </Gate>
        </Card>

        <Card title="Güven Panosu" aside={<Link to="/guven-panosu" className="more">Tüm kayıt →</Link>}>
          {offline ? <p className="muted small">Veri şu an alınamıyor.</p> : book.loading ? <Skeleton rows={1} h={64} /> : (
            <div className="kpis two">
              <Stat label="Kilitli karar" value={preds.length} />
              <Stat label="Tekli isabet" value={pct(S.hit, 1)} sub={`${S.won}/${S.won + S.lost} sonuçlanan`} />
              <Stat label="Toplam kâr (birim)" value={T.profit !== null ? signed(T.profit) : "—"} tone={(T.profit ?? 0) > 0 ? "pos" : (T.profit ?? 0) < 0 ? "neg" : "muted"} sub="tekliler + kuponlar" />
              <Stat label="Toplam ROI" value={T.roi !== null ? `${signed(T.roi * 100, 1)}%` : "—"} sub={`${T.priced} piyasa oranlı bahis`} />
            </div>
          )}
          <p className="muted tiny">Kayıplar silinmez. Kâr yalnızca gerçek piyasa oranlarıyla, 1 birim sabit hesaplanır.</p>
        </Card>
      </div>

      <Card title={next.data ? (next.data.day === today ? "Bugünün maçları" : `Sıradaki maç günü · ${dateLong(next.data.day + "T12:00:00+03:00")}`) : "Maçlar"}
        aside={<Link to="/mac-merkezi" className="more">Maç Merkezi →</Link>}>
        <Gate loading={next.loading} error={next.error} rows={4}>
          {nm.length ? (
            <>
              <p className="muted small">{nm.length} maç · {leagues} lig. Her maçın sayfasında Meclis'in analizi, senaryoları ve tahmini 11'i var.</p>
              <div className="mlist">{nm.slice(0, 8).map((m: Match) => <MatchRow key={m.id} m={m} />)}</div>
              {nm.length > 8 && <Link to="/mac-merkezi" className="btn ghost wide">Bütün maçlar ({nm.length})</Link>}
            </>
          ) : <Empty title="Yakın tarihte maç görünmüyor" icon="◎" />}
        </Gate>
      </Card>

      <Card title="Gündem Masası" aside={<Link to="/gundem-masasi" className="more">Tüm gündem →</Link>}>
        <Gate loading={newsQ.loading} error={newsQ.error} rows={3}>
          {news.length ? (
            <ul className="news-mini">
              {news.map((n) => (
                <li key={n.id}>
                  <a href={n.link} target="_blank" rel="noopener noreferrer">{n.title}</a>
                  <span className="muted small">{n.source}{n.alsoIn.length ? ` +${n.alsoIn.length} kaynak` : ""} · {relTime(n.published_at)}{n.match_ids[0] ? ` · ${league(n.match_ids[0].split(":")[0]).name}` : ""}</span>
                </li>
              ))}
            </ul>
          ) : <p className="muted small">Gündem her sabah taranır.</p>}
        </Gate>
      </Card>

      <section className="pillars" aria-label="Bölümler">
        {NAV.map((n) => (
          <Link key={n.to} to={n.to} className="pillar">
            <span className="pillar-icon" aria-hidden="true">{n.icon}</span>
            <strong>{n.label}</strong>
            <span>{PILLARS[n.to]}</span>
          </Link>
        ))}
      </section>

      <section className="manifesto">
        <div>
          <h2>Masanın kuralları</h2>
          <p>Her maç analiz edilir; yalnızca değer taşıyan seçim karara dönüşür. Karar maç başlamadan saatler önce deftere yazılır; kayıt anı sunucu saatiyle damgalanır, seçim, oran ve olasılık sonradan değiştirilemez, kayıt silinemez. Model bu sezon genelinde çalışır.</p>
        </div>
        <ul>
          <li><b>Kilitli defter</b><span>Maç başladıktan sonra ekleme ya da düzeltme yok.</span></li>
          <li><b>Dürüst kâr/zarar</b><span>Gerçek piyasa oranı, 1 birim sabit.</span></li>
          <li><b>Tek masa</b><span>Veri, analiz, karar ve sonuç aynı yerde.</span></li>
        </ul>
      </section>
      <Disclaimer />
    </div>
  );
}
