// Monogram arma (telifsiz): takım adından kısaltma + adın karmasından renk. Maç sayfası ve Maç Merkezi satırları.
const STOP = new Set(["fc", "cf", "sc", "sk", "fk", "afc", "ac", "as", "ss", "us", "cd", "ud", "rc", "rcd", "sv", "vfb", "vfl", "tsg", "1.", "de", "of", "the"]);
export function abbr(n: string): string {
  const w = n.replace(/[^\p{L}\p{N} ]/gu, " ").split(/\s+/).filter((x) => x && !STOP.has(x.toLocaleLowerCase("tr-TR")));
  if (!w.length) return n.slice(0, 3).toLocaleUpperCase("tr-TR");
  return (w.length === 1 ? w[0].slice(0, 3) : w.slice(0, 3).map((x) => x[0]).join("")).toLocaleUpperCase("tr-TR");
}
function hue(n: string): number { let h = 0; for (const c of n) h = (h * 31 + c.charCodeAt(0)) % 360; return h; }
export function Crest({ name, small = false }: { name: string; small?: boolean }) {
  const h = hue(name), t = abbr(name);
  return (
    <svg className={small ? "crest sm" : "crest"} viewBox="0 0 48 56" aria-hidden="true">
      <defs><linearGradient id={`cr${h}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={`hsl(${h} 70% 52%)`} /><stop offset="1" stopColor={`hsl(${(h + 30) % 360} 65% 30%)`} /></linearGradient></defs>
      <path d="M24 2 L44 9 V27 C44 41 35 50 24 54 C13 50 4 41 4 27 V9 Z" fill={`url(#cr${h})`} stroke="rgba(255,255,255,.35)" strokeWidth="1.5" />
      <path d="M24 2 L44 9 V20 H4 V9 Z" fill="rgba(255,255,255,.10)" />
      <text x="24" y="35" textAnchor="middle" fontSize={t.length > 2 ? 13 : 16} fontWeight="800" fill="#fff" fontFamily="Barlow Condensed, sans-serif">{t}</text>
    </svg>
  );
}
