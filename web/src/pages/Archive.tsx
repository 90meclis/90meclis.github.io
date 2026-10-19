import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { dateShort, dateTime, hoursBefore, num, pct, signed, time } from "../lib/format";
import { MARKET_LABELS, STATUS_LABELS, TAG_LABELS, league, pickLabel } from "../lib/labels";
import { matchPath } from "../lib/match";
import { usePageMeta, ROUTES } from "../lib/seo";
import { CouponCard } from "../components/CouponCard";
import { Disclaimer, Empty, Gate, PageHead, StatusPill, TagPill } from "../components/ui";
import type { PredStatus, Tag } from "../lib/types";

const PAGE = 40;

export default function Archive() {
  const meta = ROUTES[3];
  usePageMeta(meta.title, meta.description);
  const d = useAsync("archive", async () => {
    const [preds, coupons] = await Promise.all([api.allPredictions(), api.allCoupons()]);
    return { preds, coupons };
  });
  const [tag, setTag] = useState<Tag | "">("");
  const [status, setStatus] = useState<PredStatus | "">("");
  const [lg, setLg] = useState("");
  const [market, setMarket] = useState("");
  const [qText, setQ] = useState("");
  const [n, setN] = useState(PAGE);
  const [view, setView] = useState<"kayit" | "kupon">("kayit");

  const preds = useMemo(() => d.data?.preds ?? [], [d.data]);
  const leagues = useMemo(() => [...new Set(preds.map((p) => p.league ?? ""))].filter(Boolean).sort((a, b) => league(a).order - league(b).order), [preds]);
  const markets = useMemo(() => [...new Set(preds.map((p) => p.market))].sort(), [preds]);
  const rows = preds.filter((p) =>
    (!tag || p.tag === tag) && (!status || p.status === status) && (!lg || p.league === lg) && (!market || p.market === market) &&
    (!qText || `${p.home_name} ${p.away_name}`.toLocaleLowerCase("tr-TR").includes(qText.toLocaleLowerCase("tr-TR"))),
  );

  return (
    <>
      <PageHead kicker="Değiştirilemez defter" title="Tahmin Arşivi">
        Her karar maç başlamadan önce kilitlenir. Kayıt anı sunucu saatiyle damgalanır; seçim, oran ve olasılık sonradan değiştirilemez, hiçbir kayıt silinemez.
      </PageHead>
      <div className="seg" role="tablist" aria-label="Arşiv görünümü">
        {([["kayit", "Kayıtlar"], ["kupon", "Kuponlar"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={view === k} className={view === k ? "on" : ""} onClick={() => setView(k)}>{l}</button>
        ))}
      </div>
      <Gate loading={d.loading} error={d.error} rows={6}>
        {view === "kayit" && (
          <>
            <div className="filters">
              <label><span>Etiket</span><select value={tag} onChange={(e) => setTag(e.target.value as Tag | "")}><option value="">Tümü</option>{Object.entries(TAG_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
              <label><span>Durum</span><select value={status} onChange={(e) => setStatus(e.target.value as PredStatus | "")}><option value="">Tümü</option>{Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
              <label><span>Lig</span><select value={lg} onChange={(e) => setLg(e.target.value)}><option value="">Tümü</option>{leagues.map((l) => <option key={l} value={l}>{league(l).name}</option>)}</select></label>
              <label><span>Pazar</span><select value={market} onChange={(e) => setMarket(e.target.value)}><option value="">Tümü</option>{markets.map((m) => <option key={m} value={m}>{MARKET_LABELS[m] ?? m}</option>)}</select></label>
              <label className="grow"><span>Takım ara</span><input type="search" value={qText} onChange={(e) => setQ(e.target.value)} placeholder="ör. Galatasaray" /></label>
            </div>
            <p className="muted small">{rows.length} kayıt</p>
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
        {view === "kupon" && (
          d.data!.coupons.length ? (
            <div className="coupons">{d.data!.coupons.map((c) => <CouponCard key={c.id} c={c} legs={preds.filter((p) => p.coupon_id === c.id)} />)}</div>
          ) : <Empty title="Henüz kupon yok" icon="◆">Günün Kararı yalnızca 2,30–4,00 bandında değerli bir kombinasyon bulunursa kurulur.</Empty>
        )}
      </Gate>
      <Disclaimer />
    </>
  );
}
