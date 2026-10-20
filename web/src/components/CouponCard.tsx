import type { Coupon, Prediction } from "../lib/types";
import { Link } from "react-router-dom";
import { num, pct, signed, dateMed, time } from "../lib/format";
import { league, pickLabel } from "../lib/labels";
import { matchPath } from "../lib/match";
import { StatusPill, TagPill } from "./ui";
import { PickCard } from "./PickCard";

export function CouponCard({ c, legs }: { c: Coupon; legs: Prediction[] }) {
  return (
    <article className={`coupon c-${c.tag} st-border-${c.status}`}>
      <header className="coupon-head">
        <div><TagPill tag={c.tag} /><span className="muted small"> {dateMed(c.coupon_date + "T12:00:00+03:00")} · {c.legs_count} maç</span></div>
        <StatusPill status={c.status} />
      </header>
      <div className="coupon-nums">
        <div><small>Toplam oran</small><b>{num(c.total_odds)}</b>{c.odds_source === "model_adil" && <em className="muted tiny">adil oran</em>}</div>
        <div><small>Ortak olasılık</small><b>{pct(c.joint_probability, 1)}</b></div>
        <div><small>Kâr/Zarar</small><b className={c.profit === null ? "" : c.profit >= 0 ? "pos" : "neg"}>{c.profit === null ? "—" : signed(c.profit)}</b></div>
      </div>
      <div className="coupon-legs">{legs.map((p) => <PickCard key={p.id} p={p} compact />)}</div>
    </article>
  );
}

/** Günün Kararı vitrini: masanın ana kuponu. */
export function CouponHero({ c, legs }: { c: Coupon; legs: Prediction[] }) {
  return (
    <article className={`coupon-hero st-border-${c.status}`}>
      <header>
        <div><span className="kicker">{dateMed(c.coupon_date + "T12:00:00+03:00")}</span><h2>Günün Kararı</h2><span className="muted small">{legs.length} maç · toplam oran {num(c.total_odds)}</span></div>
        <div className="ch-odds"><small>Toplam oran</small><b>{num(c.total_odds)}</b>{c.odds_source === "model_adil" && <em>adil oran</em>}</div>
      </header>
      <ol className="ch-legs">
        {legs.map((p) => (
          <li key={p.id}>
            <Link to={matchPath(p.match_id)} className="ch-match"><span className="muted small">{league(p.league).flag} {time(p.kickoff_at)}</span><b>{p.home_name} – {p.away_name}</b></Link>
            <span className="ch-pick">{pickLabel(p.market, p.selection, p.line, p.home_name ?? "Ev", p.away_name ?? "Dep")}</span>
            <span className="ch-o">{num(p.odds ?? p.fair_odds)}</span>
            <StatusPill status={p.status} />
          </li>
        ))}
      </ol>
      <footer>
        <span>Ortak olasılık <b>{pct(c.joint_probability, 1)}</b></span>
        <span>Durum <StatusPill status={c.status} /></span>
        {c.profit !== null && <span>K/Z <b className={c.profit >= 0 ? "pos" : "neg"}>{signed(c.profit)}</b></span>}
        <span className="muted tiny">🔒 Maçlardan önce kilitlendi · 18+ · garanti yoktur</span>
      </footer>
    </article>
  );
}
