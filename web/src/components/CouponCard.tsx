import type { Coupon, Prediction } from "../lib/types";
import { num, pct, signed, dateMed } from "../lib/format";
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
