import { Link } from "react-router-dom";
import type { Match, Prediction } from "../lib/types";
import { time, num } from "../lib/format";
import { hasScore, matchPath, matchState, odds1x2 } from "../lib/match";

export function MatchRow({ m, pick }: { m: Match; pick?: Prediction }) {
  const st = matchState(m);
  const o = odds1x2(m);
  const sc = hasScore(m);
  const homeWin = sc && m.home_goals! > m.away_goals!;
  const awayWin = sc && m.away_goals! > m.home_goals!;
  return (
    <Link to={matchPath(m.id)} className={`mrow s-${st.key}`}>
      <div className="mrow-time">
        {st.key === "gelecek" ? <time dateTime={m.kickoff_at}>{time(m.kickoff_at)}</time> : <span className={`mstate ${st.key}`}>{st.label}</span>}
      </div>
      <div className="mrow-teams">
        <div className={`team ${homeWin ? "win" : ""}`}><span className="tname">{m.home_name}</span>{sc && <b className="tgoal">{m.home_goals}</b>}</div>
        <div className={`team ${awayWin ? "win" : ""}`}><span className="tname">{m.away_name}</span>{sc && <b className="tgoal">{m.away_goals}</b>}</div>
      </div>
      <div className="mrow-side">
        {pick ? (
          <span className={`mini-pick st-${pick.status}`} title="Meclis kararı var">◆ Karar</span>
        ) : o && o["1"] ? (
          <span className="odds-mini" aria-label="Maç sonucu oranları">
            <span>{num(o["1"])}</span><span>{num(o.X)}</span><span>{num(o["2"])}</span>
          </span>
        ) : null}
      </div>
      <span className="chev" aria-hidden="true">›</span>
    </Link>
  );
}
