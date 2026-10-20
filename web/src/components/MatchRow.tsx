import { Link } from "react-router-dom";
import type { Match, Prediction } from "../lib/types";
import type { BotAnalysis } from "../lib/data";
import { time, num, pct, signed } from "../lib/format";
import { hasScore, matchPath, matchState, odds1x2 } from "../lib/match";
import { TAG_LABELS, pickLabel } from "../lib/labels";
import { scanMatch } from "../lib/scan";

const UEFA = new Set(["CL", "EL", "ECL"]);
const TAG_SHORT: Record<string, string> = { gunun_karari: "Günün Kararı", meclis_gorusu: "Meclis Görüşü", karar_birligi: "Karar Birliği" };

/** Maç Merkezi satırı: saat/durum, takımlar, kupa rozeti, model 1X2 (kendi modeli varsa), en değerli pazar, karar rozeti. */
export function MatchRow({ m, picks, an }: { m: Match; picks?: Prediction[]; an?: BotAnalysis }) {
  const st = matchState(m);
  const o = odds1x2(m);
  const sc = hasScore(m);
  const homeWin = sc && m.home_goals! > m.away_goals!;
  const awayWin = sc && m.away_goals! > m.home_goals!;
  const own = (an?.basis ?? "").startsWith("model") && !!an?.ready;
  const p1 = own ? Object.fromEntries((an?.markets ?? []).filter((x) => x.market === "1X2").map((x) => [x.selection, x.probability])) : {};
  const enough = Math.min(an?.model_matches?.home ?? 0, an?.model_matches?.away ?? 0) >= (an?.min_team_matches ?? 4);
  const best = own && enough && st.key === "gelecek"
    ? scanMatch(m, an?.markets, true).filter((r) => r.value).sort((a, b) => (b.edge ?? 0) - (a.edge ?? 0))[0] : undefined;
  const pick = picks?.find((p) => p.tag === "gunun_karari") ?? picks?.find((p) => p.tag === "meclis_gorusu") ?? picks?.[0];
  return (
    <Link to={matchPath(m.id)} className={`mrow rich s-${st.key}`}>
      <div className="mrow-time">
        {st.key === "gelecek" ? <time dateTime={m.kickoff_at}>{time(m.kickoff_at)}</time> : <span className={`mstate ${st.key}`}>{st.label}</span>}
        {UEFA.has(m.league) && <small className="cup-badge">{m.league}</small>}
      </div>
      <div className="mrow-teams">
        <div className={`team ${homeWin ? "win" : ""}`}><span className="tname">{m.home_name}</span>{sc && <b className="tgoal">{m.home_goals}</b>}</div>
        <div className={`team ${awayWin ? "win" : ""}`}><span className="tname">{m.away_name}</span>{sc && <b className="tgoal">{m.away_goals}</b>}</div>
        {(p1["1"] !== undefined || best || pick) && (
          <div className="mrow-meta">
            {pick && <span className={`mini-pick st-${pick.status}`} title={TAG_LABELS[pick.tag]}>◆ {TAG_SHORT[pick.tag]}: {pickLabel(pick.market, pick.selection, pick.line, m.home_name, m.away_name)}</span>}
            {p1["1"] !== undefined && <span className="m1x2" title="Meclis modeli: ev / beraberlik / deplasman">Model {pct(p1["1"])} · {pct(p1["X"])} · {pct(p1["2"])}</span>}
            {best && !pick && <span className="mval" title="Modelin piyasaya göre en değerli bulduğu pazar">Değer: {pickLabel(best.market, best.selection, best.line, m.home_name, m.away_name)} {num(best.odds)} ({signed((best.edge ?? 0) * 100, 0)}%)</span>}
          </div>
        )}
      </div>
      <div className="mrow-side">
        {o && o["1"] ? (
          <span className="odds-mini" aria-label="Maç sonucu oranları">
            <span>{num(o["1"])}</span><span>{num(o.X)}</span><span>{num(o["2"])}</span>
          </span>
        ) : null}
      </div>
      <span className="chev" aria-hidden="true">›</span>
    </Link>
  );
}
