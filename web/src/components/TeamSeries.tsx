import { Link } from "react-router-dom";
import { dateShort, num } from "../lib/format";
import { matchPath, result, sameTeam } from "../lib/match";
import type { Match, MatchStat } from "../lib/types";

/** Takımın maç maç tablosu (Veri Laboratuvarı). */
export function TeamSeries({ name, teamId, games, stats }: { name: string; teamId: string; games: Match[]; stats: MatchStat[] }) {
  const sidx = new Map(stats.map((s) => [`${s.match_id}:${s.side}`, s]));
  if (!games.length) return <div><h3 className="ts-name">{name}</h3><p className="muted small">Bu sezon için maç verisi henüz yok.</p></div>;
  const hasXg = games.some((g) => sidx.get(`${g.id}:${sameTeam(g.home_team_id, teamId) ? "home" : "away"}`)?.xg != null);
  return (
    <div className="team-series">
      <h3 className="ts-name">{name}</h3>
      <div className="form-dots" aria-label="Son 5 maç">
        {games.slice(0, 5).map((g) => { const r = result(g, teamId); return <span key={g.id} className={`fd r-${r}`} title={`${g.home_name} ${g.home_goals}-${g.away_goals} ${g.away_name}`}>{r}</span>; })}
      </div>
      <div className="table-wrap">
        <table className="tbl tight">
          <thead><tr><th>Tarih</th><th>Rakip</th><th>Skor</th><th title="Şut">Şut</th><th title="İsabetli şut">İsb.</th><th title="Korner">Krn</th><th title="Kart (sarı+kırmızı)">Kart</th>{hasXg && <th>xG</th>}</tr></thead>
          <tbody>
            {games.map((g) => {
              const home = sameTeam(g.home_team_id, teamId);
              const s = sidx.get(`${g.id}:${home ? "home" : "away"}`);
              const r = result(g, teamId);
              const card = s && (s.yellow !== null || s.red !== null) ? (s.yellow ?? 0) + (s.red ?? 0) : null;
              return (
                <tr key={g.id}>
                  <td>{dateShort(g.kickoff_at)}</td>
                  <td><Link to={matchPath(g.id)}>{home ? "" : "@ "}{home ? g.away_name : g.home_name}</Link></td>
                  <td><span className={`res r-${r}`}>{home ? `${g.home_goals}-${g.away_goals}` : `${g.away_goals}-${g.home_goals}`}</span></td>
                  <td>{s?.shots ?? "–"}</td><td>{s?.shots_on_target ?? "–"}</td><td>{s?.corners ?? "–"}</td><td>{card ?? "–"}</td>
                  {hasXg && <td>{s?.xg != null ? num(s.xg, 1) : "–"}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted tiny">Skor takımın bakış açısıyla; "@" deplasman maçı.</p>
    </div>
  );
}

