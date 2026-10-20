import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Card, Gate, PageHead } from "../components/ui";
import { leagueTables, seasonSim, simConsistent, type SimRow } from "../lib/data";
import { league } from "../lib/labels";
import { useAsync } from "../lib/useAsync";

/** %: 0 → "%0", <%0,5 → "<%1", aksi halde tam sayı. Boş/tire yok. */
const sp = (p: number) => (p <= 0 ? "%0" : p < 0.005 ? "<%1" : p > 0.995 && p < 1 ? ">%99" : `%${Math.round(p * 100)}`);

function Dist({ d, n }: { d: number[]; n: number }) {
  const mx = Math.max(...d, 0.0001);
  return (
    <span className="sim-dist" aria-label="Sıra dağılımı">
      {d.slice(0, n).map((v, i) => <i key={i} title={`${i + 1}. sıra: ${sp(v)}`} style={{ opacity: v <= 0 ? 0.08 : 0.15 + 0.85 * (v / mx) }} />)}
    </span>
  );
}

export default function Season() {
  const [q, setQ] = useSearchParams();
  const all = useAsync("sim:all", async () => {
    const sim = (await seasonSim()) ?? [];
    const lgs = [...new Set(sim.map((r) => r.league))];
    const tb = lgs.length ? (await leagueTables(lgs)) ?? [] : [];
    // yalnızca bugünkü puan durumuyla tutan ligler
    return sim.filter((r) => simConsistent(sim.filter((x) => x.league === r.league), tb.filter((x) => x.league === r.league)));
  }, []);
  const leagues = useMemo(() => {
    const s = [...new Set((all.data ?? []).map((r) => r.league))];
    return s.sort((a, b) => league(a).order - league(b).order);
  }, [all.data]);
  const lg = q.get("lig") && leagues.includes(q.get("lig")!) ? q.get("lig")! : leagues[0];
  const rows: SimRow[] = useMemo(() => (all.data ?? []).filter((r) => r.league === lg).sort((a, b) => a.ort_sira - b.ort_sira), [all.data, lg]);
  const cur = useMemo(() => {
    const m = new Map<string, number>();
    [...rows].sort((a, b) => b.mevcut_puan - a.mevcut_puan).forEach((r, i) => m.set(r.team_id, i + 1));
    return m;
  }, [rows]);
  const hasKume = rows.some((r) => r.kume > 0), has4 = rows.some((r) => r.ilk4 > 0 && r.ilk4 < 1);
  const fav = rows[0];
  const second = [...rows].sort((a, b) => b.sampiyon - a.sampiyon)[1];
  const danger = hasKume ? [...rows].sort((a, b) => b.kume - a.kume)[0] : null;
  const mover = [...rows].map((r) => ({ r, d: (cur.get(r.team_id) ?? 0) - r.tahmini_sira })).sort((a, b) => b.d - a.d)[0];
  const at = rows[0]?.computed_at ? new Intl.DateTimeFormat("tr-TR", { timeZone: "Europe/Istanbul", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }).format(new Date(rows[0].computed_at)) : null;
  if (!all.loading && !all.error && !(all.data ?? []).length) return (
    <PageHead kicker="Sezon Simülasyonu" title="Sezon sonu tablosu hazırlanıyor" />
  );
  return (
    <>
      <PageHead kicker="Sezon Simülasyonu" title="Sezon böyle biterse">
        Kalan bütün maçlar Meclis modeliyle {rows[0]?.kosu ? rows[0].kosu.toLocaleString("tr-TR") : "on binlerce"} kez oynatıldı. Şampiyonluk, ilk dört ve küme düşme olasılığı bu benzetimlerden sayılır.
      </PageHead>
      <Gate loading={all.loading} error={all.error} rows={8}>
        <div className="chips-scroll" role="group" aria-label="Lig">
          {leagues.map((l) => (
            <button key={l} type="button" className={`chip ${l === lg ? "on" : ""}`} onClick={() => setQ({ lig: l }, { replace: true })}>{league(l).flag} {league(l).name}</button>
          ))}
        </div>
        {fav && (
          <div className="sim-heads">
            <div className="sim-h lead"><small>Şampiyonluk favorisi</small><b>{fav.team_name}</b><span>{sp(fav.sampiyon)}{second && second.team_id !== fav.team_id ? ` · en yakın rakibi ${second.team_name} ${sp(second.sampiyon)}` : ""}</span></div>
            {danger && danger.kume > 0.05 && <div className="sim-h bad"><small>En büyük küme tehlikesi</small><b>{danger.team_name}</b><span>{sp(danger.kume)} düşme olasılığı</span></div>}
            {mover && mover.d >= 3 && <div className="sim-h up"><small>Tablo yalan söylüyor</small><b>{mover.r.team_name}</b><span>şu an {cur.get(mover.r.team_id)}., modele göre {mover.r.tahmini_sira}. bitirir</span></div>}
          </div>
        )}
        <Card title={`${league(lg).flag} ${league(lg).name}: tahmini sezon sonu`}>
          <div className="table-wrap">
            <table className="tbl sim-tbl">
              <thead><tr><th>#</th><th>Takım</th><th className="n" title="Şu anki puan → sezon sonu ortalama puan">Puan</th><th className="n">Şamp.</th>{has4 && <th className="n">İlk 4</th>}{hasKume && <th className="n">Düşme</th>}<th className="sim-dcol">Bitirdiği sıra</th></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const c = cur.get(r.team_id) ?? r.tahmini_sira, dd = c - r.tahmini_sira;
                  return (
                    <tr key={r.team_id}>
                      <td className="n">{r.tahmini_sira}{dd !== 0 && <small className={dd > 0 ? "pos" : "neg"}>{dd > 0 ? "▲" : "▼"}{Math.abs(dd)}</small>}</td>
                      <td className="sim-team"><Link to={`/veri-laboratuvari?lig=${r.league}&gor=takim&takim=${r.team_id.slice(r.team_id.indexOf(":") + 1)}`}>{r.team_name}</Link><small>{r.kalan_mac} maç kaldı</small></td>
                      <td className="n">{r.mevcut_puan}<small> → {Math.round(r.ort_puan)}</small></td>
                      <td className={`n ${r.sampiyon >= 0.2 ? "hot" : ""}`}>{sp(r.sampiyon)}</td>
                      {has4 && <td className="n">{sp(r.ilk4)}</td>}
                      {hasKume && <td className={`n ${r.kume >= 0.2 ? "cold" : ""}`}>{sp(r.kume)}</td>}
                      <td className="sim-dcol">{r.sira_dagilimi && <Dist d={r.sira_dagilimi} n={rows.length} />}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="muted tiny">▲▼: bugünkü sırasına göre fark. Bitirdiği sıra şeridi soldan sağa 1. sıradan sonuncuya; koyu hücre o sırada bitirme olasılığı yüksek. {rows[0]?.yontem ? `Yöntem: ${rows[0].yontem}.` : ""}{at ? ` Son hesap: ${at} TSİ.` : ""} Lig formatı düz olmayan (play-off'lu) ligler hesaplanmaz.</p>
        </Card>
      </Gate>
    </>
  );
}
