import { useId, useState } from "react";
import { dateShort, num, signed, pct } from "../lib/format";
import type { CurvePoint } from "../lib/trust";

/** Kasa eğrisi (SVG, bağımlılıksız). */
export function EquityChart({ points, height = 220 }: { points: CurvePoint[]; height?: number }) {
  const id = useId();
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, H = height, P = { l: 40, r: 12, t: 14, b: 26 };
  const data = [{ t: points[0]?.t ?? "", v: 0, label: "Başlangıç" }, ...points];
  const vs = data.map((d) => d.v);
  const lo = Math.min(0, ...vs), hi = Math.max(0, ...vs);
  const span = hi - lo || 1;
  const x = (i: number) => P.l + (i / Math.max(1, data.length - 1)) * (W - P.l - P.r);
  const y = (v: number) => P.t + (1 - (v - lo) / span) * (H - P.t - P.b);
  const path = data.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.v).toFixed(1)}`).join(" ");
  const area = `${path} L${x(data.length - 1)},${y(0)} L${x(0)},${y(0)} Z`;
  const last = data[data.length - 1].v;
  const tone = last >= 0 ? "pos" : "neg";
  const ticks = [lo, (lo + hi) / 2, hi];
  const h = hover !== null ? data[hover] : null;
  return (
    <figure className={`chart equity ${tone}`}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Kasa eğrisi: ${data.length - 1} sonuç, son durum ${signed(last)} birim`}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = ((e.clientX - r.left) / r.width) * W;
          const i = Math.round(((px - P.l) / (W - P.l - P.r)) * (data.length - 1));
          setHover(Math.max(0, Math.min(data.length - 1, i)));
        }}>
        <defs>
          <linearGradient id={`${id}-a`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="currentColor" stopOpacity=".35" />
            <stop offset="1" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={P.l} x2={W - P.r} y1={y(t)} y2={y(t)} className="grid" />
            <text x={P.l - 6} y={y(t) + 4} textAnchor="end" className="axis">{num(t, 1)}</text>
          </g>
        ))}
        <line x1={P.l} x2={W - P.r} y1={y(0)} y2={y(0)} className="zero" />
        <path d={area} fill={`url(#${id}-a)`} />
        <path d={path} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
        {data.length < 60 && data.map((d, i) => <circle key={i} cx={x(i)} cy={y(d.v)} r={hover === i ? 5 : 3} className="dot" />)}
        {h && hover !== null && <line x1={x(hover)} x2={x(hover)} y1={P.t} y2={H - P.b} className="cursor" />}
        <text x={P.l} y={H - 6} className="axis">{dateShort(data[0].t)}</text>
        <text x={W - P.r} y={H - 6} textAnchor="end" className="axis">{dateShort(data[data.length - 1].t)}</text>
      </svg>
      {h && (
        <figcaption className="chart-tip">
          <b>{signed(h.v)} birim</b> · {h.label}{h.t ? ` · ${dateShort(h.t)}` : ""}
        </figcaption>
      )}
    </figure>
  );
}

/** Maç maç değerler: her çubuk bir maç (ortalama değil). Eşik çizgisi varsa tutan/tutmayan renklenir. */
export function GameBars({ values, threshold, labels, height = 120, unit = "" }: {
  values: (number | null)[]; threshold?: number | null; labels?: string[]; height?: number; unit?: string;
}) {
  const max = Math.max(1, threshold ?? 0, ...values.map((v) => v ?? 0));
  return (
    <div className="gamebars" style={{ height }} role="img"
      aria-label={`Maç maç değerler (eskiden yeniye): ${values.map((v) => (v === null ? "veri yok" : v)).join(", ")}`}>
      {threshold !== undefined && threshold !== null && (
        <div className="gb-thr" style={{ bottom: `${(threshold / max) * 100}%` }}><span>{num(threshold, 1)}</span></div>
      )}
      {values.map((v, i) => {
        const hit = threshold === undefined || threshold === null ? null : v === null ? null : v > threshold;
        return (
          <div key={i} className="gb-col" title={`${labels?.[i] ?? ""}: ${v === null ? "veri yok" : v + unit}`}>
            <div className={`gb-bar ${v === null ? "na" : hit === null ? "" : hit ? "hit" : "miss"}`} style={{ height: v === null ? "6%" : `${Math.max(4, (v / max) * 100)}%` }}>
              <span className="gb-val">{v === null ? "–" : num(v, Number.isInteger(v) ? 0 : 1)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ProbBar({ p1, px, p2, home, away }: { p1: number; px: number; p2: number; home: string; away: string }) {
  return (
    <div className="probbar">
      <div className="pb-track" role="img" aria-label={`${home} ${pct(p1)}, beraberlik ${pct(px)}, ${away} ${pct(p2)}`}>
        <span className="pb-1" style={{ flexGrow: p1 }} />
        <span className="pb-x" style={{ flexGrow: px }} />
        <span className="pb-2" style={{ flexGrow: p2 }} />
      </div>
      <div className="pb-legend">
        <span><b>{pct(p1)}</b> {home}</span>
        <span><b>{pct(px)}</b> Beraberlik</span>
        <span><b>{pct(p2)}</b> {away}</span>
      </div>
    </div>
  );
}
