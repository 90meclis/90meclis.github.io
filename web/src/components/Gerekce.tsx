import type { Kart } from "../lib/editorial";

/** Seçimin gerekçe kartı: 3 madde + risk + geri test bandı. */
export function Gerekce({ k, compact = false }: { k: Kart; compact?: boolean }) {
  const body = (
    <>
      <ul className="gk-bullets">{k.maddeler.map((m, i) => <li key={i}>{m}</li>)}</ul>
      {k.risk && <p className="gk-risk"><b>Risk:</b> {k.risk}</p>}
      {k.bant && <p className="gk-band muted tiny">{k.bant.metin}</p>}
    </>
  );
  return compact
    ? <details className="gerekce"><summary>Neden bu seçim?</summary>{body}</details>
    : <div className="gerekce"><span className="gk-title">Neden bu seçim?</span>{body}</div>;
}

export function SonNot({ text }: { text: string }) {
  const ok = text.startsWith("Tuttu") || text.startsWith("Kupon tuttu");
  return <p className={`son-not ${ok ? "ok" : "bad"}`}><b>{ok ? "Neden tuttu" : "Neden yattı"}:</b> {text}</p>;
}
