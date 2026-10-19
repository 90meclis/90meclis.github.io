import { Link } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { summarize } from "../lib/trust";
import { pct, signed, trDay, addDays, relTime } from "../lib/format";
import { usePageMeta, ROUTES } from "../lib/seo";
import { PickCard } from "../components/PickCard";
import { MatchRow } from "../components/MatchRow";
import { Card, Disclaimer, Empty, Gate, Skeleton, Stat } from "../components/ui";
import { NAV } from "../components/Layout";
import type { Match } from "../lib/types";

const PILLARS: Record<string, string> = {
  "/mac-merkezi": "Form, istatistik, eksikler, ilk 11, hava ve oranlar tek ekranda.",
  "/tahmin-botu": "Her maça, saatler önce kilitlenen karar.",
  "/tahmin-arsivi": "Silinemeyen, değiştirilemeyen tahmin defteri.",
  "/guven-panosu": "İsabet, ROI ve kasa eğrisi; kayıplar dahil.",
  "/gundem-masasi": "Maçlara bağlanmış transfer ve sakatlık gündemi.",
  "/veri-laboratuvari": "Maç maç değerler: ortalamanın arkasındaki gerçek.",
};

export default function Home() {
  const meta = ROUTES[0];
  usePageMeta(meta.title, meta.description);
  const preds = useAsync("preds:all", api.allPredictions);
  const up = useAsync("preds:upcoming", api.upcomingPredictions);
  const today = trDay();
  const next = useAsync(`home:next:${today}`, async () => {
    const days = await api.matchDays(today, addDays(today, 10));
    const d = Object.keys(days).sort()[0];
    return d ? { day: d, matches: await api.matchesOnDay(d) } : null;
  });
  const newsQ = useAsync("news:home", () => api.news(6));

  const singles = (preds.data ?? []).filter((p) => p.tag === "meclis_gorusu");
  const s = summarize(singles);
  const live = (up.data ?? []).filter((p) => p.status === "bekliyor" || p.status === "basladi");
  const showcase = (live.length ? live : (up.data ?? [])).slice(0, 3);
  const offline = preds.error === "offline";

  return (
    <div className="home">
      <section className="hero">
        <div className="hero-bg" aria-hidden="true" />
        <p className="kicker">Futbol tahmin ve analiz masası</p>
        <h1 className="hero-title">Her şey <em>tek masada.</em></h1>
        <p className="hero-lead">
          90 Meclis maçları veriyle tartışır, kararını maçtan önce kilitler ve sonucu herkesin önünde tutar.
          Kazanç da kayıp da silinmez.
        </p>
        <div className="hero-cta">
          <Link to="/tahmin-botu" className="btn primary">Bugünün kararları</Link>
          <Link to="/guven-panosu" className="btn ghost">Güven Panosu</Link>
        </div>
        {!offline && (
          <div className="hero-stats">
            {preds.loading ? <Skeleton rows={1} h={64} /> : (
              <>
                <Stat label="Kilitli karar" value={preds.data?.length ?? 0} />
                <Stat label="İsabet" value={pct(s.hit, 1)} sub={`${s.won}/${s.won + s.lost} sonuçlanan`} />
                <Stat label="Kâr (birim)" value={signed(s.profit)} tone={s.profit > 0 ? "pos" : s.profit < 0 ? "neg" : "muted"} sub="piyasa oranlı tekliler" />
              </>
            )}
          </div>
        )}
      </section>

      <div className="grid-2">
        <Card title="Masadaki kararlar" aside={<Link to="/tahmin-botu" className="more">Tümü →</Link>}>
          <Gate loading={up.loading} error={up.error} rows={2}>
            {showcase.length ? (
              <div className="picks">{showcase.map((p) => <PickCard key={p.id} p={p} compact />)}</div>
            ) : (
              <Empty title="Bugün için karar henüz yok" icon="◆">Meclis kararları her maçtan saatler önce burada yayımlanır ve kilitlenir.</Empty>
            )}
          </Gate>
        </Card>
        <Card title={next.data ? (next.data.day === today ? "Bugünün maçları" : "Sıradaki maç günü") : "Maçlar"} aside={<Link to="/mac-merkezi" className="more">Maç Merkezi →</Link>}>
          <Gate loading={next.loading} error={next.error} rows={4}>
            {next.data?.matches.length ? (
              <div className="mlist">{next.data.matches.slice(0, 8).map((m: Match) => <MatchRow key={m.id} m={m} />)}</div>
            ) : <Empty title="Yakın tarihte maç görünmüyor" icon="◎" />}
          </Gate>
        </Card>
      </div>

      <section className="pillars" aria-label="Bölümler">
        {NAV.map((n) => (
          <Link key={n.to} to={n.to} className="pillar">
            <span className="pillar-icon" aria-hidden="true">{n.icon}</span>
            <strong>{n.label}</strong>
            <span>{PILLARS[n.to]}</span>
          </Link>
        ))}
      </section>

      <Card title="Gündem Masası" aside={<Link to="/gundem-masasi" className="more">Tüm gündem →</Link>}>
        <Gate loading={newsQ.loading} error={newsQ.error} rows={3}>
          <ul className="news-mini">
            {(newsQ.data ?? []).slice(0, 6).map((n) => (
              <li key={n.id}>
                <a href={n.link} target="_blank" rel="noopener noreferrer">{n.title}</a>
                <span className="muted small">{n.source} · {relTime(n.published_at)}</span>
              </li>
            ))}
          </ul>
        </Gate>
      </Card>

      <section className="manifesto">
        <div>
          <h2>Neden güvenebilirsin?</h2>
          <p>Her tahmin maç başlamadan önce veritabanına yazılır. Kayıt anı sunucu saatiyle damgalanır; seçim, oran ve olasılık sonradan değiştirilemez, kayıt silinemez. Bültendeki her maç için karar, başlama saatinden saatler önce yayımlanır.</p>
        </div>
        <ul>
          <li><b>Kilitli defter</b><span>Maç başladıktan sonra ekleme yok.</span></li>
          <li><b>Dürüst kâr/zarar</b><span>Yalnızca gerçek piyasa oranlarıyla, 1 birim sabit.</span></li>
          <li><b>Her maça karar</b><span>Maçtan saatler önce, güven göstergesiyle.</span></li>
        </ul>
      </section>
      <Disclaimer />
    </div>
  );
}
