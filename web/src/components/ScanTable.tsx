import { MARKET_GROUPS, pickLabel, sourceLabel } from "../lib/labels";
import { num, pct, signed } from "../lib/format";
import type { ScanRow } from "../lib/scan";

/** Pazar taraması tablosu: model, marjsız piyasa olasılığı, oran ve değer; grup grup. */
export function ScanTable({ rows, home, away, groups, picked }: {
  rows: ScanRow[]; home: string; away: string; groups?: string[]; picked?: Set<string>;
}) {
  const gs = Object.keys(MARKET_GROUPS).filter((g) => (!groups || groups.includes(g)) && rows.some((r) => r.group === g));
  if (!gs.length) return <p className="muted small">Bu maç için pazar verisi yok.</p>;
  const hasM = rows.some((r) => r.pModel != null), hasP = rows.some((r) => r.pMarket != null), hasO = rows.some((r) => r.odds);
  const srcs = [...new Set(rows.map((r) => r.src).filter(Boolean).map((s) => sourceLabel(s!)))].slice(0, 3);
  return (
    <div className="scan">
      {gs.map((g) => (
        <div key={g} className="scan-group">
          <h4>{g}</h4>
          <table className="scan-tbl">
            <thead><tr><th>Seçim</th>{hasM && <th>Ortak</th>}{hasP && <th>Piyasa</th>}{hasO && <th>Oran</th>}{hasM && hasO && <th>Değer</th>}</tr></thead>
            <tbody>
              {rows.filter((r) => r.group === g).map((r, i) => {
                const k = `${r.market}|${r.selection}|${r.line ?? ""}`;
                return (
                  <tr key={i} className={`${r.value ? "val" : ""} ${picked?.has(k) ? "pick" : ""}`}>
                    <td>{pickLabel(r.market, r.selection, r.line, home, away)}</td>
                    {hasM && <td className="n">{r.pModel != null ? pct(r.pModel) : <span className="dim">·</span>}</td>}
                    {hasP && <td className="n">{r.pMarket != null ? pct(r.pMarket) : <span className="dim">·</span>}</td>}
                    {hasO && <td className="n">{r.odds ? num(r.odds) : <span className="dim">·</span>}</td>}
                    {hasM && hasO && <td className={`n ${r.edge != null && !r.wild ? (r.edge >= 0.03 ? "pos" : r.edge < 0 ? "neg" : "") : ""}`}>{r.wild ? <span className="dim" title="Model piyasadan 20 puandan fazla ayrışıyor: değer sayılmaz">⚠ ayrışma</span> : r.edge != null && r.pModel != null ? `${signed(r.edge * 100, 1)}%` : <span className="dim">·</span>}</td>}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
      <p className="muted tiny">Ortak: Meclis modelinin olasılığı. · işareti: o hücrede veri yok. ⚠ ayrışma: model piyasadan 20 puandan fazla uzak; Ortak bunu değer saymaz. Piyasa: oranlardan marjı arındırılmış olasılık. Değer: piyasa ile kalibre edilmiş olasılık × oran − 1. {srcs.length ? `Oran kaynağı: ${srcs.join(", ")}.` : ""}</p>
    </div>
  );
}
