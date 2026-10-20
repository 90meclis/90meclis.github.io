import { MARKET_GROUPS, pickLabel, sourceLabel } from "../lib/labels";
import { num, pct, signed } from "../lib/format";
import type { ScanRow } from "../lib/scan";

/** Pazar taraması tablosu: model, marjsız piyasa olasılığı, oran ve değer; grup grup. */
export function ScanTable({ rows, home, away, groups, picked }: {
  rows: ScanRow[]; home: string; away: string; groups?: string[]; picked?: Set<string>;
}) {
  const gs = Object.keys(MARKET_GROUPS).filter((g) => (!groups || groups.includes(g)) && rows.some((r) => r.group === g));
  if (!gs.length) return <p className="muted small">Bu maç için pazar verisi yok.</p>;
  const srcs = [...new Set(rows.map((r) => r.src).filter(Boolean).map((s) => sourceLabel(s!)))].slice(0, 3);
  return (
    <div className="scan">
      {gs.map((g) => (
        <div key={g} className="scan-group">
          <h4>{g}</h4>
          <table className="scan-tbl">
            <thead><tr><th>Seçim</th><th>Model</th><th>Piyasa</th><th>Oran</th><th>Değer</th></tr></thead>
            <tbody>
              {rows.filter((r) => r.group === g).map((r, i) => {
                const k = `${r.market}|${r.selection}|${r.line ?? ""}`;
                return (
                  <tr key={i} className={`${r.value ? "val" : ""} ${picked?.has(k) ? "pick" : ""}`}>
                    <td>{pickLabel(r.market, r.selection, r.line, home, away)}</td>
                    <td className="n">{r.pModel != null ? pct(r.pModel) : "—"}</td>
                    <td className="n">{r.pMarket != null ? pct(r.pMarket) : "—"}</td>
                    <td className="n">{r.odds ? num(r.odds) : "—"}</td>
                    <td className={`n ${r.edge != null ? (r.edge >= 0.03 ? "pos" : r.edge < 0 ? "neg" : "") : ""}`}>{r.edge != null && r.pModel != null ? `${signed(r.edge * 100, 1)}%` : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
      <p className="muted tiny">Model: Meclis'in olasılığı. Piyasa: oranlardan marjı arındırılmış olasılık. Değer: piyasa ile kalibre edilmiş olasılık × oran − 1. {srcs.length ? `Oran kaynağı: ${srcs.join(", ")}.` : ""}</p>
    </div>
  );
}
