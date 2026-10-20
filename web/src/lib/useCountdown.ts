import { useEffect, useState } from "react";

/** Geri sayım (TSİ bağımsız: hedef ISO zamana kalan süre). */
export function useCountdown(iso: string | null | undefined) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { if (!iso) return; const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, [iso]);
  if (!iso) return null;
  const ms = new Date(iso).getTime() - now;
  if (ms <= 0) return { done: true, h: 0, m: 0, s: 0, d: 0 };
  const s = Math.floor(ms / 1000);
  return { done: false, d: Math.floor(s / 86400), h: Math.floor((s % 86400) / 3600), m: Math.floor((s % 3600) / 60), s: s % 60 };
}
