import { useMemo } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { summarize, toBets, clvStat, SETTLED } from "../lib/trust";
import { trDay, addDays, relTime, num, time, dateLong, dateTime, dayLabel, signed } from "../lib/format";
import { league, pickLabel, TAG_LABELS } from "../lib/labels";
import { matchPath, matchState } from "../lib/match";
import { dedupNews } from "../lib/news";
import { usePageMeta, ROUTES } from "../lib/seo";
import { Empty, Gate, Skeleton, StatusPill } from "../components/ui";
import { CountUp, LineBars } from "../components/elite/viz";
import { useCountdown } from "../lib/useCountdown";
import { NAV } from "../lib/nav";
import { bulletinRows, hunt, scanFor, streakText, type Saha, type ScanRow } from "../lib/lab";
import type { Coupon, Match, Prediction } from "../lib/types";
import "../styles/elite.css";

const UEFA = new Set(["CL", "EL", "ECL"]);
const ortak = () => NAV.find((n) => n.to === "/ortak") ?? { to: "/ortak", label: "Ortak", icon: "◆", short: "Ortak" };

const SECTION_TXT: [RegExp, string][] = [
  [/mac-merkezi/, "Maça dokun: kadro, ağırlıklı eksikler, yaptığı/verdiği istatistik, Avrupa izi, senaryolar."],
  [/ortak/, "Ortak bütün bülteni tarar: her maç, her pazar, model olasılığı ve piyasa değeri."],
  [/tahmin-arsivi/, "Günün Kararı, Meclis Görüşleri ve Karar Birliği. Kilitli defter."],
  [/guven-panosu/, "Tahminler iyi mi? İsabet, ROI, kapanış oranı ve kalibrasyon, kayıplar dahil."],
  [/gundem-masasi/, "Sakatlık, transfer ve teknik direktör gündemi, maçlara bağlı."],
  [/veri-laboratuvari/, "Kendi analizini yap: takım seç, maç maç seri, liderler, Seri Avcısı."],
  [/sezon-simulasyonu/, "Kalan fikstür 10.000 kez oynandı: şampiyonluk, ilk dört ve düşme olasılıkları."],
];

function Countdown({ iso }: { iso: string }) {
  const c = useCountdown(iso);
  if (!c) return null;
  if (c.done) return <span className="cd live">Başladı</span>;
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    <span className="cd" aria-label="İlk maça kalan süre">
      {c.d > 0 && <><b>{c.d}</b><small>g</small></>}<b>{pad(c.h)}</b><small>sa</small><b>{pad(c.m)}</b><small>dk</small><b>{pad(c.s)}</b><small>sn</small>
    </span>
  );
}

function seal(c: Coupon): string | null {
  const r = c as unknown as Record<string, unknown>;
  const v = r.muhur ?? r.seal ?? r.hash ?? r.kanit_ozeti ?? r.sha256;
  return typeof v === "string" && v.length >= 8 ? v : null;
}

function GkHero({ gk, legs, live }: { gk: Coupon; legs: Prediction[]; live: boolean }) {
  const s = seal(gk);
  const settled = SETTLED.has(gk.status);
  return (
    <article className={`gk-hero ${settled ? "settled st-" + gk.status : ""}`}>
      <div className="gk-glow" aria-hidden="true" />
      <header className="gk-top">
        <div>
          <p className="eyebrow">{live ? (gk.coupon_date === trDay() ? "Bugünün kuponu" : dateLong(gk.coupon_date + "T12:00:00+03:00")) : "Son kupon · sonuçlandı"}</p>
          <h2>Günün Kararı</h2>
          <p className="muted small">Meclis'in ana tercihlerinden oluşan günün kuponu</p>
        </div>
        <div className="gk-odds"><small>Toplam oran</small><b><CountUp to={Number(gk.total_odds)} digits={2} /></b></div>
      </header>
      <ol className="gk-legs2">
        {legs.map((p, i) => (
          <li key={p.id}>
            <span className="gl-n">{i + 1}</span>
            <Link to={matchPath(p.match_id)} className="gl-m">
              <span className="muted tiny">{league(p.league).flag} {league(p.league).name} · {dayLabel(trDay(p.kickoff_at)).top} {time(p.kickoff_at)}</span>
              <b>{p.home_name} – {p.away_name}</b>
            </Link>
            <span className="gl-p">
              <b>{pickLabel(p.market, p.selection, p.line, p.home_name ?? "Ev", p.away_name ?? "Dep")}</b>
              <span className="muted tiny">{p.odds ? `oran ${num(p.odds)}` : ""}{p.probability ? ` · %${Math.round(p.probability * 100)}` : ""}</span>
            </span>
            {settled && <StatusPill status={p.status} />}
          </li>
        ))}
      </ol>
      <footer className="gk-foot">
        <span className="lockb" title="Kayıt maçlardan önce kilitlendi; seçim, oran ve olasılık değiştirilemez">🔒 Kilitli · {dateTime(gk.created_at)}{s ? <> · mühür <code>{s.slice(0, 10)}…</code></> : null}</span>
        {live && !settled ? <Countdown iso={gk.first_kickoff_at} /> : <span className={`stamp st-${gk.status}`}>{gk.status === "kazandi" ? "KAZANDI" : gk.status === "kaybetti" ? "KAYBETTİ" : gk.status === "iade" ? "İADE" : "BAŞLADI"}</span>}
      </footer>
      <div className="gk-cta"><Link to="/tahmin-arsivi" className="btn primary">Kuponu aç</Link>{settled && <span className="muted small">Kaybettiğimizde de burada kalır. Bugünün kuponu masaya düştüğünde bu kartın yerini alır.</span>}</div>
    </article>
  );
}

function WinBar({ p1, px, p2 }: { p1: number; px: number; p2: number }) {
  return (
    <div className="wbar" role="img" aria-label={`Model: ev %${Math.round(p1 * 100)}, beraberlik %${Math.round(px * 100)}, deplasman %${Math.round(p2 * 100)}`}>
      <span className="w1" style={{ flexGrow: p1 }}><b>%{Math.round(p1 * 100)}</b></span>
      <span className="wx" style={{ flexGrow: px }}><b>%{Math.round(px * 100)}</b></span>
      <span className="w2" style={{ flexGrow: p2 }}><b>%{Math.round(p2 * 100)}</b></span>
    </div>
  );
}

export default function Home() {
  const meta = ROUTES[0];
  usePageMeta(meta.title, meta.description);
  const today = trDay();
  const book = useAsync("home:book", async () => {
    const [p, c] = await Promise.all([api.allPredictions(), api.allCoupons()]);
    return { p, c };
  });
  const next = useAsync(`home:next2:${today}`, async () => {
    const days = await api.matchDays(today, addDays(today, 10));
    const ds = Object.keys(days).sort();
    let day = ds[0], matches: Match[] = [];
    for (const d of ds.slice(0, 3)) {
      matches = (await api.matchesOnDay(d)).filter((m) => matchState(m).key === "gelecek");
      day = d;
      if (matches.length) break;
    }
    if (!day) return null;
    const top = [...matches].sort((a, b) => league(a.league).order - league(b.league).order || a.kickoff_at.localeCompare(b.kickoff_at));
    const an = await api.analysesLite(top.slice(0, 40).map((m) => m.id), true);
    const scan: ScanRow[] = await scanFor(matches.map((m) => m.id)).catch(() => []);
    return { day, matches: top, an, scan };
  });
  // Seri Avcısı ağır sorgu: üst bölümler yüklendikten sonra ve yalnızca öncelikli liglerin 30 maçı için
  const hq = useAsync(next.data !== undefined || next.error ? `home:hunt:${today}` : null, async () => {
    const b = await bulletinRows(30);
    return { ...b, scan: await scanFor(b.fixtures.map((f) => f.id)) };
  });
  const newsQ = useAsync("news:home", () => api.news(60));

  const preds = useMemo(() => book.data?.p ?? [], [book.data]);
  const coupons = useMemo(() => book.data?.c ?? [], [book.data]);
  const bets = toBets(preds, coupons);
  const T = summarize(bets);
  const clv = clvStat(bets.filter((b) => b.kind === "tekli"));
  const gkAll = coupons.filter((c) => c.tag === "gunun_karari");
  const gkLive = gkAll.filter((c) => c.coupon_date >= today && !SETTLED.has(c.status)).sort((a, b) => a.coupon_date.localeCompare(b.coupon_date))[0] ?? null;
  const gk = gkLive ?? [...gkAll].sort((a, b) => b.coupon_date.localeCompare(a.coupon_date))[0] ?? null;
  const gkLegs = gk ? preds.filter((p) => p.coupon_id === gk.id).sort((a, b) => a.kickoff_at.localeCompare(b.kickoff_at)) : [];
  const gkMatchIds = new Set(gkLegs.map((p) => p.match_id));
  const recent = useMemo(() => {
    const rows: { t: string; label: string; sub: string; status: string; to: string }[] = [];
    for (const p of preds) if (p.tag === "meclis_gorusu" && SETTLED.has(p.status)) rows.push({ t: p.kickoff_at, label: `${p.home_name} – ${p.away_name}`, sub: `${TAG_LABELS[p.tag]} · ${pickLabel(p.market, p.selection, p.line, p.home_name ?? "Ev", p.away_name ?? "Dep")}${p.odds ? " · " + num(p.odds) : ""}`, status: p.status, to: matchPath(p.match_id) });
    for (const c of coupons) if (SETTLED.has(c.status)) rows.push({ t: c.first_kickoff_at, label: `${TAG_LABELS[c.tag]} · ${c.legs_count} maç`, sub: `toplam oran ${num(c.total_odds)}`, status: c.status, to: "/tahmin-arsivi" });
    return rows.sort((a, b) => b.t.localeCompare(a.t)).slice(0, 6);
  }, [preds, coupons]);
  const news = useMemo(() => dedupNews(newsQ.data ?? []).slice(0, 5), [newsQ.data]);
  const O = ortak();

  const nd = next.data;
  const featured = (nd?.matches ?? []).filter((m) => {
    const a = nd?.an[m.id];
    return a && (a.basis ?? "").startsWith("model") && a.ready && (a.markets ?? []).some((x) => x.market === "1X2");
  }).sort((a, b) => league(a.league).order - league(b.league).order || a.kickoff_at.localeCompare(b.kickoff_at)).slice(0, 6);
  // İsabet önceliği: Ortak'ın en olası (kalibre) seçimleri; oran ≥ 1.50, veri kontrolü (aşırı ayrışma) hariç
  const pk = (r: ScanRow) => r.p_kal ?? r.p_model ?? 0;
  const candRows = (nd?.scan ?? []).filter((r) => r.deger && r.odds && r.odds >= 1.5 && Math.abs(r.edge ?? 0) <= 0.4 && !gkMatchIds.has(r.match_id));
  const chosen = candRows.filter((r) => r.secildi);
  const picks = (chosen.length ? chosen : candRows).sort((a, b) => pk(b) - pk(a));
  const picksAreChoices = chosen.length > 0;
  const pickRows = [...new Map(picks.map((r) => [r.match_id, r])).values()].slice(0, 4);
  const mById = new Map((nd?.matches ?? []).map((m) => [m.id, m]));

  const huntTop = useMemo(() => {
    if (!hq.data) return [];
    const slug = (id: string) => id.slice(id.indexOf(":") + 1);
    const names = new Map(hq.data.rows.map((r) => [r.team_slug, r]));
    const ts = hq.data.fixtures.flatMap((f) => (["home", "away"] as const).map((side) => {
      const s = slug(side === "home" ? f.home_team_id : f.away_team_id), r = names.get(s);
      return r ? { t: { slug: s, id: r.team_id, name: side === "home" ? f.home_name : f.away_name }, saha: (side === "home" ? "ic" : "dis") as Saha, fixture: f, side } : null;
    })).filter((x): x is NonNullable<typeof x> => x !== null);
    return hunt(hq.data.rows, ts, 5).slice(0, 3);
  }, [hq.data]);

  const settledN = T.won + T.lost;
  return (
    <div className="elite home2">
      <section className="hero2">
        <div className="hero2-bg" aria-hidden="true" />
        <p className="kicker">90 Meclis · futbolun karar masası</p>
        <h1 className="hero2-title">Kaybı da<br /><em>gösteren masa.</em></h1>
        <p className="hero2-lead">Her maç veriyle konuşur. Meclis kararını maçtan saatler önce verir ve kilitler. Kazanç da kayıp da, kapanış oranı da herkesin önünde.</p>
        <div className="hero-cta">
          <a href="#gunun-karari" className="btn primary">Günün Kararı</a>
          <Link to="/mac-merkezi" className="btn ghost">Bugünün maçları</Link>
          <Link to="/veri-laboratuvari" className="btn ghost">Kendi analizini yap</Link>
        </div>
        <div className="trust-strip" aria-label="Canlı kayıt">
          {book.loading ? <Skeleton rows={1} h={52} /> : book.error ? null : (
            <>
              <div><small>Kayıt</small><b>{T.won}<i>–</i>{T.lost}</b><span>{T.total} kilitli karar</span></div>
              <div><small>İsabet</small><b>{T.hit !== null ? <CountUp to={T.hit * 100} suffix="" prefix="%" /> : "—"}</b><span>{settledN} sonuçlanan</span></div>
              <div><small>ROI</small><b className={(T.roi ?? 0) > 0 ? "pos" : (T.roi ?? 0) < 0 ? "neg" : ""}>{T.roi !== null ? `${signed(T.roi * 100, 0)}%` : "—"}</b><span>{T.priced} piyasa oranlı</span></div>
              {clv && clv.n > 0 && <div><small>CLV</small><b className={clv.mean > 0 ? "pos" : "neg"}>{signed(clv.mean * 100, 1)}%</b><span>{clv.n} kapanışla ölçüldü</span></div>}
              {settledN < 30 && <p className="ts-note">{settledN === 0 ? "Kayıt 27 Ekim 2026'da başladı. İsabet, ROI ve kapanış oranı farkı ilk sonuçlarla burada." : `Örneklem yeni (${settledN} sonuç). Rakamlar her sonuçla güncellenir, hiçbiri silinmez.`} <Link to="/guven-panosu">Güven Panosu →</Link></p>}
            </>
          )}
        </div>
      </section>

      <div className="home-grid">
        <section id="gunun-karari" className="hg-gk">
          <Gate loading={book.loading} error={book.error} rows={3}>
            {gk ? <GkHero gk={gk} legs={gkLegs} live={!!gkLive} /> : (
              <div className="coupon-hero empty gk-wait">
                <span className="kicker">Günün Kararı</span>
                <h2>Masa hazırlanıyor</h2>
                <p className="muted">Meclis'in ana tercihlerinden oluşan günün kuponu, seçimler netleştiğinde burada açılır ve kilitlenir.</p>
                <Link to={O.to} className="more">Bütün bülten şu an {O.label}'ın masasında →</Link>
              </div>
            )}
          </Gate>
        </section>

        <section className="hg-side">
          <div className="sec-head"><h2>{O.label} ne görüyor?</h2><Link to={O.to} className="more">Bütün tarama →</Link></div>
          <Gate loading={next.loading} error={next.error} rows={3}>
            {pickRows.length ? (<>
              <p className="muted tiny op-cap">{picksAreChoices ? "Ortak'ın bu bültende seçtikleri: oranı en az 1.50 olan pazarlar içinde tutma olasılığı en yüksek olanlar (model + marjsız piyasa)." : "Tutma olasılığı en yüksek adaylar (oran ≥ 1.50)."}</p>
              <ul className="ortak-list">
                {pickRows.map((r) => {
                  const m = mById.get(r.match_id);
                  if (!m) return null;
                  return (
                    <li key={r.match_id}><Link to={matchPath(m.id)}>
                      <span className="muted tiny">{league(m.league).flag} {time(m.kickoff_at)} · {m.home_name} – {m.away_name}</span>
                      <b>{pickLabel(r.market, r.selection, r.line, m.home_name, m.away_name)}</b>
                      <span className="op-nums"><span>olasılık <b>%{Math.round(pk(r) * 100)}</b></span><span>oran <b>{num(r.odds)}</b></span><span className={(r.edge ?? 0) >= 0 ? "pos" : "muted"}>değer <b>{signed((r.edge ?? 0) * 100, 1)}%</b></span></span>
                    </Link></li>
                  );
                })}
              </ul>
            </>) : <p className="muted small">Ortak bu bültende oranı 1.50 ve üzeri olup tutma olasılığı %50'yi geçen seçim görmüyor. Bülten tazelendikçe burası güncellenir.</p>}
          </Gate>
          {huntTop.length > 0 && (
            <div className="hunt-mini">
              <div className="sec-head"><h3>Seri Avcısı</h3><Link to="/veri-laboratuvari?gor=seri" className="more">Hepsi →</Link></div>
              {huntTop.map((s, i) => (
                <Link key={i} to={s.fixture ? matchPath(s.fixture.id) : "/veri-laboratuvari?gor=seri"} className="hm-row">
                  <span className="h-run"><b>{s.run}</b><small>maç</small></span>
                  <span><b>{s.t.name}</b><span className="muted tiny"> {streakText(s)}</span></span>
                  <LineBars values={s.vals.slice(-8)} line={s.s.k === "kg" ? null : s.line} over={s.over} height={22} compact />
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="block">
        <div className="sec-head"><h2>{nd ? (nd.day === today ? "Bugünün öne çıkanları" : `Sıradaki maç günü · ${dateLong(nd.day + "T12:00:00+03:00")}`) : "Maçlar"}</h2><Link to="/mac-merkezi" className="more">Bütün maçlar{nd ? ` (${nd.matches.length})` : ""} →</Link></div>
        <Gate loading={next.loading} error={next.error} rows={4}>
          {featured.length ? (
            <div className="fx-grid">
              {featured.map((m) => {
                const mk = Object.fromEntries((nd!.an[m.id]?.markets ?? []).filter((x) => x.market === "1X2").map((x) => [x.selection, x.probability]));
                const val = (nd!.scan ?? []).filter((r) => r.match_id === m.id && r.deger && r.odds && r.odds >= 1.5 && Math.abs(r.edge ?? 0) <= 0.4).sort((a, b) => pk(b) - pk(a))[0];
                return (
                  <Link key={m.id} to={matchPath(m.id)} className="fx">
                    <span className="fx-top"><span>{league(m.league).flag} {league(m.league).name}{UEFA.has(m.league) && <i className="cupb">{m.league}</i>}</span><span>{dayLabel(trDay(m.kickoff_at)).top} {time(m.kickoff_at)}</span></span>
                    <span className="fx-teams"><b>{m.home_name}</b><b>{m.away_name}</b></span>
                    <WinBar p1={mk["1"] ?? 0} px={mk["X"] ?? 0} p2={mk["2"] ?? 0} />
                    <span className="fx-foot">{gkMatchIds.has(m.id) ? <span className="vbadge v-gk">◆ Günün Kararı'nda</span> : val ? <span className="vbadge v-yes">En olası: {pickLabel(val.market, val.selection, val.line, m.home_name, m.away_name)} · %{Math.round(pk(val) * 100)} · {num(val.odds)}</span> : <span className="muted tiny">Model olasılığı · ev / X / dep</span>}</span>
                  </Link>
                );
              })}
            </div>
          ) : <Empty title="Yakın tarihte analiz edilmiş maç görünmüyor" icon="◎" />}
        </Gate>
      </section>

      <div className="grid-2 block">
        {recent.length > 0 && <section className="panel">
          <div className="sec-head"><h2>Son sonuçlar</h2><Link to="/guven-panosu" className="more">Bütün kayıt →</Link></div>
          {recent.length ? (
            <ul className="res-list">
              {recent.map((r, i) => (
                <li key={i}><Link to={r.to}><span><b>{r.label}</b><span className="muted tiny">{r.sub}</span></span><StatusPill status={r.status} /></Link></li>
              ))}
            </ul>
          ) : <p className="muted small">İlk sonuçlar geldiğinde, kazanan da kaybeden de burada.</p>}
          <p className="muted tiny">Kayıplar silinmez, gizlenmez. Kâr yalnızca gerçek piyasa oranıyla, 1 birim sabit hesaplanır.</p>
        </section>}
        <section className="panel">
          <div className="sec-head"><h2>Gündem</h2><Link to="/gundem-masasi" className="more">Tüm gündem →</Link></div>
          <Gate loading={newsQ.loading} error={newsQ.error} rows={3}>
            {news.length ? (
              <ul className="news-mini">
                {news.map((n) => (
                  <li key={n.id}>
                    <a href={n.link} target="_blank" rel="noopener noreferrer">{n.title}</a>
                    <span className="muted small">{n.source}{n.alsoIn.length ? ` +${n.alsoIn.length} kaynak` : ""} · {relTime(n.published_at)}</span>
                  </li>
                ))}
              </ul>
            ) : <p className="muted small">Gündem her sabah taranır.</p>}
          </Gate>
        </section>
      </div>

      <section className="sections" aria-label="Bölümler">
        {NAV.map((n) => {
          const txt = SECTION_TXT.find(([re]) => re.test(n.to))?.[1] ?? "";
          const lab = n.label;
          return (
            <Link key={n.to} to={n.to} className="sect">
              <span className="sect-i" aria-hidden="true">{n.icon}</span>
              <span><strong>{lab}</strong><span>{txt}</span></span>
              <span className="sect-arrow" aria-hidden="true">→</span>
            </Link>
          );
        })}
      </section>

      <section className="promise">
        <h2>Neden 90 Meclis?</h2>
        <ul>
          <li><b>Kilitli defter</b><span>Karar maçtan önce yazılır; seçim, oran ve olasılık sonradan değişmez, kayıt silinmez.</span></li>
          <li><b>Yalnızca değer</b><span>Model piyasadan anlamlı biçimde ayrılmıyorsa Meclis oynamaz. Oranlar yalnızca yabancı piyasalardan.</span></li>
          <li><b>Ölçülebilir</b><span>İsabet, ROI, kapanış oranı farkı ve kalibrasyon herkese açık.</span></li>
        </ul>
      </section>
    </div>
  );
}
