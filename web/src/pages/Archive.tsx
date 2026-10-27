import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { dateLong, dateShort, dateTime, hoursBefore, num, pct, signed, time, trDay } from "../lib/format";
import { MARKET_LABELS, STATUS_LABELS, league, pickLabel } from "../lib/labels";
import { matchPath } from "../lib/match";
import { usePageMeta, ROUTES } from "../lib/seo";
import { CouponCard, CouponHero } from "../components/CouponCard";
import { PickCard } from "../components/PickCard";
import { Empty, Gate, StatusPill, TagPill } from "../components/ui";
import type { PredStatus } from "../lib/types";

const PAGE = 40;

export default function Archive() {
  const meta = ROUTES[3];
  usePageMeta(meta.title, meta.description);
  const d = useAsync("archive", async () => {
    const [preds, coupons] = await Promise.all([api.allPredictions(), api.allCoupons()]);
    return { preds, coupons };
  });
  const [status, setStatus] = useState<PredStatus | "">("");
  const [lg, setLg] = useState("");
  const [market, setMarket] = useState("");
  const [qText, setQ] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const inRange = (iso: string | null | undefined) => {
    if (!from && !to) return true;
    if (!iso) return false;
    const day = trDay(iso);
    return (!from || day >= from) && (!to || day <= to);
  };
  const [n, setN] = useState(PAGE);
  const [view, setView] = useState<"masa" | "kayit" | "kupon">("masa");
  const [pickDay, setPickDay] = useState("");

  const preds = useMemo(() => d.data?.preds ?? [], [d.data]);
  const leagues = useMemo(() => [...new Set(preds.map((p) => p.league ?? ""))].filter(Boolean).sort((a, b) => league(a).order - league(b).order), [preds]);
  const coupons = (d.data?.coupons ?? []).filter((c) => inRange(c.first_kickoff_at));
  const markets = useMemo(() => [...new Set(preds.map((p) => p.market))].sort(), [preds]);
  const inScope = preds.filter((p) => inRange(p.kickoff_at));
  const scopeCount = `${new Set(inScope.map((p) => p.match_id)).size} maç · ${coupons.length} kupon · ${inScope.filter((p) => p.tag === "meclis_gorusu").length} tekli`;
  // Tekliler sekmesi yalnızca Meclis Görüşü kayıtlarını listeler; kupon bacakları kuponlarının altında durur.
  const singlesAll = preds.filter((p) => p.tag === "meclis_gorusu");
  const rows = singlesAll.filter((p) => inRange(p.kickoff_at) &&
    (!status || p.status === status) && (!lg || p.league === lg) && (!market || p.market === market) &&
    (!qText || `${p.home_name} ${p.away_name}`.toLocaleLowerCase("tr-TR").includes(qText.toLocaleLowerCase("tr-TR"))),
  );

  // Masa: seçilen günün küratörlü içeriği
  const allCoupons = d.data?.coupons ?? [];
  const contentDays = useMemo(() => [...new Set([...preds.map((p) => trDay(p.kickoff_at)), ...(d.data?.coupons ?? []).map((c) => c.coupon_date)])].sort().reverse(), [preds, d.data]);
  const today = trDay();
  const autoDay = [...contentDays].reverse().find((x) => x >= today) ?? contentDays[0] ?? today;
  const day = pickDay || autoDay;
  const dayCoupons = allCoupons.filter((c) => c.coupon_date === day);
  const gk = dayCoupons.filter((c) => c.tag === "gunun_karari");
  const kb = dayCoupons.filter((c) => c.tag === "karar_birligi");
  const legsOf = (id: string) => preds.filter((p) => p.coupon_id === id);
  const gkMatches = new Set(gk.flatMap((c) => legsOf(c.id).map((p) => p.match_id)));
  const daySingles = preds.filter((p) => p.tag === "meclis_gorusu" && trDay(p.kickoff_at) === day && !gkMatches.has(p.match_id))
    .sort((a, b) => a.kickoff_at.localeCompare(b.kickoff_at));

  const ledger = useMemo(() => {
    const items = [
      ...preds.filter((p) => p.tag === "meclis_gorusu").map((p) => p.status as string),
      ...(d.data?.coupons ?? []).map((c) => c.status as string),
    ];
    return {
      total: items.length,
      won: items.filter((x) => x === "kazandi").length,
      lost: items.filter((x) => x === "kaybetti").length,
      pending: items.filter((x) => x === "bekliyor").length,
    };
  }, [preds, d.data]);

  return (
    <>
      <header className="ledger-head">
        <span className="ledger-kicker">Meclis Defteri · yayımlanan kararlar</span>
        <h1>Tahmin Arşivi</h1>
        <p>Burada yalnızca Meclis'in yayımladığı kararlar durur: <b>Günün Kararı</b> kuponu, <b>Meclis Görüşleri</b> ve <b>Karar Birliği</b>. Hepsi Ortak'ın analiz ettiği bütün bültenden, tutma olasılığı en yüksek seçimlerden süzülür; bir maç günde yalnızca bir üründe yer alır. Kuponlar bir önceki gün 18:00'de (TSİ) bütün gün masadayken kurulur; her karar maçtan en az 3 saat önce kilitlenir, mühürlenir ve kazansın kaybetsin hiç silinmez.</p>
        <div className="ledger-stats">
          <div><b>{ledger.total}</b><span>karar</span></div>
          <div className="w"><b>{ledger.won}</b><span>kazandı</span></div>
          <div className="l"><b>{ledger.lost}</b><span>kaybetti</span></div>
          <div className="p"><b>{ledger.pending}</b><span>bekliyor</span></div>
        </div>
        <p className="ledger-note">Kayıt 27 Ekim 2026'da başladı · <Link to="/ortak">Bütün bültenin analizi Ortak'ta →</Link></p>
      </header>
      <div className="seg" role="tablist" aria-label="Arşiv görünümü">
        {([["masa", "Masa"], ["kayit", "Tekliler"], ["kupon", "Kuponlar"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={view === k} className={view === k ? "on" : ""} onClick={() => setView(k)}>{l}</button>
        ))}
      </div>
      {view !== "masa" && <div className="filters dates">
        <label><span>Başlangıç (TSİ)</span><input type="date" value={from} max={to || undefined} onChange={(e) => { setFrom(e.target.value); setN(PAGE); }} /></label>
        <label><span>Bitiş (TSİ)</span><input type="date" value={to} min={from || undefined} onChange={(e) => { setTo(e.target.value); setN(PAGE); }} /></label>
        {(from || to) && <button className="btn ghost" onClick={() => { setFrom(""); setTo(""); }}>Tarihi temizle</button>}
      </div>}
      <Gate loading={d.loading} error={d.error} rows={6}>
        {view === "masa" && (
          <div className="masa">
            <div className="masa-day">
              <h2 className="day-title">{day === today ? "Bugünün masası" : dateLong(day + "T12:00:00+03:00")}</h2>
              {contentDays.length > 1 && (
                <label><span className="muted small">Gün</span>
                  <select value={day} onChange={(e) => setPickDay(e.target.value)}>
                    {contentDays.map((x) => <option key={x} value={x}>{dateLong(x + "T12:00:00+03:00")}</option>)}
                  </select>
                </label>
              )}
            </div>
            {gk.length ? gk.map((c) => <CouponHero key={c.id} c={c} legs={legsOf(c.id)} />) : (
              <div className="coupon-hero empty"><span className="kicker">Günün Kararı</span><p className="muted">{day >= today ? "Günün Kararı, değer gören seçimler netleştiğinde maçtan en az 3 saat önce burada kilitlenir. Değer yoksa Meclis oynamaz." : "Bu gün Günün Kararı çıkmadı: kurallara uyan değerli seçim yoktu."}</p></div>
            )}
            <h3 className="sub">Meclis Görüşleri <span className="muted">· {daySingles.length} tekli</span></h3>
            {daySingles.length ? <div className="picks grid">{daySingles.map((p) => <PickCard key={p.id} p={p} />)}</div>
              : <p className="muted">Bu gün için Günün Kararı dışında tekli görüş yok.</p>}
            {kb.length > 0 && (
              <>
                <h3 className="sub">Karar Birliği</h3>
                <div className="coupons">{kb.map((c) => <CouponCard key={c.id} c={c} legs={legsOf(c.id)} />)}</div>
              </>
            )}
            
          </div>
        )}
        {view === "kayit" && (
          <>
            <div className="filters">
              <label><span>Durum</span><select value={status} onChange={(e) => setStatus(e.target.value as PredStatus | "")}><option value="">Tümü</option>{Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
              <label><span>Lig</span><select value={lg} onChange={(e) => setLg(e.target.value)}><option value="">Tümü</option>{leagues.map((l) => <option key={l} value={l}>{league(l).name}</option>)}</select></label>
              <label><span>Pazar</span><select value={market} onChange={(e) => setMarket(e.target.value)}><option value="">Tümü</option>{markets.map((m) => <option key={m} value={m}>{MARKET_LABELS[m] ?? m}</option>)}</select></label>
              <label className="grow"><span>Takım ara</span><input type="search" value={qText} onChange={(e) => setQ(e.target.value)} placeholder="ör. Galatasaray" /></label>
            </div>
            <p className="muted small">{scopeCount}{rows.length !== inScope.filter((p) => p.tag === "meclis_gorusu").length ? ` · filtrede ${rows.length} tekli` : ""}</p>
            {rows.length === 0 ? <Empty title="Bu filtrelerde kayıt yok" icon="▤" /> : (
              <div className="table-wrap">
                <table className="tbl ledger">
                  <thead><tr><th>Maç</th><th>Etiket</th><th>Tahmin</th><th>Oran</th><th>Olasılık</th><th>Durum</th><th>Sonuç</th><th>K/Z</th><th>Kilit</th></tr></thead>
                  <tbody>
                    {rows.slice(0, n).map((p) => (
                      <tr key={p.id}>
                        <td data-label="Maç"><Link to={matchPath(p.match_id)}><b>{p.home_name} – {p.away_name}</b></Link><br /><small className="muted">{league(p.league).flag} {dateShort(p.kickoff_at)} {time(p.kickoff_at)}</small></td>
                        <td data-label="Etiket"><TagPill tag={p.tag} /></td>
                        <td data-label="Tahmin">{pickLabel(p.market, p.selection, p.line, p.home_name ?? "Ev", p.away_name ?? "Dep")}</td>
                        <td data-label="Oran">{p.odds ? num(p.odds) : <span title="Piyasa oranı yoktu; modelin adil oranı">{num(p.fair_odds)}<sup>a</sup></span>}</td>
                        <td data-label="Olasılık">{pct(p.probability)}</td>
                        <td data-label="Durum"><StatusPill status={p.status} /></td>
                        <td data-label="Sonuç">{p.result_value ?? "—"}</td>
                        <td data-label="K/Z" className={p.profit === null ? "" : p.profit > 0 ? "pos" : p.profit < 0 ? "neg" : ""}>{p.profit === null ? "—" : signed(p.profit)}</td>
                        <td data-label="Kilit"><span title={`Kayıt: ${dateTime(p.recorded_at)} TSİ`}>🔒 {hoursBefore(p.recorded_at, p.kickoff_at)}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {rows.length > n && <button className="btn ghost wide" onClick={() => setN(n + PAGE)}>Daha fazla göster</button>}
            <p className="muted tiny"><sup>a</sup> Kayıt anında piyasa oranı yoktu; modelin adil oranı gösterilir. Bu kayıtlar isabete dahildir, kâr/zarara dahil değildir.</p>
          </>
        )}
        {view === "kupon" && <p className="muted small">{scopeCount}</p>}
        {view === "kupon" && (
          coupons.length ? (
            <div className="coupons">{coupons.map((c) => <CouponCard key={c.id} c={c} legs={preds.filter((p) => p.coupon_id === c.id)} />)}</div>
          ) : <Empty title={from || to ? "Bu tarih aralığında kupon yok" : "Henüz kupon yok"} icon="◆" />
        )}
      </Gate>
    </>
  );
}
