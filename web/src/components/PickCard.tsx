import { Link } from "react-router-dom";
import type { Prediction } from "../lib/types";
import { pickLabel, league, sourceLabel } from "../lib/labels";
import { dateTime, hoursBefore, num, pct, signed, time, dateShort } from "../lib/format";
import { matchPath } from "../lib/match";
import { StatusPill, TagPill } from "./ui";
import { ShareButton } from "./ShareButton";
import { SealBadge } from "./SealBadge";
import { cardForPick } from "../lib/share";
import type { Kart } from "../lib/editorial";
import { Gerekce, SonNot } from "./Gerekce";
import { Kurtarildi } from "./Kurtarildi";

export function PickCard({ p, compact = false, kart, not }: { p: Prediction; compact?: boolean; kart?: Kart; not?: string }) {
  const home = p.home_name ?? "Ev", away = p.away_name ?? "Dep";
  return (
    <article className={`pick st-border-${p.status} ${compact ? "compact" : ""}`}>
      <div className="pick-top">
        <TagPill tag={p.tag} />
        <StatusPill status={p.status} />
        <Kurtarildi mv={p.model_version} />
      </div>
      <Link to={matchPath(p.match_id)} className="pick-match">
        <span className="muted small">{league(p.league).flag} {league(p.league).name} · {dateShort(p.kickoff_at)} {time(p.kickoff_at)}</span>
        <strong>{home} – {away}</strong>
      </Link>
      <div className="pick-sel">
        <span className="pick-label">{pickLabel(p.market, p.selection, p.line, home, away)}</span>
        <span className="pick-odds">
          {p.odds ? <><b>{num(p.odds)}</b><small>{sourceLabel(p.odds_source)}</small></> : <><b>{num(p.fair_odds)}</b><small>adil oran</small></>}
        </span>
      </div>
      <div className="pick-meta">
        <span>Olasılık <b>{pct(p.probability)}</b></span>
        {p.confidence !== null && <span>Güven <b>{pct(p.confidence)}</b></span>}
        {p.result_value && <span>Sonuç <b>{p.result_value}</b></span>}
        {p.profit !== null && p.status !== "bekliyor" && <span>K/Z <b className={p.profit >= 0 ? "pos" : "neg"}>{signed(p.profit)}</b></span>}
      </div>
      {kart ? <Gerekce k={kart} compact={compact} /> : !compact && p.scenario_note && <p className="pick-note"><span className="muted">Senaryo:</span> {p.scenario_note}</p>}
      {not && <SonNot text={not} />}
      <p className="pick-lock" title={`Kayıt: ${dateTime(p.recorded_at)} TSİ`}>
        <span aria-hidden="true">🔒</span> Maçtan {hoursBefore(p.recorded_at, p.kickoff_at)} kilitlendi
      </p>
      <SealBadge id={p.id} />
      {!compact && <ShareButton make={() => cardForPick(p)} name={`90meclis-${p.match_id.replace(/:/g, "-")}.png`} text={`90 Meclis · ${home} – ${away}`} />}
    </article>
  );
}
