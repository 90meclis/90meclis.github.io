import type { ReactNode } from "react";
import { cleanLine } from "../lib/text";

// Teknik/iç notları ziyaretçiye göstermemek için süzülen ifadeler
const HIDE = /(anahtar|api[- ]?football|api_|_key|token|kota|kuru çalıştır|service_role)/i;

function inline(s: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;
  let last = 0, m: RegExpExecArray | null, i = 0;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const t = m[0];
    out.push(t.startsWith("**") ? <strong key={i++}>{t.slice(2, -2)}</strong> : <em key={i++}>{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}

/** Botun anlatımını güvenli biçimde gösterir (HTML enjeksiyonu yok). */
export function MiniMd({ text, skipFirst = false, published = false }: { text: string; skipFirst?: boolean; published?: boolean }) {
  let paras = text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  if (skipFirst) paras = paras.slice(1);
  paras = paras
    .map((p) => p.split("\n").filter((l) => !HIDE.test(l)).map((l) => cleanLine(l, published)).filter((l) => l.trim()).join("\n"))
    .filter((p) => p && !HIDE.test(p));
  return (
    <div className="md">
      {paras.map((p, i) => <p key={i}>{p.split("\n").map((l, j) => <span key={j}>{j > 0 && <br />}{inline(l.replace(/^[-•]\s*/, "• "))}</span>)}</p>)}
    </div>
  );
}
