import { Link } from "react-router-dom";
import type { Match, Prediction } from "../lib/types";
import type { BotAnalysis } from "../lib/data";
import { time, num, pct, signed } from "../lib/format";
import { hasScore, matchPath, matchState, odds1x2 } from "../lib/match";
import { TAG_LABELS, pickLabel } from "../lib/labels";
import { scanMatch } from "../lib/scan";
import { Crest } from "./Crest";

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
  const scan = own ? scanMatch(m, an?.markets, true) : [];
  // Model 1X2'de piyasadan 20 puandan fazla ayrışıyorsa modelin bu maçtaki sayıları güvenilmez: şerit piyasaya döner, değer gösterilmez
  const off = scan.some((r) => r.market === "1X2" && r.wild);
  const best = own && enough && !off && st.key === "gelecek"
    ? scan.filter((r) => r.value).sort((a, b) => (b.edge ?? 0) - (a.edge ?? 0))[0] : undefined;
  // olasılık şeridi: kendi modeli varsa model, yoksa marjı arındırılmış piyasa
  const inv = o && o["1"] && o.X && o["2"] ? [1 / o["1"], 1 / o.X, 1 / o["2"]] : null;
  const mk = inv ? inv.map((x) => x / (inv[0] + inv[1] + inv[2])) : null;
  const bar = p1["1"] !== undefined && !off ? { src: "Model", v: [p1["1"], p1["X"], p1["2"]] as number[] } : mk && st.key === "gelecek" ? { src: "Piyasa", v: mk } : null;
  const pick = picks?.find((p) => p.tag === "gunun_karari") ?? picks?.find((p) => p.tag === "meclis_gorusu") ?? picks?.[0];
  return (
    <Link to={matchPath(m.id)} className={`mrow rich s-${st.key}`}>
      <div className="mrow-time">
        {st.key === "gelecek" ? <time dateTime={m.kickoff_at}>{time(m.kickoff_at)}</time> : <span className={`mstate ${st.key}`}>{st.label}</span>}
        {UEFA.has(m.league) && <small className="cup-badge">{m.league}</small>}
      </div>
      <div className="mrow-teams">
        <div className={`team ${homeWin ? "win" : ""}`}><Crest name={m.home_name} small /><span className="tname">{m.home_name}</span>{sc && <b className="tgoal">{m.home_goals}</b>}</div>
        <div className={`team ${awayWin ? "win" : ""}`}><Crest name={m.away_name} small /><span className="tname">{m.away_name}</span>{sc && <b className="tgoal">{m.away_goals}</b>}</div>
        {bar && (
          <div className={`mrow-pb ${bar.src === "Model" ? "own" : ""}`} title={`${bar.src}: ev ${pct(bar.v[0])} · beraberlik ${pct(bar.v[1])} · deplasman ${pct(bar.v[2])}`}>
            <span className="mrow-pb-bar"><i style={{ width: `${bar.v[0] * 100}%` }} /><i style={{ width: `${bar.v[1] * 100}%` }} /><i style={{ width: `${bar.v[2] * 100}%` }} /></span>
            <small>{bar.src} {pct(bar.v[0])} · {pct(bar.v[1])} · {pct(bar.v[2])}{own && !off && an?.lambdas ? ` · gol bekl. ${num(an.lambdas.home, 1)}–${num(an.lambdas.away, 1)}` : ""}</small>
            {off && <span className="vk" title="Meclis modeli bu maçta piyasadan 20 puandan fazla ayrışıyor; sayıları kontrol edilene kadar değer gösterilmez">veri kontrol</span>}
          </div>
        )}
        {(best || pick) && (
          <div className="mrow-meta">
            {pick && <span className={`mini-pick st-${pick.status}`} title={TAG_LABELS[pick.tag]}>◆ {TAG_SHORT[pick.tag]}: {pickLabel(pick.market, pick.selection, pick.line, m.home_name, m.away_name)}</span>}
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
