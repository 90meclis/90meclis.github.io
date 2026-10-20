import type { ReactNode } from "react";
import type { PredStatus, Tag } from "../lib/types";
import { STATUS_LABELS, TAG_LABELS, league } from "../lib/labels";

export function PageHead({ kicker, title, children }: { kicker?: string; title: string; children?: ReactNode }) {
  return (
    <header className="page-head">
      {kicker && <p className="kicker">{kicker}</p>}
      <h1>{title}</h1>
      {children && <div className="page-lead">{children}</div>}
    </header>
  );
}

export function Card({ children, className = "", title, aside }: { children: ReactNode; className?: string; title?: ReactNode; aside?: ReactNode }) {
  return (
    <section className={`card ${className}`}>
      {(title || aside) && (
        <div className="card-head">
          {title && <h2 className="card-title">{title}</h2>}
          {aside && <div className="card-aside">{aside}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatusPill({ status }: { status: PredStatus | string }) {
  const label = STATUS_LABELS[status as PredStatus] ?? status;
  return <span className={`pill st-${status}`}><i aria-hidden="true" />{label}</span>;
}

export function TagPill({ tag }: { tag: Tag | string }) {
  return <span className={`tag tag-${tag}`}>{TAG_LABELS[tag as Tag] ?? tag}</span>;
}

export function LeagueBadge({ code, short = false }: { code: string | null | undefined; short?: boolean }) {
  const l = league(code);
  return (
    <span className="league-badge" title={`${l.name}${l.country ? " · " + l.country : ""}`}>
      <span aria-hidden="true">{l.flag}</span> {short ? l.name : `${l.name}`}
    </span>
  );
}

export function Empty({ title, children, icon = "◌" }: { title: string; children?: ReactNode; icon?: string }) {
  return (
    <div className="empty" role="status">
      <div className="empty-icon" aria-hidden="true">{icon}</div>
      <p className="empty-title">{title}</p>
      {children && <div className="empty-text">{children}</div>}
    </div>
  );
}

export function Skeleton({ rows = 4, h = 56 }: { rows?: number; h?: number }) {
  return (
    <div className="skeletons" aria-busy="true" aria-label="Yükleniyor">
      {Array.from({ length: rows }, (_, i) => <div key={i} className="skeleton" style={{ height: h }} />)}
    </div>
  );
}

/** Ortak yükleniyor / bağlantı yok / hata ekranı. */
export function Gate({ loading, error, children, rows }: { loading: boolean; error: string | null; children: ReactNode; rows?: number }) {
  if (error === "offline") return <Empty title="Veriler hazırlanıyor" icon="⏳">Meclis masayı kuruyor. Kısa süre içinde burada olacak.</Empty>;
  if (error) return <Empty title="Veriler şu an yüklenemedi" icon="↻">Bağlantını kontrol edip sayfayı yenilemeyi dene.</Empty>;
  if (loading) return <Skeleton rows={rows} />;
  return <>{children}</>;
}

export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "pos" | "neg" | "muted" }) {
  return (
    <div className={`stat ${tone ? "tone-" + tone : ""}`}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function Meter({ value, max = 100, label }: { value: number | null | undefined; max?: number; label?: string }) {
  const v = value ?? 0;
  const p = Math.max(0, Math.min(1, v / max));
  const tone = p >= 0.6 ? "ok" : p >= 0.4 ? "mid" : "low";
  return (
    <div className={`meter m-${tone}`} role="meter" aria-valuenow={v} aria-valuemin={0} aria-valuemax={max} aria-label={label ?? "Güven"}>
      <span style={{ width: `${p * 100}%` }} />
    </div>
  );
}

export function Chips<T extends string>({ options, value, onChange, label, render }: {
  options: T[]; value: T; onChange: (v: T) => void; label: string; render?: (v: T) => ReactNode;
}) {
  return (
    <div className="chips" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o} type="button" role="radio" aria-checked={o === value} className={`chip ${o === value ? "on" : ""}`} onClick={() => onChange(o)}>
          {render ? render(o) : o}
        </button>
      ))}
    </div>
  );
}

export function Disclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <p className={`disclaimer ${compact ? "compact" : ""}`}>
      <span className="age">18+</span> <span>Tahminler olasılık hesabıdır, kesinlik ya da kazanç garantisi değildir. Sorumlu oyna; kaybetmeyi göze alamayacağın tutarı riske atma. Bahis bağımlılığı için ücretsiz destek: Yeşilay Danışmanlık Merkezi (YEDAM) <a href="tel:115">115</a>.</span>
    </p>
  );
}
