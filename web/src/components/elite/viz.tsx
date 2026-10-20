import { useEffect, useRef, useState, type ReactNode } from "react";
import { fmtLine } from "../../lib/labels";

/** Maç maç çubuklar + çizgi. Yeşil = çizgiyi geçti, gri = geçmedi, kesik = veri yok. */
export function LineBars({ values, line, labels, height = 120, over = true, showVals = true, compact = false }: {
  values: (number | null)[]; line?: number | null; labels?: string[]; height?: number; over?: boolean; showVals?: boolean; compact?: boolean;
}) {
  const max = Math.max(1, (line ?? 0) * 1.25, ...values.map((v) => v ?? 0));
  return (
    <div className={`lb ${compact ? "lb-c" : ""}`} style={{ height }} role="img"
      aria-label={`Eskiden yeniye maç maç: ${values.map((v) => (v === null ? "veri yok" : v)).join(", ")}${line != null ? ` · çizgi ${fmtLine(line)}` : ""}`}>
      {line != null && <div className="lb-line" style={{ bottom: `${(line / max) * 100}%` }}>{!compact && <span>{fmtLine(line)}</span>}</div>}
      {values.map((v, i) => {
        const hit = line == null || v === null ? null : over ? v > line : v < line;
        return (
          <div key={i} className="lb-col" title={`${labels?.[i] ?? ""}${labels?.[i] ? ": " : ""}${v === null ? "veri yok" : v}`}>
            <div className={`lb-bar ${v === null ? "na" : hit === null ? "" : hit ? "hit" : "miss"}`}
              style={{ height: v === null ? "100%" : `${Math.max(3, (v / max) * 100)}%`, animationDelay: `${i * 22}ms` }}>
              {showVals && !compact && <span className="lb-val">{v === null ? "–" : Number.isInteger(v) ? v : v.toFixed(1).replace(".", ",")}</span>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Halka gösterge (isabet / tutma oranı). */
export function Ring({ value, size = 56, label, tone }: { value: number | null; size?: number; label?: ReactNode; tone?: "lime" | "mint" | "loss" | "gold" }) {
  const r = (size - 6) / 2, c = 2 * Math.PI * r, p = Math.max(0, Math.min(1, value ?? 0));
  return (
    <div className={`ring ring-${tone ?? "lime"}`} style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-bg" />
        <circle cx={size / 2} cy={size / 2} r={r} className="ring-fg" strokeDasharray={`${c * p} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      </svg>
      <span>{label ?? (value === null ? "—" : `%${Math.round(p * 100)}`)}</span>
    </div>
  );
}

/** Ekrana girince sayıyı sıfırdan yukarı sayar (hareket azaltma tercihine uyar). */
export function CountUp({ to, digits = 0, prefix = "", suffix = "", signed = false }: { to: number | null; digits?: number; prefix?: string; suffix?: string; signed?: boolean }) {
  const [v, setV] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (to === null) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setV(to); return; }
    let raf = 0; const t0 = performance.now(), d = 700;
    const tick = (t: number) => { const k = Math.min(1, (t - t0) / d); setV(to * (1 - Math.pow(1 - k, 3))); if (k < 1) raf = requestAnimationFrame(tick); };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  if (to === null) return <span>—</span>;
  const s = Math.abs(v).toLocaleString("tr-TR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return <span ref={ref}>{signed && to !== 0 ? (to > 0 ? "+" : "−") : to < 0 ? "−" : ""}{prefix}{s}{suffix}</span>;
}

/** Segmentli seçim (küçük, yatay). */
export function Seg<T extends string>({ value, options, onChange, label }: { value: T; options: [T, ReactNode][]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="eseg" role="radiogroup" aria-label={label}>
      {options.map(([k, l]) => (
        <button key={k} type="button" role="radio" aria-checked={value === k} className={value === k ? "on" : ""} onClick={() => onChange(k)}>{l}</button>
      ))}
    </div>
  );
}

/** Basit yatay oran çubuğu. */
export function HBar({ value, max = 1, tone = "lime" }: { value: number; max?: number; tone?: string }) {
  return <span className={`hbar hb-${tone}`}><i style={{ width: `${Math.max(0, Math.min(1, value / (max || 1))) * 100}%` }} /></span>;
}

